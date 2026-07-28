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
Anda adalah Master Institutional SMC (Smart Money Concepts) & ICT Elite Trading Mentor yang telah terbukti sukses menumbuhkan modal kecil menjadi portofolio besar secara konsisten melalui eksekusi presisi tinggi dan disiplin risiko 1R ekuitas.

Evaluasi transaksi berikut dengan memberikan ulasan mentor kualitatif yang sangat tajam, realistis, dan sarat insight SMC institusional:

=== PARAMETER TRANS-EKSEKUSI ===
• Pair / Instrumen: {data['symbol_pair']} (Arah: {data['direction'].upper()})
• Hasil Akhir: {data['outcome']} (Realized RR: {data['rr_realized']} R)
• Durasi Posisi: {data['holding_time_minutes']} menit
• Alasan Exit Posisi: {data['exit_reason']}
• Tag Setup SMC: {', '.join(data['setup_tags']) if data['setup_tags'] else 'Order Block / Liquidity Sweep / FVG'}

=== STRUCTURAL MARKET CONTEXT ===
• Trend HTF (4H): {mkt['trend_htf']} | Trend LTF (1H): {mkt['trend_ltf']} | Sesi Trading: {mkt['session']}
• Makro Sentimen: Fear & Greed {mkt['fear_greed_index']} | BTC Dominance {mkt['btc_dominance']}%

=== MENTAL STATE & ADHERENCE TRADER ===
• Confidence Level: {psych['confidence_level']} / 10
• Plan Adherence: {'YA (Disiplin Sesuai Rencana SMC)' if psych['plan_adherence'] else 'TIDAK (Deviasi Rencana / Impulsif)'}
• Tag Bias Emosional: {', '.join(psych['psychological_tags']) if psych['psychological_tags'] else 'Tenang & Terkontrol'}
• Jurnal Bebas Trader: "{psych['free_notes']}"

=== STATISTIK HISTORI SETUP SERUPA ===
• Sampel Histori Setup Ini: {hist['sample_size']} trade
• Win Rate Histori Setup Ini: {hist['win_rate_pct']}%
• Rata-rata RR Histori: {hist['avg_rr']} R
• Expectancy Histori: {hist['expectancy_r']} R

Tuliskan evaluasi dalam 4 bagian Markdown terstruktur khas Mentor SMC Senior:
1. 📌 **Analisis Eksekusi SMC & Order Flow Pasar**
2. 🧠 **Audit Psikologi, Bias Mental & Adherensi Plan**
3. 📊 **Ekspektasi Matematik Jangka Panjang vs Variansi Acak**
4. 💡 **Instruksi Kunci Mentor SMC untuk Scaling Modal**
""".strip()

    @classmethod
    def _call_llm_provider(cls, prompt_text: str, data: Dict[str, Any]) -> str:
        """
        Dispatches prompt to configured LLM provider (Groq / OpenRouter / DeepSeek / Together AI / OpenAI / Gemini / Ollama / Fallback Coach Engine).
        """
        system_prompt = (
            "Anda adalah Master Institutional Smart Money Concepts (SMC) & ICT Elite Trading Mentor "
            "berpengalaman 12+ tahun yang terbukti sukses mengubah akun modal kecil menjadi portofolio "
            "skala besar melalui manajemen risiko 1R ekuitas yang ketat, eksekusi Liquidity Sweeps, "
            "Order Block (OB) mitigation, FVG Imbalances, Inducement, dan HTF Confluence. "
            "Berikan analisis dan bimbingan kualitatif yang sangat tajam, bijak, realistis, dan jujur "
            "layaknya mentor pribadi profesional yang duduk tepat di samping trader."
        )

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
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt_text}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 1200
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
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt_text}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 1200
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
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1200
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
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1200
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

        # Option 5: OpenAI GPT API
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
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    },
                    timeout=15
                )
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}. Falling back to alternate provider.")

        # Option 6: Ollama Local LLM
        ollama_host = getattr(settings, "OLLAMA_HOST", None)
        if ollama_host:
            try:
                logger.info("Calling Ollama Local LLM API for AI Coach review...")
                res = requests.post(
                    f"{ollama_host.rstrip('/')}/api/generate",
                    json={
                        "model": getattr(settings, "OLLAMA_MODEL", "llama3"),
                        "prompt": f"{system_prompt}\n\n{prompt_text}",
                        "stream": False
                    },
                    timeout=20
                )
                if res.status_code == 200:
                    return res.json().get("response", "")
            except Exception as e:
                logger.warning(f"Ollama API call failed: {e}. Falling back to Coach Engine.")

        # Option 7: Gemini API
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
                            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt_text}"}]}]
                        },
                        timeout=15
                    )
                    if res.status_code == 200:
                        candidates = res.json().get("candidates", [])
                        if candidates:
                            return candidates[0]["content"]["parts"][0]["text"]
                    elif res.status_code == 429:
                        logger.warning(f"Gemini API ({model_name}) Quota Exceeded (429): {res.text[:200]}")
                        break
                except Exception as e:
                    logger.warning(f"Gemini API call ({model_name}) failed: {e}.")

        # Option 8: Master SMC Analytic AI Coach Fallback Engine
        logger.info("⚡ Executing Master SMC Analytic AI Coach Fallback Engine...")
        return cls._generate_analytic_fallback_review(data)

    @classmethod
    def _generate_analytic_fallback_review(cls, data: Dict[str, Any]) -> str:
        """
        Generates a deep Master SMC Institutional Mentor qualitative analysis tailored specifically to
        trade outcome, exit reason, holding time, plan adherence, market context, and historical setup metrics.
        """
        outcome = data["outcome"]
        rr = data["rr_realized"]
        pair = data["symbol_pair"]
        direction = data["direction"]
        setup_str = ", ".join(data["setup_tags"]) if data["setup_tags"] else "Order Block / Liquidity Sweep / FVG"
        psych = data["psychology"]
        hist = data["historical_similar_setup"]
        mkt = data["market_context"]
        adherence = psych["plan_adherence"]
        conf = psych["confidence_level"]
        psych_tags = ", ".join(psych["psychological_tags"]) if psych["psychological_tags"] else "Stabil (Terfungsi sempurna)"
        exit_reason = data.get("exit_reason", "N/A")
        holding_mins = data.get("holding_time_minutes", 0)

        # 1. Executive Summary & Duration Dynamics
        if outcome == "WIN":
            summary = f"🔥 **Eksekusi Presisi SMC**: Posisi **{direction} {pair}** berhasil memanen profit **+{rr} R**. Struktur pergerakan *Smart Money Order Flow* berjalan efisien memenuhi area *liquidity target* Anda."
        elif outcome == "LOSS":
            summary = f"🛡️ **Proteksi Modal Teruji**: Posisi **{direction} {pair}** menyentuh Stop Loss sebesar **{rr} R**. Ingat prinsip utama menumbuhkan modal kecil: *1R loss adalah biaya bisnis wajib untuk memburu kemenangan 2R hingga 5R+ saat Liquidity Sweep terkonfirmasi*."
        else:
            summary = f"⚖️ **Breakeven Defense**: Posisi **{direction} {pair}** ditutup pada **0 R**. Pengamanan posisi di titik Breakeven (*BE Move*) berhasil melindungi modal dari pergerakan pembalikan tak terduga."

        # Duration context
        if holding_mins > 0:
            if holding_mins < 15:
                dur_desc = f"Posisi berlangsung sangat kilat (**{holding_mins} menit** - Scalp). Pastikan entry ini murni dipicu *LTF CHOCH / Liquidity Sweep* di POI HTF, bukan karena godaan *candle chasing* impulsif."
            elif holding_mins <= 240:
                dur_desc = f"Durasi eksekusi berjalan terukur selama **{holding_mins} menit** (Intraday SMC Expansion Phase)."
            else:
                dur_desc = f"Posisi ditahan selama **{holding_mins} menit ({holding_mins // 60} jam)** (Swing Structural Position)."
            summary += f"\n• *Dynamic Duration*: {dur_desc}"

        # Exit Reason SMC Detail
        if exit_reason == "take_profit":
            summary += "\n• *Mekanisme Exit*: 🎯 **Take Profit (TP)** tersentuh presisi di area *Unmitigated Order Block / Liquidity Pool* lawan."
        elif exit_reason == "stop_loss":
            summary += "\n• *Mekanisme Exit*: 🛡️ **Stop Loss (SL)** tersentuh. Selalu validasi bahwa SL Anda diletakkan di luar *Invalidation Level / Liquidity Sweep High-Low* yang aman."
        elif exit_reason == "manual_close":
            summary += "\n• *Mekanisme Exit*: ✋ **Manual Close** sebelum TP/SL. Kunci utama menumbuhkan modal kecil menjadi besar adalah membiarkan target R-Multiple berjalan tanpa ditarik secara prematur karena cemas."
        elif exit_reason == "breakeven":
            summary += "\n• *Mekanisme Exit*: ⚖️ **Break Even Move** dipicu untuk mengamankan posisi pasca-pembentukan *BOS / Displacement baru*."

        # 2. Plan Adherence & Psychology Assessment
        if adherence:
            psych_review = (
                f"✅ **Disiplin Mentor SMC**: Anda menunjukkan disiplin eksekusi yang matang (*Plan Adherence: YA*). "
                f"Tingkat keyakinan ({conf}/10) berada pada skala objektif. Catatan emosi: *{psych_tags}* menunjukkan ketenangan seorang profesional."
            )
        else:
            psych_review = (
                f"⚠️ **Peringatan Deviasi Rencana**: Terjadi penyimpangan dari rencana awal (*Plan Adherence: TIDAK*). "
                f"Trader profesional yang berhasil menumbuhkan akun modal kecil HANYA mengeksekusi posisi yang memenuhi 100% kriteria SMC. Jangan biarkan emosi *{psych_tags}* membajak keputusan entry Anda!"
            )

        if psych["free_notes"]:
            psych_review += f"\n• *Refleksi Jurnal*: \"{psych['free_notes']}\""

        htf = mkt.get("trend_htf", "N/A")
        ltf = mkt.get("trend_ltf", "N/A")
        if htf != "N/A" and ltf != "N/A":
            if (direction == "LONG" and htf.lower() == "bullish") or (direction == "SHORT" and htf.lower() == "bearish"):
                psych_review += f"\n• *Struktur Pasar*: 🔥 Entry **{direction}** searah dengan Trend HTF ({htf.upper()}), memberikan dorongan konfluensi institusional yang kuat."
            elif (direction == "LONG" and htf.lower() == "bearish") or (direction == "SHORT" and htf.lower() == "bullish"):
                psych_review += f"\n• *Struktur Pasar*: ⚠️ Entry **{direction}** berlawanan arah dengan Trend HTF ({htf.upper()}). Perdagangan *Counter-Trend* membutuhkan konfirmasi *Liquidity Sweep & CHOCH LTF* yang sangat presisi."

        # 3. Historical Setup Comparison
        if hist["sample_size"] > 0:
            hist_review = (
                f"Populasi data statistik untuk kombinasi setup **[{setup_str}]** mencatat **{hist['sample_size']} trade** historis serupa "
                f"dengan Win Rate **{hist['win_rate_pct']}%** dan Expectancy jangka panjang **{hist['expectancy_r']} R**.\n"
            )
            if outcome == "WIN" and rr > hist["avg_rr"]:
                hist_review += f"Hasil trade ini (+{rr} R) **melampaui rata-rata R-Multiple historisnya ({hist['avg_rr']} R)**, membuktikan presisi penempatan TP di area Liquidity Pool lawan."
            elif outcome == "LOSS":
                hist_review += f"Meskipun trade ini berakhir rugi, ekspektasi statistik jangka panjang setup **[{setup_str}]** tetap **{hist['expectancy_r']} R**. Dalam model 1R Equity Risk, variansi rugi pendek tidak boleh mengganggu keyakinan eksekusi Anda."
        else:
            hist_review = (
                f"Ini adalah transaksi awal untuk kombinasi setup **[{setup_str}]**. Data sampel historis belum mencukupi ($n=0$). "
                f"Kumpulkan hingga 20 trade bertag identik untuk mengaktifkan kalkulasi Edge Discovery."
            )

        # 4. Actionable Key Takeaways for Scaling Account
        takeaways = []
        if not adherence:
            takeaways.append("• **Instruksi Mentor**: Dilarang keras menekan tombol Entry tanpa menandai syarat setup SMC lengkap di Quick-Tag. Kedisiplinan adalah pintu utama pertumbuhan akun.")
        if outcome == "LOSS" and holding_mins < 10:
            takeaways.append("• **Instruksi Mentor**: Durasi trade terlalu singkat pasca-entry. Biarkan struktur harga bernapas sesuai perhitungan ATR dan jarak SL awal.")
        if outcome == "WIN" and rr >= 2.0:
            takeaways.append("• **Instruksi Mentor**: Kunci profit secara bertahap saat R-Multiple melampaui +2R dengan menggeser SL ke Breakeven setelah pembentukan BOS baru.")
        if exit_reason == "manual_close":
            takeaways.append("• **Instruksi Mentor**: Evaluasi alasan penutupan manual pada jurnal. Menutupi posisi terlalu cepat menghancurkan ekspektasi matematis RR tinggi.")

        if not takeaways:
            takeaways.append("• **Instruksi Mentor**: Pertahankan manajemen risiko 1R ekuitas konstan ($0.96) dan fokus pada konfluensi HTF Discount/Premium Zone.")
            takeaways.append("• **Instruksi Mentor**: Selalu tunggu pembentukan *Liquidity Sweep & CHOCH* sebelum mengeksekusi entry di LTF.")

        return f"""📌 **Analisis Eksekusi SMC & Order Flow Pasar**
{summary}

🧠 **Audit Psikologi, Bias Mental & Adherensi Plan**
{psych_review}

📊 **Ekspektasi Matematik Jangka Panjang vs Variansi Acak**
{hist_review}

💡 **Instruksi Kunci Mentor SMC untuk Scaling Modal**
{chr(10).join(takeaways)}
""".strip()

    @classmethod
    def generate_weekly_review(cls, db: Session, start_date: str, end_date: str, data_source: str = "all") -> Dict[str, Any]:
        """
        Generates weekly AI Coach executive evaluation for all trades within the specified date range.
        Synthesizes weekly performance, psychological tendencies, plan adherence, setup efficiency,
        and provides 3 key mindset directives for the upcoming trading week.
        """
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except Exception:
            raise ValueError("Format tanggal harus YYYY-MM-DD (contoh: 2026-07-27).")

        query = db.query(Trade).filter(
            Trade.entry_time >= s_dt,
            Trade.entry_time <= e_dt,
            Trade.exit_time != None
        )
        if data_source and data_source != "all":
            query = query.filter(Trade.data_source == data_source)

        trades = query.all()
        if not trades:
            return {
                "start_date": start_date,
                "end_date": end_date,
                "total_trades": 0,
                "review_markdown": f"### 🤖 Evaluasi AI Coach Mingguan ({start_date} s/d {end_date})\n\nBelum ada transaksi tertutup yang tercatat pada rentang minggu ini. Lakukan entry transaksi baru dan catat Quick-Tag untuk mulai mengumpulkan statistik evaluasi mingguan Anda."
            }

        # Calculate weekly metrics
        total_trades = len(trades)
        wins = [t for t in trades if t.pnl and float(t.pnl) > 0]
        win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
        total_pnl = sum(float(t.pnl) for t in trades if t.pnl)
        total_r = sum(float(t.rr_realized) for t in trades if t.rr_realized)

        # Gather psychology metrics
        psychologies = []
        for t in trades:
            if t.psychology:
                psychologies.append(t.psychology)

        adherence_count = sum(1 for p in psychologies if p.plan_adherence)
        adherence_pct = (adherence_count / len(psychologies)) * 100.0 if psychologies else 100.0

        # Collect psychological tags
        all_tags = []
        for p in psychologies:
            if p.psychological_tags:
                all_tags.extend(p.psychological_tags if isinstance(p.psychological_tags, list) else [])

        from collections import Counter
        tag_counts = Counter(all_tags)
        top_tags_str = ", ".join([f"{k} ({v}x)" for k, v in tag_counts.most_common(4)]) if tag_counts else "Sesuai Plan, Tenang"

        # Generate LLM or Fallback Review
        review_markdown = cls._build_weekly_review_markdown(
            start_date=start_date,
            end_date=end_date,
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_r=total_r,
            adherence_pct=adherence_pct,
            top_tags_str=top_tags_str,
            trades=trades
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "total_r": round(total_r, 2),
            "adherence_pct": round(adherence_pct, 1),
            "review_markdown": review_markdown
        }

    @classmethod
    def _build_weekly_review_markdown(
        cls,
        start_date: str,
        end_date: str,
        total_trades: int,
        win_rate: float,
        total_pnl: float,
        total_r: float,
        adherence_pct: float,
        top_tags_str: str,
        trades: List[Trade]
    ) -> str:
        prompt_text = f"""Anda adalah Master Institutional Smart Money Concepts (SMC) & ICT Elite Trading Mentor yang berpengalaman mengubah modal kecil menjadi portofolio besar secara konsisten.

Berikan evaluasi audit kualitatif mingguan yang sangat tajam, inspiratif, realistis, dan berorientasi pada pertumbuhan modal untuk trader berdasarkan data minggu ini ({start_date} s.d. {end_date}):

METRIK AUDIT MINGGUAN:
- Total Posisi: {total_trades} transaksi
- Win Rate: {win_rate:.1f}%
- Total PnL Bersih: ${total_pnl:.2f}
- Akumulasi Realized RR: {total_r:+.2f} R
- Kepatuhan Rencana Trading (Plan Adherence): {adherence_pct:.1f}%
- Pola Emosi Dominan: {top_tags_str}

Formatkan audit mingguan dalam 4 bagian Markdown terstruktur khas Mentor SMC Senior:
1. 📊 **Audit Performa Executive & Pertumbuhan Ekuitas R**
2. 🧠 **Review Psikologi, Kontrol Emosi & Kedisiplinan SMC**
3. 🎯 **Analisis Efisiensi Order Flow & Eksekusi**
4. 💡 **3 Instruksi Emas Mentor SMC untuk Scaling Akun Minggu Depan**

Gunakan bahasa Indonesia yang tegas, bijak, profesional, mendalam, kaya terminologi SMC (Liquidity Sweeps, Discount/Premium, Order Block, FVG, 1R Risk), layaknya bimbingan privat dari mentor senior."""

        try:
            llm_res = cls._call_llm_provider(prompt_text, {})
            if llm_res and len(llm_res) > 50:
                return llm_res
        except Exception as e:
            logger.warning(f"LLM call failed for weekly review fallback: {e}")

        pnl_sign = "+" if total_pnl >= 0 else ""
        r_sign = "+" if total_r >= 0 else ""
        status_eval = "sangat presisi dan berdisiplin tinggi" if total_r > 0 else "memerlukan pembenahan kontrol risiko & disiplin SMC"

        return f"""### 🤖 Audit & Bimbingan Privat Mentor SMC Mingguan ({start_date} s/d {end_date})

📊 **Audit Performa Executive & Pertumbuhan Ekuitas R**
Minggu ini Anda telah menyelesaikan **{total_trades} posisi transaksi** dengan *Win Rate* **{win_rate:.1f}%**, menghasilkan pencapaian akumulasi **{r_sign}{total_r:.2f} R** ({pnl_sign}${total_pnl:.2f}). Kualitas eksekusi trading Anda pada periode ini dinilai **{status_eval}** dari kacamata ekspektasi matematis R-Multiple.

🧠 **Review Psikologi, Kontrol Emosi & Kedisiplinan SMC**
• Kepatuhan Rencana (*Plan Adherence*): **{adherence_pct:.1f}%** dari total posisi.
• Kondisi Emosi Dominan: *{top_tags_str}*.
• *Prinsip Mentor*: Kunci utama menumbuhkan modal kecil menjadi besar BUKAN dengan memperbesar leverage atau mengambil risiko nekat (gambling), melainkan menjaga keutuhan 1R Risk (1.0% Equity) secara religius dan membiarkan *Liquidity Sweep & Order Block mitigation* bekerja menghasilkan R-Multiple tinggi (1:2R hingga 1:5R+).

🎯 **Analisis Efisiensi Order Flow & Eksekusi**
Seluruh posisi minggu ini telah terdokumentasi di lembar jurnal. Penggunaan model **1R Equity Risk konstan** memastikan akun Anda terlindungi dari bahaya *catastrophic drawdown* saat menghadapi variansi acak pasar.

💡 **3 Instruksi Emas Mentor SMC untuk Scaling Akun Minggu Depan**
1. • **Instruksi 1 (SMC High Confluence Only)**: Hanya buka posisi entry ketika harga berada di *Discount Zone* untuk LONG atau *Premium Zone* untuk SHORT yang bertepatan dengan *Liquidity Sweep* di session Asia/London/NY.
2. • **Instruksi 2 (Kunci Bias Subjektif di Quick-Tag)**: Jangan pernah melewatkan pengisian Quick-Tag dalam 120 detik pasca-entry untuk mengunci bias psikologis sebelum hasil trade keluar.
3. • **Instruksi 3 (Kedisiplinan 1R Equity Risk)**: Jaga risiko per trade tepat di 1.0% Total Equity ($0.96). Biarkan ekspektasi positif matematika R-Multiple menumbuhkan saldo Anda secara konsisten dari minggu ke minggu.
""".strip()
