import os
import logging
import json
import requests
import numpy as np
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.models.models import Trade, Psychology, MarketContext, TradeExecution, AICoachReview
from app.services.analytics_engine import AnalyticsEngine

logger = logging.getLogger(__name__)


class AICoachService:
    """
    FITUR 14 - Asisten AI (AI Coach Service)
    
    Provides post-trade qualitative evaluations and contextual coaching feedback.
    Compares current trade performance with historical metrics of similar setup tags while
    strictly anonymizing raw account balances, API credentials, leverage, and raw margin USD.
    """

    @classmethod
    def generate_trade_review(cls, db: Session, trade_id: str) -> Dict[str, Any]:
        """
        Gathers anonymized trade data, psychology, market context, and historical setup metrics,
        builds a structured prompt, calls the LLM provider (OpenAI / Ollama / Gemini / Fallback),
        saves the review to MySQL `psychology.ai_coach_review`, and returns the qualitative feedback.
        """
        logger.info(f"🤖 Generating AI Coach review for trade_id: {trade_id}...")

        # 1. Fetch & Validate Trade
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade:
            raise ValueError(f"Trade dengan ID '{trade_id}' tidak ditemukan.")

        if trade.exit_time is None:
            raise ValueError("Evaluasi AI Coach hanya dapat dilakukan untuk trade yang sudah ditutup (exit_time tidak NULL).")

        # 2. Gather Setup Tags
        tag_rows = db.execute(text("""
            SELECT stv.tag_name 
            FROM trade_setup_tags st
            JOIN setup_taxonomy_versions stv ON st.taxonomy_version_id = stv.id
            WHERE st.trade_id = :trade_id
        """), {"trade_id": trade_id}).fetchall()

        setup_tags = [r.tag_name for r in tag_rows]

        # 3. Gather Market Context
        mkt = db.query(MarketContext).filter(MarketContext.trade_id == trade_id).first()
        mkt_info = {
            "trend_htf": mkt.trend_htf if mkt else "N/A",
            "trend_ltf": mkt.trend_ltf if mkt else "N/A",
            "session": mkt.session if mkt else "N/A",
            "fear_greed_index": mkt.fear_greed_index if mkt else "N/A",
            "btc_dominance": float(mkt.btc_dominance) if mkt and mkt.btc_dominance else "N/A",
        }

        # 4. Gather Psychology Data
        psych = db.query(Psychology).filter(Psychology.trade_id == trade_id).first()
        psych_info = {
            "confidence_level": psych.confidence_level if psych else 5,
            "psychological_tags": psych.psychological_tags if psych and psych.psychological_tags else [],
            "plan_adherence": psych.plan_adherence if psych else True,
            "free_notes": psych.free_notes if psych else "",
        }

        # 5. Gather Trade Execution Data
        exec_info = db.query(TradeExecution).filter(TradeExecution.trade_id == trade_id).first()
        exit_reason = exec_info.exit_reason if exec_info and exec_info.exit_reason else "N/A"

        # 6. Gather Historical Setup Metrics
        similar_metrics = cls._fetch_similar_setup_metrics(db, setup_tags, current_trade_id=trade_id)

        # 7. Anonymize Trade Data (Strict Rule: NO raw balance, NO API keys, NO leverage, NO USD margin)
        anonymized_payload = cls._anonymize_trade_data(
            trade=trade,
            setup_tags=setup_tags,
            mkt_info=mkt_info,
            psych_info=psych_info,
            exit_reason=exit_reason,
            similar_metrics=similar_metrics
        )

        # 8. Build Prompt
        prompt_text = cls._build_prompt(anonymized_payload)

        # 9. Call LLM Provider (OpenAI / Ollama / Gemini / Fallback Engine)
        review_text = cls._call_llm_provider(prompt_text, anonymized_payload)

        # 10. Save to Dedicated DB Table (`ai_coach_reviews`)
        existing_review = db.query(AICoachReview).filter(AICoachReview.trade_id == trade_id).first()
        if not existing_review:
            existing_review = AICoachReview(
                trade_id=trade_id,
                review_type='post_trade_critique',
                feedback_markdown=review_text
            )
            db.add(existing_review)
        else:
            existing_review.feedback_markdown = review_text

        db.commit()

        logger.info(f"✅ AI Coach review successfully stored in ai_coach_reviews for trade {trade_id}.")

        return {
            "trade_id": trade_id,
            "pair": trade.pair,
            "direction": trade.direction,
            "ai_coach_review": review_text,
            "created_at": datetime.now().isoformat(),
            "anonymized_context": anonymized_payload
        }

    @classmethod
    def _anonymize_trade_data(
        cls,
        trade: Trade,
        setup_tags: List[str],
        mkt_info: Dict[str, Any],
        psych_info: Dict[str, Any],
        exit_reason: str,
        similar_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filters and anonymizes trade details according to Security Rule 9 & 16:
        Removes raw account balances, API credentials, leverage multiplier, and raw USD margin.
        """
        # Calculate holding duration
        holding_mins = 0
        if trade.entry_time and trade.exit_time:
            holding_mins = int((trade.exit_time - trade.entry_time).total_seconds() / 60)

        rr_realized = float(trade.rr_realized) if trade.rr_realized is not None else 0.0
        pnl_val = float(trade.pnl) if trade.pnl is not None else 0.0
        outcome = "WIN" if pnl_val > 0 else ("LOSS" if pnl_val < 0 else "BREAKEVEN")

        return {
            "symbol_pair": trade.pair,
            "direction": trade.direction.upper(),
            "outcome": outcome,
            "rr_realized": rr_realized,
            "holding_time_minutes": holding_mins,
            "exit_reason": exit_reason,
            "setup_tags": setup_tags,
            "market_context": mkt_info,
            "psychology": psych_info,
            "historical_similar_setup": similar_metrics
        }

    @classmethod
    def _fetch_similar_setup_metrics(
        cls,
        db: Session,
        setup_tags: List[str],
        current_trade_id: str
    ) -> Dict[str, Any]:
        """
        Fetches historical performance metrics for trades sharing identical setup tags.
        """
        if not setup_tags:
            return {"sample_size": 0, "win_rate_pct": 0.0, "avg_rr": 0.0, "expectancy_r": 0.0}

        placeholders = ", ".join([f"'{t}'" for t in setup_tags])
        tag_count = len(setup_tags)

        sql = f"""
            SELECT t.id, t.rr_realized, t.pnl
            FROM trades t
            JOIN trade_setup_tags st ON t.id = st.trade_id
            JOIN setup_taxonomy_versions stv ON st.taxonomy_version_id = stv.id
            WHERE stv.tag_name IN ({placeholders})
              AND t.id != '{current_trade_id}'
              AND t.exit_time IS NOT NULL
            GROUP BY t.id
            HAVING COUNT(DISTINCT stv.tag_name) >= {tag_count}
        """
        rows = db.execute(text(sql)).fetchall()
        sample_size = len(rows)

        if sample_size == 0:
            return {"sample_size": 0, "win_rate_pct": 0.0, "avg_rr": 0.0, "expectancy_r": 0.0}

        wins = sum(1 for r in rows if float(r.pnl or 0) > 0)
        win_rate_pct = round((wins / sample_size) * 100.0, 2)
        r_list = [float(r.rr_realized) if r.rr_realized is not None else (1.0 if float(r.pnl or 0) > 0 else -1.0) for r in rows]
        avg_rr = round(sum(r_list) / sample_size, 4)

        loss_rate = 1.0 - (wins / sample_size)
        win_rate = wins / sample_size
        avg_win_r = np.mean([r for r in r_list if r > 0]) if any(r > 0 for r in r_list) else 1.0
        avg_loss_r = abs(np.mean([r for r in r_list if r < 0])) if any(r < 0 for r in r_list) else 1.0
        expectancy_r = round(float((win_rate * avg_win_r) - (loss_rate * avg_loss_r)), 4)

        return {
            "sample_size": sample_size,
            "win_rate_pct": win_rate_pct,
            "avg_rr": avg_rr,
            "expectancy_r": expectancy_r
        }

    @classmethod
    def _build_prompt(cls, data: Dict[str, Any]) -> str:
        """
        Constructs an elite Master SMC Institutional Trading Coach evaluation prompt.
        """
        hist = data["historical_similar_setup"]
        psych = data["psychology"]
        mkt = data["market_context"]

        return f"""
Anda adalah Master Institutional SMC (Smart Money Concepts) & Elite Trading Coach dunia yang telah sukses mengubah modal kecil menjadi portofolio besar secara konsisten.
Anda menguasai analisis Struktur Pasar (BOS, CHOCH, Liquidity Sweeps Asia/London/NY, Premium/Discount Arrays, Order Blocks, Fair Value Gap/FVG, dan SMT Divergence).
Tugas Anda adalah memberikan ulasan kualitatif pasca-trade (*post-trade review*) yang sangat tajam, profesional, realistis, dan mendalam berdasarkan data anonim berikut.

=== DATA TRADING EKSEKUSI ===
• Instrumen/Pair: {data['symbol_pair']} (Arah: {data['direction']})
• Hasil Akhir: {data['outcome']} (Realized RR: {data['rr_realized']} R)
• Durasi Penahanan Posisi: {data['holding_time_minutes']} menit
• Alasan Exit Posisi: {data['exit_reason']}
• Setup Tag Komposisi: {', '.join(data['setup_tags']) if data['setup_tags'] else 'Order Block / Liquidity Sweep'}

=== KONTEKS PASAR INSTITUSIONAL ===
• Tren HTF (High Timeframe): {mkt['trend_htf']} | Tren LTF (Low Timeframe): {mkt['trend_ltf']} | Sesi Trading: {mkt['session']}
• Sentimen Pasar (Fear & Greed): {mkt['fear_greed_index']} | BTC Dominance: {mkt['btc_dominance']}%

=== PSIKOLOGI & EKSEKUSI TRADER ===
• Level Kepercayaan (1-10): {psych['confidence_level']} / 10
• Kepatuhan Rencana Trading (Plan Adherence): {'YA (Sangat Disiplin)' if psych['plan_adherence'] else 'TIDAK (Terjadi Deviasi Rencana)'}
• Tag Bias Emosional: {', '.join(psych['psychological_tags']) if psych['psychological_tags'] else 'Stabil (Tanpa bias emosional)'}
• Catatan Bebas Trader: "{psych['free_notes']}"

=== STATISTIK HISTORI SETUP SERUPA ===
• Ukuran Sampel Histori: {hist['sample_size']} trade serupa
• Win Rate Histori Setup Ini: {hist['win_rate_pct']}%
• Rata-rata RR Histori: {hist['avg_rr']} R
• Expectancy Histori: {hist['expectancy_r']} R

Berikan ulasan terstruktur dalam format Markdown berbahasa Indonesia yang tegas, motivatif, profesional, dan kaya akan perspektif institusional SMC dengan 4 bagian berikut:
1. 📌 **Ringkasan Eksekusi & Hasil**
2. 🧠 **Analisis Psikologi, Adherensi Rencana & Bias Market**
3. 📊 **Perbandingan statistik Ekspektasi Jangka Panjang vs Variansi Trade**
4. 💡 **Rekomendasi Aksi Konkret SMC & Manajemen Risiko**
""".strip()

    @classmethod
    def _call_llm_provider(cls, prompt_text: str, data: Dict[str, Any]) -> str:
        """
        Dispatches prompt to configured LLM provider (Groq / OpenRouter / DeepSeek / Together AI / OpenAI / Gemini / Ollama / Fallback Coach Engine).
        """
        # Option 1: Groq Cloud API (Super-fast, Llama 3.3 70B & DeepSeek R1)
        groq_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY")
        if groq_key and len(str(groq_key)) > 5:
            groq_models = ["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b", "gemma2-9b-it"]
            for model_id in groq_models:
                try:
                    logger.info(f"Calling Groq Cloud API ({model_id}) for AI Coach review...")
                    res = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {groq_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": "Anda adalah AI Trading Coach senior yang analitis, disiplin, dan objektif."},
                                {"role": "user", "content": prompt_text}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 1000
                        },
                        timeout=12
                    )
                    if res.status_code == 200:
                        choices = res.json().get("choices", [])
                        if choices and choices[0].get("message", {}).get("content"):
                            content = choices[0]["message"]["content"]
                            if len(content.strip()) > 10:
                                logger.info(f"✅ Groq API ({model_id}) review successfully generated!")
                                return content
                    else:
                        logger.warning(f"Groq API ({model_id}) status {res.status_code}: {res.text[:200]}")
                except Exception as e:
                    logger.warning(f"Groq API call ({model_id}) failed: {e}.")

        # Option 2: OpenRouter Free API
        openrouter_key = getattr(settings, "OPENROUTER_API_KEY", None) or os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key and len(str(openrouter_key)) > 5:
            openrouter_models = [
                "inclusionai/ling-3.0-flash:free",
                "google/gemma-4-31b-it:free",
                "poolside/laguna-s-2.1:free",
                "openrouter/free"
            ]
            for model_id in openrouter_models:
                try:
                    logger.info(f"Calling OpenRouter API ({model_id}) for AI Coach review...")
                    res = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {openrouter_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:3000",
                            "X-Title": "TEIS AI Coach"
                        },
                        json={
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": "Anda adalah AI Trading Coach senior yang analitis dan disiplin."},
                                {"role": "user", "content": prompt_text}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 1000
                        },
                        timeout=15
                    )
                    if res.status_code == 200:
                        choices = res.json().get("choices", [])
                        if choices and choices[0].get("message", {}).get("content"):
                            content = choices[0]["message"]["content"]
                            if len(content.strip()) > 10:
                                logger.info(f"✅ OpenRouter API ({model_id}) review successfully generated!")
                                return content
                    else:
                        logger.warning(f"OpenRouter API ({model_id}) status {res.status_code}: {res.text[:200]}")
                except Exception as e:
                    logger.warning(f"OpenRouter API call ({model_id}) failed: {e}.")

        # Option 3: DeepSeek Official API
        deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", None) or os.environ.get("DEEPSEEK_API_KEY")
        if deepseek_key and len(str(deepseek_key)) > 5:
            try:
                logger.info("Calling DeepSeek Official API for AI Coach review...")
                res = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {deepseek_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "Anda adalah AI Trading Coach senior yang analitis."},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    },
                    timeout=15
                )
                if res.status_code == 200:
                    choices = res.json().get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        return choices[0]["message"]["content"]
                else:
                    logger.warning(f"DeepSeek API status {res.status_code}: {res.text[:200]}")
            except Exception as e:
                logger.warning(f"DeepSeek API call failed: {e}.")

        # Option 4: Together AI API
        together_key = getattr(settings, "TOGETHER_API_KEY", None) or os.environ.get("TOGETHER_API_KEY")
        if together_key and len(str(together_key)) > 5:
            try:
                logger.info("Calling Together AI API for AI Coach review...")
                res = requests.post(
                    "https://api.together.xyz/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {together_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                        "messages": [
                            {"role": "system", "content": "Anda adalah AI Trading Coach senior yang analitis."},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    },
                    timeout=15
                )
                if res.status_code == 200:
                    choices = res.json().get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        return choices[0]["message"]["content"]
                else:
                    logger.warning(f"Together AI API status {res.status_code}: {res.text[:200]}")
            except Exception as e:
                logger.warning(f"Together AI API call failed: {e}.")

        # Option 1: OpenAI GPT API
        openai_key = getattr(settings, "OPENAI_API_KEY", None)
        if openai_key and len(str(openai_key)) > 5:
            try:
                logger.info("Calling OpenAI GPT API for AI Coach review...")
                res = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": getattr(settings, "LLM_MODEL", "gpt-4o-mini"),
                        "messages": [
                            {"role": "system", "content": "Anda adalah AI Trading Coach yang analitis dan disiplin."},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 800
                    },
                    timeout=15
                )
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}. Falling back to alternate provider.")

        # Option 2: Ollama Local LLM
        ollama_host = getattr(settings, "OLLAMA_HOST", None)
        if ollama_host:
            try:
                logger.info("Calling Ollama Local LLM API for AI Coach review...")
                res = requests.post(
                    f"{ollama_host.rstrip('/')}/api/generate",
                    json={
                        "model": getattr(settings, "OLLAMA_MODEL", "llama3"),
                        "prompt": prompt_text,
                        "stream": False
                    },
                    timeout=20
                )
                if res.status_code == 200:
                    return res.json().get("response", "")
            except Exception as e:
                logger.warning(f"Ollama API call failed: {e}. Falling back to Coach Engine.")

        # Option 3: Gemini API / Antigravity
        gemini_key = getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GEMINI_API_KEY")
        if gemini_key and len(str(gemini_key)) > 5:
            models_to_try = [
                getattr(settings, "LLM_MODEL", "gemini-2.0-flash"),
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "gemini-1.5-flash"
            ]
            for model_name in models_to_try:
                try:
                    logger.info(f"Calling Gemini API ({model_name}) for AI Coach review...")
                    res = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
                        headers={
                            "Content-Type": "application/json",
                            "X-goog-api-key": gemini_key
                        },
                        json={
                            "contents": [{"parts": [{"text": prompt_text}]}]
                        },
                        timeout=15
                    )
                    if res.status_code == 200:
                        candidates = res.json().get("candidates", [])
                        if candidates:
                            return candidates[0]["content"]["parts"][0]["text"]
                    elif res.status_code == 429:
                        logger.warning(f"Gemini API ({model_name}) Quota Exceeded (429): {res.text[:200]}")
                        break  # Quota exceeded for project
                except Exception as e:
                    logger.warning(f"Gemini API call ({model_name}) failed: {e}.")

        # Option 4: Structured Analytic AI Coach Fallback Engine (Data-driven, Production Ready)
        logger.info("⚡ Executing Analytic AI Coach Fallback Engine...")
        return cls._generate_analytic_fallback_review(data)

    @classmethod
    def _generate_analytic_fallback_review(cls, data: Dict[str, Any]) -> str:
        """
        Generates a deep, dynamic, data-driven qualitative analysis tailored specifically to
        trade outcome, exit reason, holding time, plan adherence, market context, and historical setup metrics.
        """
        outcome = data["outcome"]
        rr = data["rr_realized"]
        pair = data["symbol_pair"]
        direction = data["direction"]
        setup_str = ", ".join(data["setup_tags"]) if data["setup_tags"] else "Tidak bertag"
        psych = data["psychology"]
        hist = data["historical_similar_setup"]
        mkt = data["market_context"]
        adherence = psych["plan_adherence"]
        conf = psych["confidence_level"]
        psych_tags = ", ".join(psych["psychological_tags"]) if psych["psychological_tags"] else "Stabil (Tanpa bias emosional)"
        exit_reason = data.get("exit_reason", "N/A")
        holding_mins = data.get("holding_time_minutes", 0)

        # 1. Executive Summary & Duration Dynamics
        if outcome == "WIN":
            summary = f"Posisi **{direction} {pair}** berhasil menghasilkan profit sebesar **+{rr} R**. Eksekusi berjalan efektif selaras dengan pergerakan pasar."
        elif outcome == "LOSS":
            summary = f"Posisi **{direction} {pair}** berakhir rugi sebesar **{rr} R**. Risiko terbatasi sesuai batas Stop Loss yang direncanakan."
        else:
            summary = f"Posisi **{direction} {pair}** ditutup pada **Breakeven (0 R)** tanpa keuntungan atau kerugian bersih."

        # Duration context
        if holding_mins > 0:
            if holding_mins < 15:
                dur_desc = f"Posisi berlangsung sangat cepat (**{holding_mins} menit** - Scalp). Perhatikan dampak akumulasi fee transaksi pada frekuensi trading tinggi."
            elif holding_mins <= 240:
                dur_desc = f"Durasi posisi berjalan terukur selama **{holding_mins} menit** (Intraday)."
            else:
                dur_desc = f"Posisi ditahan relatif lama selama **{holding_mins} menit ({holding_mins // 60} jam)** (Swing)."
            summary += f"\n• *Durasi Execution*: {dur_desc}"

        # Exit Reason Detail
        if exit_reason == "take_profit":
            summary += "\n• *Alasan Exit*: 🎯 **Take Profit (TP)** tersentuh sesuai target harga utama."
        elif exit_reason == "stop_loss":
            summary += "\n• *Alasan Exit*: 🛡️ **Stop Loss (SL)** tersentuh, menghentikan akumulasi risiko."
        elif exit_reason == "manual_close":
            summary += "\n• *Alasan Exit*: ✋ **Manual Close** sebelum mengenai TP/SL. Evaluasi apakah penutupan manual ini didasari sinyal struktur harga yang valid atau rasa cemas (*anxiety*)."
        elif exit_reason == "breakeven":
            summary += "\n• *Alasan Exit*: ⚖️ **Break Even Move** dipicu untuk mengamankan posisi."

        # 2. Plan Adherence & Psychology Assessment
        if adherence:
            psych_review = (
                f"✅ **Disiplin Teruji**: Anda menunjukkan adherensi rencana trading yang baik (Plan Adherence: YA). "
                f"Tingkat kepercayaan saat entry ({conf}/10) berada pada skala seimbang. "
                f"Catatan emosi: *{psych_tags}*."
            )
        else:
            psych_review = (
                f"⚠️ **Deviasi Rencana Trading**: Terdeteksi adanya penyimpangan dari rencana awal (Plan Adherence: TIDAK). "
                f"Dengan tingkat kepercayaan {conf}/10 dan tag emosi *{psych_tags}*, periksa apakah entry ini terpengaruh oleh dorongan FOMO atau dorongan pembalasan (*revenge trading*)."
            )

        if psych["free_notes"]:
            psych_review += f"\n• *Catatan Jurnal*: \"{psych['free_notes']}\""

        # Market trend alignment
        htf = mkt.get("trend_htf", "N/A")
        ltf = mkt.get("trend_ltf", "N/A")
        if htf != "N/A" and ltf != "N/A":
            if (direction == "LONG" and htf.lower() == "bullish") or (direction == "SHORT" and htf.lower() == "bearish"):
                psych_review += f"\n• *Struktur Pasar*: 🔥 Entry **{direction}** searah dengan Trend HTF ({htf.upper()}), meningkatkan probabilitas sukses."
            elif (direction == "LONG" and htf.lower() == "bearish") or (direction == "SHORT" and htf.lower() == "bullish"):
                psych_review += f"\n• *Struktur Pasar*: ⚠️ Entry **{direction}** berlawanan dengan Trend HTF ({htf.upper()}). Membutuhkan konfirmasi pembalikan arah LTF yang sangat presisi."

        # 3. Historical Setup Comparison
        if hist["sample_size"] > 0:
            hist_review = (
                f"Kombinasi setup **[{setup_str}]** tercatat memiliki populasi **{hist['sample_size']} trade** historis serupa "
                f"dengan Win Rate **{hist['win_rate_pct']}%** dan Expectancy statistik **{hist['expectancy_r']} R**.\n"
            )
            if outcome == "WIN" and rr > hist["avg_rr"]:
                hist_review += f"Hasil trade ini (+{rr} R) **melampaui rata-rata Risk-to-Reward historisnya ({hist['avg_rr']} R)**, menunjukkan kualitas eksekusi titik exit yang optimal."
            elif outcome == "LOSS":
                hist_review += f"Meskipun trade ini berakhir rugi, ekspektasi statistik jangka panjang setup **[{setup_str}]** tetap **{hist['expectancy_r']} R**. Kerugian acak adalah bagian alami dari sampel statistik."
        else:
            hist_review = (
                f"Ini adalah transaksi pertama untuk kombinasi setup **[{setup_str}]**. Data sampel historis belum mencukupi ($n=0$). "
                f"Kumpulkan hingga 20 trade bertag identik untuk mengaktifkan kalkulasi Edge Discovery."
            )

        # 4. Actionable Key Takeaways
        takeaways = []
        if not adherence:
            takeaways.append("• **Aksi Kunci**: Jangan pernah membuka posisi tanpa menandai kriteria setup Quick-Tag secara lengkap di lembar jurnal.")
        if outcome == "LOSS" and holding_mins < 10:
            takeaways.append("• **Aksi Kunci**: Durasi trade sangat singkat pasca-entry. Berikan posisi ruang bernapas sesuai jarak ATR/SL awal.")
        if outcome == "WIN" and rr >= 2.0:
            takeaways.append("• **Aksi Kunci**: Pertahankan teknik penguncian profit (trailing stop/partial exit) saat R-multiple melampaui +2R.")
        if exit_reason == "manual_close":
            takeaways.append("• **Aksi Kunci**: Catat alasan pasti penutupan manual pada kolom catatan bebas untuk mengevaluasi apakah exit manual tersebut konsisten menambah profit atau merusak expectancy.")
        
        if not takeaways:
            takeaways.append("• Pertahankan konsistensi dokumentasi jurnal harian dan jaga rasio risiko per trade tetap konstan.")
            takeaways.append("• Evaluasi kembali titik entry pada timeframe LTF untuk mengoptimalkan presisi Risk-to-Reward.")

        return f"""📌 **Ringkasan Eksekusi & Hasil**
{summary}

🧠 **Analisis Psikologi & Adherensi Rencana**
{psych_review}

📊 **Perbandingan dengan Histori Setup**
{hist_review}

💡 **Rekomendasi & Tindakan Kunci**
{chr(10).join(takeaways)}
""".strip()
