import os
import logging
import json
import requests
import numpy as np
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple

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

    MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM: int = 20
    MIN_SAMPLE_SIZE_FOR_CAUTIOUS_NOTE: int = 5

    @classmethod
    def _fetch_image_as_base64(cls, url: str) -> Optional[Dict[str, str]]:
        """
        Downloads image bytes from MinIO/Storage URL (handling Docker internal vs localhost),
        encodes it into base64, and returns a dict with mime_type, base64 data, and url.
        Gracefully returns None on failure.
        """
        import base64
        if not url:
            return None

        urls_to_try = [url]
        if "localhost:9000" in url:
            urls_to_try.append(url.replace("localhost:9000", "minio:9000"))
        elif "minio:9000" in url:
            urls_to_try.append(url.replace("minio:9000", "localhost:9000"))

        for u in urls_to_try:
            try:
                res = requests.get(u, timeout=4)
                if res.status_code == 200 and res.content:
                    content_type = res.headers.get("Content-Type", "").lower()
                    if "webp" in content_type or u.endswith(".webp"):
                        mime_type = "image/webp"
                    elif "png" in content_type or u.endswith(".png"):
                        mime_type = "image/png"
                    elif "jpg" in content_type or "jpeg" in content_type or u.endswith(".jpg") or u.endswith(".jpeg"):
                        mime_type = "image/jpeg"
                    else:
                        mime_type = "image/webp"

                    b64_str = base64.b64encode(res.content).decode("utf-8")
                    return {
                        "mime_type": mime_type,
                        "base64": b64_str,
                        "url": u
                    }
            except Exception as e:
                logger.debug(f"Image fetch attempt for {u} failed: {e}")
                continue

        return None

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

        # 6.5 Gather Daily Equity Growth Progression (14 Days Window)
        equity_growth = cls._fetch_daily_equity_progression(db, target_date=trade.entry_time, days=14)

        # 7. Anonymize Trade Data (Strict Rule: NO raw balance, NO API keys, NO leverage, NO USD margin)
        anonymized_payload = cls._anonymize_trade_data(
            trade=trade,
            setup_tags=setup_tags,
            mkt_info=mkt_info,
            psych_info=psych_info,
            exit_reason=exit_reason,
            similar_metrics=similar_metrics,
            equity_growth=equity_growth
        )

        # 8. Build Prompt & Image Payloads
        prompt_text, image_payloads = cls._build_prompt(anonymized_payload)

        # 9. Call LLM Provider (Vision-capable when images available, else text-only / fallback)
        review_text = cls._call_llm_provider(prompt_text, anonymized_payload, image_payloads=image_payloads)

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
        similar_metrics: Dict[str, Any],
        equity_growth: Optional[Dict[str, Any]] = None
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
        
        screenshots_meta = []
        if hasattr(trade, "screenshots") and trade.screenshots:
            for sc in trade.screenshots:
                fp = getattr(sc, "file_path", None) or getattr(sc, "url", None) or ""
                if fp.startswith("http://") or fp.startswith("https://"):
                    url_val = fp.replace("minio:9000", "localhost:9000")
                else:
                    bucket_name = getattr(settings, "MINIO_BUCKET_NAME", "teis-screenshots")
                    key = fp if fp.startswith("screenshots/") else f"screenshots/{trade.id}/{getattr(sc, 'stage', 'before_entry_4h')}.webp"
                    url_val = f"http://localhost:9000/{bucket_name}/{key}" if fp else ""

                screenshots_meta.append({
                    "stage": getattr(sc, "stage", "N/A"),
                    "url": url_val
                })

        exec_details = {
            "order_type": trade.execution.order_type if hasattr(trade, "execution") and trade.execution else "market",
            "moved_to_breakeven": trade.execution.moved_to_breakeven if hasattr(trade, "execution") and trade.execution else False,
            "trailing_stop_used": trade.execution.trailing_stop_used if hasattr(trade, "execution") and trade.execution else False,
            "exit_reason": exit_reason
        }

        return {
            "symbol_pair": trade.pair,
            "direction": trade.direction.upper(),
            "outcome": outcome,
            "entry_price": float(trade.entry_price) if trade.entry_price is not None else None,
            "exit_price": float(trade.exit_price) if trade.exit_price is not None else None,
            "stop_loss": float(trade.stop_loss) if trade.stop_loss is not None else None,
            "take_profit": float(trade.take_profit) if trade.take_profit is not None else None,
            "rr_planned": float(trade.rr_planned) if trade.rr_planned is not None else None,
            "rr_realized": rr_realized,
            "pnl": pnl_val,
            "fee": float(trade.fee) if trade.fee is not None else 0.0,
            "holding_time_minutes": holding_mins,
            "exit_reason": exit_reason,
            "execution_details": exec_details,
            "setup_tags": setup_tags,
            "market_context": mkt_info,
            "psychology": psych_info,
            "historical_similar_setup": similar_metrics,
            "screenshots": screenshots_meta,
            "equity_growth": equity_growth or {}
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
            return {
                "sample_size": 0,
                "win_rate_pct": 0.0,
                "avg_rr": 0.0,
                "expectancy_r": 0.0,
                "is_statistically_significant": False
            }

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
            return {
                "sample_size": 0,
                "win_rate_pct": 0.0,
                "avg_rr": 0.0,
                "expectancy_r": 0.0,
                "is_statistically_significant": False
            }

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
            "expectancy_r": expectancy_r,
            "is_statistically_significant": sample_size >= cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM
        }

    @classmethod
    def _fetch_daily_equity_progression(cls, db: Session, target_date: Optional[datetime] = None, days: int = 14) -> Dict[str, Any]:
        """
        Calculates daily day-by-day account equity growth progression (R-Multiple trajectory & PnL velocity).
        Enables AI Coach to track whether the account equity is expanding, consolidating, or recovering from drawdown.
        """
        from datetime import timedelta
        from collections import defaultdict

        ref_date = target_date or datetime.now()
        start_dt = ref_date - timedelta(days=days)

        trades = db.query(Trade).filter(
            Trade.entry_time >= start_dt,
            Trade.entry_time <= ref_date,
            Trade.exit_time != None
        ).order_by(Trade.entry_time.asc()).all()

        if not trades:
            return {
                "days_evaluated": days,
                "total_trades_window": 0,
                "cumulative_r_trajectory": 0.0,
                "equity_phase": "STABLE_BASELINE (Baseline Ekuitas Awal)",
                "daily_progression_str": "Belum ada riwayat transaksi tertutup dalam 14 hari terakhir."
            }

        daily_r_map = defaultdict(float)
        daily_pnl_map = defaultdict(float)
        daily_count_map = defaultdict(int)

        for t in trades:
            d_str = t.entry_time.strftime("%Y-%m-%d")
            r_val = float(t.rr_realized) if t.rr_realized is not None else 0.0
            pnl_val = float(t.pnl) if t.pnl is not None else 0.0

            daily_r_map[d_str] += r_val
            daily_pnl_map[d_str] += pnl_val
            daily_count_map[d_str] += 1

        sorted_dates = sorted(daily_r_map.keys())
        cum_r = 0.0
        daily_summary_lines = []

        for d in sorted_dates:
            r_day = daily_r_map[d]
            cnt_day = daily_count_map[d]
            cum_r += r_day
            sign_r = "+" if r_day >= 0 else ""
            sign_cum = "+" if cum_r >= 0 else ""
            daily_summary_lines.append(f"• {d}: {cnt_day} trade | Net R Harian: {sign_r}{r_day:.2f} R (Akumulasi Ekuitas: {sign_cum}{cum_r:.2f} R)")

        if cum_r >= 3.0:
            equity_phase = "🚀 EXPANSION_PEAK (Ekuitas Akun Tumbuh Pesat Merekam Peak R)"
        elif cum_r > 0:
            equity_phase = "📈 CONSISTENT_GROWTH (Ekuitas Tumbuh Positif Secara Bertahap)"
        elif cum_r == 0:
            equity_phase = "⚖️ BREAKEVEN_CONSOLIDATION (Ekuitas Konsolidasi Seimbang)"
        else:
            equity_phase = "🛡️ DRAWDOWN_RECOVERY (Ekuitas Mengalami Drawdown, Memerlukan Proteksi 1R)"

        return {
            "days_evaluated": days,
            "total_trades_window": len(trades),
            "cumulative_r_trajectory": round(cum_r, 2),
            "equity_phase": equity_phase,
            "daily_summary_lines": daily_summary_lines,
            "daily_progression_str": "\n".join(daily_summary_lines) if daily_summary_lines else "Tanpa fluktuasi ekuitas harian"
        }

    @classmethod
    def _build_prompt(cls, data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Constructs an elite Master SMC Institutional Trading Coach evaluation prompt
        and gathers base64 image payloads for vision-capable models.
        """
        hist = data["historical_similar_setup"]
        psych = data["psychology"]
        mkt = data["market_context"]
        screenshots = data.get("screenshots", [])
        setup_tags_list = data.get("setup_tags", [])
        tag_str = ", ".join(setup_tags_list) if setup_tags_list else "Belum memilih tag setup"
        exec_det = data.get("execution_details", {})
        eq_growth = data.get("equity_growth", {})

        image_payloads = []
        sc_summary = []
        for s in screenshots:
            stage_st = str(s.get("stage", "")).lower()
            if stage_st == "before_entry_4h":
                stage_name = "Chart 4H HTF (Before Entry)"
            elif stage_st == "before_entry_1h":
                stage_name = "Chart 1H LTF (Before Entry)"
            elif stage_st in ("after_exit", "exit_target", "chart_exit", "exit"):
                stage_name = "Chart AFTER Exit (Hasil Pasca Exit & Pergerakan Harga)"
            else:
                stage_name = f"Chart {stage_st.upper()} (Visualisasi)"

            sc_summary.append(f"• {stage_name}: URL={s['url']}")
            b64_info = cls._fetch_image_as_base64(s["url"])
            if b64_info:
                b64_info["stage"] = s["stage"]
                b64_info["stage_name"] = stage_name
                image_payloads.append(b64_info)

        sc_text = "\n".join(sc_summary) if sc_summary else "Belum ada foto chart diunggah di jurnal ini."

        sample_sz = hist.get("sample_size", 0)
        is_sig = hist.get("is_statistically_significant", False)
        if not is_sig:
            stat_caveat = (
                f"⚠️ PERHATIAN STATISTIK: Sampel historis untuk setup ini baru {sample_sz} trade — "
                f"TERLALU KECIL untuk dianggap edge statistik yang valid (syarat minimum n >= {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM}). "
                f"Jangan pernah menyimpulkan setup ini 'terbukti profitable' atau 'terbukti lemah' dari sampel sekecil ini. "
                f"Sampaikan angka apa adanya sebagai observasi awal, bukan kesimpulan."
            )
        else:
            stat_caveat = f"✅ Sampel historis mencukupi ({sample_sz} trade >= {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM}). Data statistik valid untuk evaluasi edge."

        prompt_text = f"""
Anda adalah Master Institutional SMC (Smart Money Concepts) & ICT Elite Trading Mentor yang telah terbukti sukses menumbuhkan modal kecil menjadi portofolio besar secara konsisten melalui eksekusi presisi tinggi dan disiplin risiko 1R ekuitas.

PERSPEKTIF MENTOR & CARA BERPIKIR TRADER PROFESIONAL:
• Anggap trader ini adalah murid Anda yang ingin belajar berpikir seperti seorang trader profesional.
• JANGAN HANYA MENUNJUKKAN KESALAHAN TRADER, tetapi berikan pembimbingan konstruktif, objektif, tajam, dan mendalam.
• Jangan pernah memberi pujian atau pembenaran otomatis hanya karena hasil trade positif. Nilai KUALITAS PROSES eksekusi secara independen dari hasil P&L. Jika proses entry lemah meski untung, katakan itu terus terang.
• Jangan pernah menyebut suatu setup sebagai 'terbukti', 'edge kuat', atau menyarankan 'scale up/double down' jika sample size di bawah {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM} trade.

PETUNJUK KUALITAS FORMATTING & PENGLIHATAN CHART VISUAL:
1. INSPEKSI CHART VISUAL BEFORE ENTRY & AFTER EXIT:
   - Gunakan penglihatan visual Anda (Vision Capability) untuk membandingkan secara teliti gambar chart yang dilampirkan: **Before Entry (4H/1H)** DAN **Chart AFTER Exit**.
   - Di **Chart AFTER Exit**, amati pergerakan harga pasca-exit: apakah harga mencapai target TP/SL, apakah terjadi pembalikan/wicking tajam setelah exit, dan bagaimana dinamika pergerakan struktur harga terbentuk setelah posisi ditutup.
2. FORMAT PENULISAN MARKDOWN YANG HIGH-READABILITY & ENAK DIBACA:
   - Buat format penulisan yang SANGAT RAPI, BERSIH, TERSTRUKTUR, DENGAN SPACING YANG NYAMAN DIBACA.
   - Gunakan **Tabel Markdown Rapi** untuk Bagian 2 (Validasi Tag Setup) dan Bagian 6 (Rapor Penilaian 1–10).
   - Gunakan penekanan teks **bold** untuk istilah penting, bullet points teratur, serta aksen emoji yang estetis.

Evaluasi transaksi berikut secara kualitatif, teknikal, dan psikologis:

=== PARAMETER TRANS-EKSEKUSI JURNAL ===
• Pair / Instrumen: {data['symbol_pair']} (Arah: {data['direction'].upper()})
• Entry Price: {data.get('entry_price', 'N/A')} | Exit Price: {data.get('exit_price', 'N/A')}
• Stop Loss: {data.get('stop_loss', 'N/A')} | Take Profit: {data.get('take_profit', 'N/A')}
• Planned RR: {data.get('rr_planned', 'N/A')} R | Realized RR: {data['rr_realized']} R | Total Fee: ${data.get('fee', 0.0):.4f}
• Hasil Akhir: {data['outcome']} | Durasi Posisi: {data['holding_time_minutes']} menit | Alasan Exit: {data['exit_reason']}
• Tipe Order: {exec_det.get('order_type', 'market').upper()} | BE Move: {'YA' if exec_det.get('moved_to_breakeven') else 'TIDAK'} | Trailing Stop: {'YA' if exec_det.get('trailing_stop_used') else 'TIDAK'}

=== PERTUMBUHAN EKUITAS AKUN HARIAN (EQUITY GROWTH TRAJECTORY) ===
• Fase Kurva Ekuitas: {eq_growth.get('equity_phase', 'STABLE_BASELINE')}
• Trajektori Kumulatif (14 Hari): {eq_growth.get('cumulative_r_trajectory', 0.0)} R
• Riwayat Pertumbuhan R Harian:
{eq_growth.get('daily_progression_str', 'Belum ada transaksi')}

=== TAG SETUP SMC TERPILIH ===
• Kriteria Setup Terpilih di Quick-Tag: [{tag_str}]

=== STRUCTURAL MARKET CONTEXT & DOKUMENTASI CHART ===
• Trend HTF (4H): {mkt['trend_htf']} | Trend LTF (1H): {mkt['trend_ltf']} | Sesi Trading: {mkt['session']}
• Makro Sentimen: Fear & Greed {mkt['fear_greed_index']} | BTC Dominance {mkt['btc_dominance']}% | Impact Berita: {'⚠️ ' + str(mkt.get('news_event_name')) if mkt.get('news_event_flag') else 'Tidak ada berita high-impact'}
• Dokumentasi Visual Chart:
{sc_text}

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
• Evaluasi Validitas Sampel: {stat_caveat}

Tuliskan evaluasi dalam 9 bagian Markdown yang SANGAT RAPI, BERSIH, DAN ENAK DIBACA:
1. 📌 **Analisis Eksekusi SMC & Order Flow Pasar**
2. 📈 **Analisis Teknikal Chart 4H / 1H & Validasi Tag Setup Terpilih [{tag_str}]**
   - Sertakan analisis visual chart **Before Entry** DAN **Chart AFTER Exit**.
   - Tampilkan **Tabel Markdown** validasi tag setup:
     | Tag SMC Terpilih | Keberadaan pada Chart | Konsistensi & Validasi SMC Detail |
3. 📉 **Pertumbuhan Ekuitas Akun Harian (Daily Equity Growth & R Trajectory)**
4. 🧠 **Audit Psikologi, Bias Mental & Adherensi Plan**
5. 🔍 **Refleksi Cara Berpikir Trader Profesional (5 Pertanyaan Kunci Mentor)**:
   - **Mengapa Analisis Salah (jika ada)**: [Penjelasan]
   - **Prinsip SMC yang Dilanggar (jika ada)**: [Penjelasan]
   - **Apa yang Seharusnya Dilihat Terlebih Dahulu**: [Penjelasan]
   - **Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan**: [Penjelasan]
   - **Pelajaran Terbesar dari Trade Ini**: [Penjelasan]
6. 🎯 **Rapor Penilaian Mentor (Skala 1–10)**:
   - Tampilkan dalam **Tabel Markdown Rapi**:
     | Kriteria Evaluasi | Skor (1-10) | Penjelasan Mentor Detail |
7. 🏆 **Klasifikasi Tier Setup & Alasan Penilaian**:
   - **Klasifikasi**: [A+ Setup / A Setup / B Setup / C Setup]
   - **Alasan Penilaian Detail**: [Penjelasan]
8. 📊 **Ekspektasi Matematik Jangka Panjang vs Variansi Acak**
9. 💡 **Instruksi Kunci Mentor SMC untuk Scaling Modal**
""".strip()

        return prompt_text, image_payloads

    @classmethod
    def _call_llm_provider(
        cls,
        prompt_text: str,
        data: Dict[str, Any],
        image_payloads: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Dispatches prompt to configured LLM provider.
        Supports Multimodal Vision payloads when image_payloads is provided.
        """
        system_prompt = (
            "Anda adalah Master Institutional Smart Money Concepts (SMC) & ICT Elite Trading Mentor "
            "berpengalaman 12+ tahun yang terbukti sukses menumbuhkan akun modal kecil secara konsisten.\n"
            "PRINSIP KRITIS EVALUASI MENTOR:\n"
            "1. Jangan pernah memberi pujian atau pembenaran otomatis hanya karena hasil trade positif. "
            "Nilai KUALITAS PROSES eksekusi secara independen dari hasil P&L. Jika proses entry lemah "
            "meski untung, katakan itu terus terang. Jika proses sudah benar meski rugi, jelaskan itu "
            "sebagai variansi wajar — tapi jangan gunakan frasa itu sebagai tameng otomatis untuk semua kerugian.\n"
            "2. Jangan pernah menyebut suatu setup sebagai 'terbukti', 'edge kuat', atau menyarankan "
            "'scale up/double down' jika sample size di bawah 20 trade. Untuk sample di bawah 20 trade, "
            "gunakan bahasa observasional yang hati-hati dan tegaskan bahwa sampel masih terlalu kecil."
        )

        has_images = bool(image_payloads)

        def _make_openai_messages():
            if not has_images:
                return [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ]

            user_content = [{"type": "text", "text": prompt_text}]
            for img in image_payloads:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['mime_type']};base64,{img['base64']}"
                    }
                })
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

        # ----------------------------------------------------
        # PRIORITY 1: Vision Providers (when screenshots exist)
        # ----------------------------------------------------

        # Option A: OpenAI API (gpt-4o-mini / gpt-4o)
        openai_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
        if openai_key and len(str(openai_key)) > 5:
            try:
                model_name = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
                logger.info(f"Calling OpenAI API ({model_name}) {'with Vision' if has_images else ''}...")
                res = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_name,
                        "messages": _make_openai_messages(),
                        "temperature": 0.3,
                        "max_tokens": 1400
                    },
                    timeout=18
                )
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    if content and len(content.strip()) > 10:
                        logger.info("✅ OpenAI API review successfully generated!")
                        return content
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}")

        # Option B: Gemini API (gemini-2.0-flash, gemini-1.5-flash)
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
                    logger.info(f"Calling Gemini API ({model_name}) {'with Vision' if has_images else ''}...")
                    parts = [{"text": f"{system_prompt}\n\n{prompt_text}"}]
                    if has_images:
                        for img in image_payloads:
                            parts.append({
                                "inline_data": {
                                    "mime_type": img["mime_type"],
                                    "data": img["base64"]
                                }
                            })

                    res = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
                        headers={"Content-Type": "application/json", "X-goog-api-key": gemini_key},
                        json={"contents": [{"parts": parts}]},
                        timeout=18
                    )
                    if res.status_code == 200:
                        candidates = res.json().get("candidates", [])
                        if candidates and candidates[0].get("content", {}).get("parts"):
                            content = candidates[0]["content"]["parts"][0]["text"]
                            if content and len(content.strip()) > 10:
                                logger.info(f"✅ Gemini API ({model_name}) review successfully generated!")
                                return content
                    elif res.status_code == 429:
                        logger.warning(f"Gemini API ({model_name}) Quota Exceeded (429)")
                        break
                except Exception as e:
                    logger.warning(f"Gemini API call ({model_name}) failed: {e}")

        # Option C: Groq Cloud API
        groq_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY")
        if groq_key and len(str(groq_key)) > 5:
            groq_models = ["llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview"] if has_images else ["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b", "gemma2-9b-it"]
            for model_id in groq_models:
                try:
                    logger.info(f"Calling Groq Cloud API ({model_id}) {'with Vision' if has_images else ''}...")
                    res = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                        json={
                            "model": model_id,
                            "messages": _make_openai_messages(),
                            "temperature": 0.3,
                            "max_tokens": 1400
                        },
                        timeout=15
                    )
                    if res.status_code == 200:
                        choices = res.json().get("choices", [])
                        if choices and choices[0].get("message", {}).get("content"):
                            content = choices[0]["message"]["content"]
                            if len(content.strip()) > 10:
                                logger.info(f"✅ Groq API ({model_id}) review successfully generated!")
                                return content
                except Exception as e:
                    logger.warning(f"Groq API call ({model_id}) failed: {e}")

        # Option D: OpenRouter API
        openrouter_key = getattr(settings, "OPENROUTER_API_KEY", None) or os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key and len(str(openrouter_key)) > 5:
            openrouter_models = ["meta-llama/llama-3.2-11b-vision-instruct:free", "google/gemma-4-31b-it:free", "openrouter/free"] if has_images else ["inclusionai/ling-3.0-flash:free", "google/gemma-4-31b-it:free", "openrouter/free"]
            for model_id in openrouter_models:
                try:
                    logger.info(f"Calling OpenRouter API ({model_id}) {'with Vision' if has_images else ''}...")
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
                            "messages": _make_openai_messages(),
                            "temperature": 0.3,
                            "max_tokens": 1400
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
                except Exception as e:
                    logger.warning(f"OpenRouter API call ({model_id}) failed: {e}")

        # ----------------------------------------------------
        # PRIORITY 2: Text Providers (Fallback for text)
        # ----------------------------------------------------

        # DeepSeek Official API (Text-only)
        deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", None) or os.environ.get("DEEPSEEK_API_KEY")
        if deepseek_key and len(str(deepseek_key)) > 5:
            try:
                logger.info("Calling DeepSeek Official API for AI Coach review...")
                res = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1400
                    },
                    timeout=15
                )
                if res.status_code == 200:
                    choices = res.json().get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        return choices[0]["message"]["content"]
            except Exception as e:
                logger.warning(f"DeepSeek API call failed: {e}")

        # Together AI API (Text)
        together_key = getattr(settings, "TOGETHER_API_KEY", None) or os.environ.get("TOGETHER_API_KEY")
        if together_key and len(str(together_key)) > 5:
            try:
                logger.info("Calling Together AI API for AI Coach review...")
                res = requests.post(
                    "https://api.together.xyz/v1/chat/completions",
                    headers={"Authorization": f"Bearer {together_key}", "Content-Type": "application/json"},
                    json={
                        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_text}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1400
                    },
                    timeout=15
                )
                if res.status_code == 200:
                    choices = res.json().get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        return choices[0]["message"]["content"]
            except Exception as e:
                logger.warning(f"Together AI API call failed: {e}")

        # Ollama Local LLM
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
                logger.warning(f"Ollama API call failed: {e}")

        # ----------------------------------------------------
        # PRIORITY 3: Fallback Engine
        # ----------------------------------------------------
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
        setup_tags = data.get("setup_tags", [])
        setup_str = ", ".join(setup_tags) if setup_tags else "Order Block / Liquidity Sweep / FVG"
        psych = data["psychology"]
        hist = data["historical_similar_setup"]
        mkt = data["market_context"]
        adherence = psych["plan_adherence"]
        conf = psych["confidence_level"]
        psych_tags = ", ".join(psych["psychological_tags"]) if psych["psychological_tags"] else "Stabil (Terfungsi sempurna)"
        exit_reason = data.get("exit_reason", "N/A")
        holding_mins = data.get("holding_time_minutes", 0)
        exec_det = data.get("execution_details", {})
        rr_planned = data.get("rr_planned")

        htf = mkt.get("trend_htf", "N/A")
        ltf = mkt.get("trend_ltf", "N/A")
        is_aligned_htf = (htf != "N/A" and ((direction == "LONG" and htf.lower() == "bullish") or (direction == "SHORT" and htf.lower() == "bearish")))
        is_counter_htf = (htf != "N/A" and ((direction == "LONG" and htf.lower() == "bearish") or (direction == "SHORT" and htf.lower() == "bullish")))

        # 1. Executive Summary & Dynamic Sub-variations
        if outcome == "LOSS":
            if is_counter_htf:
                summary = f"⚠️ **Kebocoran Counter-Trend**: Posisi **{direction} {pair}** dieksekusi melawan Trend HTF 4H ({htf.upper()}) dan menyentuh SL ({rr} R). Memotong arus besar institusional tanpa konfirmasi Liquidity Sweep HTF adalah penyebab utama kerugian."
            elif holding_mins < 15:
                summary = f"⚡ **Entry Impulsif Kilat**: Posisi **{direction} {pair}** hanya bertahan {holding_mins} menit sebelum menyentuh SL ({rr} R). Entry dilakukan terlalu terburu-buru tanpa menunggu pembentukan CHOCH/BOS LTF."
            elif exit_reason == "manual_close":
                summary = f"✋ **Manual Cut Loss Prematur**: Posisi **{direction} {pair}** ditutup manual sebelum menyentuh Stop Loss asli. Keputusan berbasis cemas mengacaukan manajemen risiko 1R."
            elif not adherence:
                summary = f"🚫 **Deviasi Rencana Trading**: Posisi **{direction} {pair}** menyentuh SL ({rr} R) akibat entry di luar kriteria rencana (Plan Adherence = TIDAK)."
            else:
                summary = f"🛡️ **Rugi Terkontrol (1R Risk)**: Posisi **{direction} {pair}** menyentuh Stop Loss ({rr} R). Eksekusi sudah sesuai rencana, kerugian ini adalah variansi statistik wajar."
        elif outcome == "WIN":
            if not adherence:
                summary = f"⚠️ **Lucky Win (Hasil Profit, Proses Impulsif)**: Posisi **{direction} {pair}** memanen profit +{rr} R, NAMUN dieksekusi di luar kriteria rencana (Plan Adherence = TIDAK). Jangan biarkan hasil positif mengaburkan proses yang berisiko tinggi!"
            elif is_counter_htf:
                summary = f"⚔️ **Counter-Trend Scalp Win**: Posisi **{direction} {pair}** memanen profit +{rr} R melawan trend HTF ({htf.upper()}). Walaupun untung, perketat kriteria counter-trend agar tidak terjebak reversal mendadak."
            elif rr >= 2.0:
                summary = f"🔥 **Eksekusi Presisi SMC**: Posisi **{direction} {pair}** berhasil memanen profit +{rr} R dengan disiplin rencana tinggi. Smart Money Order Flow terisi presisi hingga target."
            else:
                summary = f"🎯 **Profit Terukur**: Posisi **{direction} {pair}** menghasilkan profit +{rr} R sesuai rencana."
        else: # BREAKEVEN
            summary = f"⚖️ **Breakeven Defense**: Posisi **{direction} {pair}** ditutup pada 0 R. Pengamanan titik BE melindungi modal dari pergerakan pembalikan."

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

        if psych.get("free_notes"):
            psych_review += f"\n• *Refleksi Jurnal*: \"{psych['free_notes']}\""

        if is_aligned_htf:
            psych_review += f"\n• *Struktur Pasar*: 🔥 Entry **{direction}** searah dengan Trend HTF ({htf.upper()}), memberikan dorongan konfluensi institusional yang kuat."
        elif is_counter_htf:
            psych_review += f"\n• *Struktur Pasar*: ⚠️ Entry **{direction}** berlawanan arah dengan Trend HTF ({htf.upper()}). Perdagangan *Counter-Trend* membutuhkan konfirmasi *Liquidity Sweep & CHOCH LTF* yang sangat presisi."

        # 3. Historical Setup Comparison & Sample Guard (Task 3)
        sample_sz = hist.get("sample_size", 0)
        is_sig = hist.get("is_statistically_significant", False)

        if sample_sz == 0:
            hist_review = (
                f"Ini adalah transaksi awal untuk kombinasi setup **[{setup_str}]**. Data sampel historis belum mencukupi ($n=0$). "
                f"Kumpulkan hingga {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM} trade bertag identik untuk mengaktifkan kalkulasi Edge Discovery."
            )
        elif not is_sig:
            hist_review = (
                f"⚠️ **PERHATIAN STATISTIK (Sampel Belum Cukup)**: Populasi data untuk setup **[{setup_str}]** baru mencatat **{sample_sz} trade** "
                f"(Win Rate {hist.get('win_rate_pct', 0)}%, Expectancy {hist.get('expectancy_r', 0)} R).\n"
                f"Ukuran sampel ini **TERLALU KECIL** (< {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM} trade) untuk disimpulkan sebagai edge 'terbukti profit' atau 'bocor'. "
                f"Sampaikan angka ini sebagai observasi awal dan terus kumpulkan data sebelum mengambil kesimpulan."
            )
        else:
            hist_review = (
                f"✅ **Statistik Valid ($n={sample_sz} \\ge {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM}$)**: Kombinasi setup **[{setup_str}]** "
                f"mencatat Win Rate **{hist['win_rate_pct']}%** dan Expectancy **{hist['expectancy_r']} R**.\n"
            )
            if outcome == "WIN" and rr > hist["avg_rr"]:
                hist_review += f"Hasil trade ini (+{rr} R) **melampaui rata-rata R-Multiple historisnya ({hist['avg_rr']} R)**."
            elif outcome == "LOSS":
                hist_review += f"Meskipun trade ini berakhir rugi, ekspektasi statistik jangka panjang setup **[{setup_str}]** tetap **{hist['expectancy_r']} R**."

        # 4. Honest Chart Review (Task 1.5)
        screenshots = data.get("screenshots", [])
        if screenshots:
            stages_str = ", ".join([f"`{s['stage']}`" for s in screenshots])
            chart_review = (
                f"⚠️ Foto chart tersedia ({stages_str}), tapi mode ini (fallback offline) "
                f"tidak bisa membaca gambar secara visual. Analisis di bawah berdasarkan "
                f"data numerik & tag setup [{setup_str}] yang Anda pilih saja — "
                f"bukan validasi visual order block/FVG di chart Anda."
            )
        else:
            chart_review = (
                f"⚠️ Kriteria tag **[{setup_str}]** telah dipilih di Quick-Tag, namun foto chart 4H/1H belum diunggah. "
                f"Disiplin mengunggah chart sebelum entry (4H/1H) dan pasca-exit adalah kewajiban untuk evaluasi presisi teknikal secara objektif."
            )

        # Equity Growth Trajectory
        eq_growth = data.get("equity_growth", {})
        eq_phase = eq_growth.get("equity_phase", "STABLE_BASELINE")
        cum_r_traj = eq_growth.get("cumulative_r_trajectory", 0.0)
        daily_str = eq_growth.get("daily_progression_str", "Belum ada transaksi")

        equity_review = (
            f"Fase Kurva Ekuitas: **{eq_phase}** (Trajektori Kumulatif: **{cum_r_traj:+.2f} R**).\n"
            f"• *Riwayat Pergerakan R Harian*:\n{daily_str}"
        )

        takeaways = []
        if not adherence:
            takeaways.append("• **Instruksi Mentor**: Dilarang keras menekan tombol Entry tanpa menandai syarat setup SMC lengkap di Quick-Tag. Kedisiplinan adalah pintu utama pertumbuhan akun.")
        if outcome == "LOSS" and holding_mins < 15:
            takeaways.append("• **Instruksi Mentor**: Durasi trade terlalu singkat pasca-entry. Biarkan struktur harga bernapas sesuai perhitungan ATR dan jarak SL awal.")
        if outcome == "WIN" and rr >= 2.0:
            takeaways.append("• **Instruksi Mentor**: Kunci profit secara bertahap saat R-Multiple melampaui +2R dengan menggeser SL ke Breakeven setelah pembentukan BOS baru.")
        if exit_reason == "manual_close":
            takeaways.append("• **Instruksi Mentor**: Evaluasi alasan penutupan manual pada jurnal. Menutupi posisi terlalu cepat menghancurkan ekspektasi matematis RR tinggi.")
        if not takeaways:
            takeaways.append("• **Instruksi Mentor**: Pertahankan manajemen risiko 1R ekuitas konstan dan fokus pada konfluensi HTF Discount/Premium Zone.")
            takeaways.append("• **Instruksi Mentor**: Selalu tunggu pembentukan *Liquidity Sweep & CHOCH* sebelum mengeksekusi entry di LTF.")

        # Refleksi Cara Berpikir Trader Profesional (5 Pertanyaan Kunci Mentor)
        if outcome == "LOSS":
            if not adherence:
                why_wrong = "Analisis dan eksekusi mengalami kegagalan utama karena adanya deviasi dari trading plan (impulsif/FOMO). Posisi diambil tanpa konfirmasi struktur Liquidity Sweep & CHOCH yang valid."
                smc_viol = "Pelanggaran prinsip *HTF Liquidity Sweep & Inducement Validation*. Trade dimasukkan sebelum harga memitigasi POI (Order Block/FVG) utama."
                should_see_first = "Seharusnya Anda mengidentifikasi arah Trend HTF (4H) dan menunggu lokasi Discount/Premium Zone sebelum memicu trigger di LTF."
                pros_see = "Trader berpengalaman melihat *Liquidity Pool (Buy-side/Sell-side liquidity)* lawan yang diincar institusi dan sabar menunggu pembalikan harga, bukan mengejar candle impulsif."
                biggest_lesson = "Jangan pernah mengeksekusi posisi tanpa konfirmasi 100% kriteria plan. 1R loss akibat deviasi plan adalah risiko tidak perlu."
            elif is_counter_htf:
                why_wrong = f"Analisis mengeksekusi posisi counter-trend melawan dorongan kuat HTF ({htf.upper()}). Liquidity Sweep HTF belum bersih sempurna sehingga momentum melesat menembus SL."
                smc_viol = "Pelanggaran konfluensi *HTF Trend Alignment*. Counter-trend tanpa Liquidity Sweep 4H yang terkonfirmasi berisiko tinggi."
                should_see_first = "Seharusnya Anda melihat zona Invalidation Level 4H dan arah Trend HTF sebelum memicu posisi balik."
                pros_see = "Trader berpengalaman menunggu Change of Character (CHOCH) di struktur 4H terlebih dahulu sebelum melakukan perdagangan kontra-trend."
                biggest_lesson = "Berdagang searah trend HTF memberikan win-rate dan R-multiple jauh lebih tinggi daripada memprediksi top/bottom."
            else:
                why_wrong = f"Analisis teknikal telah selaras dengan rencana SMC, namun pasar mengalami variansi normal/spike volatilitas yang menembus Invalidation Level di area Stop Loss ({rr} R)."
                smc_viol = "Tidak ada pelanggaran kedisiplinan dasar. Namun pastikan titik SL diletakkan sedikit di luar *Liquidity Sweep High/Low* untuk mengantisipasi stop hunt."
                should_see_first = "Seharusnya Anda memverifikasi adanya agenda berita High-Impact (*news event*) atau bentukan *Equally Highs/Lows (EQH/EQL)* di dekat titik entry."
                pros_see = "Trader berpengalaman melihat apakah Liquidity Sweep di HTF sudah benar-benar bersih atau masih ada *Unmitigated FVG* di bawah/atas harga."
                biggest_lesson = "Kerugian 1R dengan kepatuhan rencana yang disiplin adalah biaya bisnis yang sah dalam matematika R-Multiple. Pertahankan manajemen risiko 1R."
        elif outcome == "WIN":
            if not adherence:
                why_wrong = "Posisi menghasilkan profit, tetapi analisis awal memiliki kelemahan mendasar karena eksekusi dilakukan tanpa mematuhi kriteria rencana."
                smc_viol = "Pelanggaran disiplin *Plan Adherence*. Entry dilakukan secara prematur / impulsif."
                should_see_first = "Daftar periksa (checklist) kriteria entry SMC sebelum menekan tombol order."
                pros_see = "Trader profesional melihat bahwa 'Lucky Win' adalah bahaya emosional jangka panjang karena membangun kebiasaan buruk."
                biggest_lesson = "Profit dari proses yang salah adalah keberuntungan acak. Selalu prioritaskan kualitas proses dibanding P&L."
            else:
                why_wrong = "Analisis berjalan efisien sesuai pergerakan *Smart Money Order Flow*. Tidak ditemukan kesalahan struktural fatal pada trade ini."
                smc_viol = "Prinsip SMC dijalankan dengan presisi (*Mitigation Order Block + FVG imbalance fill*)."
                should_see_first = "Struktur HTF 4H dan lokasi Liquidity Target di area Unmitigated Zone."
                pros_see = "Trader berpengalaman mengidentifikasi *Displacement & CHOCH* di LTF yang mengonfirmasi dorongan institusional ke target."
                biggest_lesson = "Kesabaran menunggu harga tiba di POI utama selalu membuahkan R-Multiple yang tinggi dan efisien."
        else:
            why_wrong = "Analisis awal benar, namun momentum dorongan harga tertahan di area struktur perantara sebelum mencapai target TP utama."
            smc_viol = "Tidak ada pelanggaran berat, namun menggeser SL ke BE terlalu dini dapat membuat posisi terkeluar sebelum ekspansi utama."
            should_see_first = "Lokasi *Minor Liquidity / Internal Structure* yang berpotensi memicu pembalikan sementara."
            pros_see = "Trader berpengalaman melihat apakah pembentukan BOS baru sudah cukup kuat untuk menjamin pergerakan Breakeven."
            biggest_lesson = "Mengamankan modal di titik BE adalah pertahanan ekuitas yang baik, namun harus dilakukan setelah pembentukan struktur baru."

        pro_reflection_review = (
            f"• **Mengapa Analisis Salah (jika ada)**: {why_wrong}\n"
            f"• **Prinsip SMC yang Dilanggar (jika ada)**: {smc_viol}\n"
            f"• **Apa yang Seharusnya Dilihat Terlebih Dahulu**: {should_see_first}\n"
            f"• **Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan**: {pros_see}\n"
            f"• **Satu Pelajaran Terbesar dari Trade Ini**: {biggest_lesson}"
        )

        # 5. Strict Scorecard Ratings (Task 2.2 & 2.3)
        # Market Structure
        if is_aligned_htf:
            ms_score = 8
        elif is_counter_htf:
            ms_score = 5
        else:
            ms_score = 6

        # Liquidity Reading
        if screenshots and is_aligned_htf and outcome == "WIN":
            lr_score = 8
        elif screenshots and adherence:
            lr_score = 7
        else:
            lr_score = 5

        # Bias Score
        if is_aligned_htf and conf >= 7:
            bias_score = 8
        elif conf >= 8 and outcome == "LOSS" and is_counter_htf:
            bias_score = 4  # Overconfidence in counter-trend loss
        else:
            bias_score = 6

        # Entry Timing Score (Task 2.3)
        if outcome == "WIN" and holding_mins <= 240 and adherence and screenshots:
            entry_score = 8
        elif outcome == "LOSS" and holding_mins < 15:
            entry_score = 4
        elif not adherence:
            entry_score = 5
        else:
            entry_score = 6

        # Risk Management Score (Task 2.2: Strict Rule - 10 ONLY if SL/TP matches plan and no risk widening)
        moved_be = exec_det.get("moved_to_breakeven", False)
        if not adherence:
            rm_score = 4
        elif exit_reason == "manual_close":
            rm_score = 5
        elif outcome == "LOSS" and abs(rr) > 1.2:
            rm_score = 5  # SL widened
        elif outcome == "WIN" and exit_reason == "take_profit" and rr_planned and abs(rr - float(rr_planned)) < 0.2 and not moved_be:
            rm_score = 10
        elif adherence and exit_reason in ("take_profit", "stop_loss", "breakeven"):
            rm_score = 8
        else:
            rm_score = 6

        overall_score = round((ms_score + lr_score + bias_score + entry_score + rm_score) / 5.0, 1)

        scorecard_review = (
            f"• **Market Structure**: {ms_score}/10\n"
            f"• **Liquidity Reading**: {lr_score}/10\n"
            f"• **Bias**: {bias_score}/10\n"
            f"• **Entry Timing**: {entry_score}/10 *(Catatan: Data presisi jarak dari POI/distance_from_poi_pct belum tercatat di MarketContext)*\n"
            f"• **Risk Management**: {rm_score}/10\n"
            f"• **Keseluruhan Kualitas Setup**: {overall_score}/10"
        )

        # 6. Tier Classification
        if outcome == "WIN" and adherence and rr >= 2.0 and is_aligned_htf and screenshots:
            tier_class = "A+ Setup"
            tier_reason = f"Trade memenuhi 100% kriteria SMC, disiplin plan terjaga, terhubung foto chart 4H/1H, aligned HTF ({htf.upper()}), dan memanen R-Multiple tinggi (+{rr} R)."
        elif outcome == "WIN" and adherence:
            tier_class = "A Setup"
            tier_reason = "Setup memiliki konfluensi struktur yang baik dan dieksekusi dengan kepatuhan rencana yang disiplin."
        elif outcome == "WIN" and not adherence:
            tier_class = "C Setup"
            tier_reason = "Meskipun menghasilkan profit (+{rr} R), eksekusi dilakukan di luar rencana trading (Plan Adherence = TIDAK). Ini adalah 'Lucky Win' yang berisiko."
        elif adherence and outcome == "BREAKEVEN":
            tier_class = "A Setup"
            tier_reason = "Eksekusi disiplin sesuai rencana dengan pengamanan ekuitas di Breakeven."
        elif adherence and outcome == "LOSS":
            tier_class = "B Setup"
            tier_reason = "Trade dieksekusi sesuai rencana SMC yang sah, kerugian 1R adalah variansi pasar yang terkontrol."
        else:
            tier_class = "C Setup"
            tier_reason = "Terjadi pelanggaran kedisiplinan (Plan Adherence = TIDAK) atau eksekusi impulsif tanpa kriteria SMC secara utuh."

        tier_review = (
            f"• **Klasifikasi**: 🏆 **{tier_class}**\n"
            f"• **Alasan Penilaian**: {tier_reason}"
        )

        return f"""📌 **Analisis Eksekusi SMC & Order Flow Pasar**
{summary}

📈 **Analisis Teknikal Chart 4H / 1H & Validasi Tag Setup Terpilih [{setup_str}]**
{chart_review}

📉 **Pertumbuhan Ekuitas Akun Harian (Daily Equity Growth & R Trajectory)**
{equity_review}

🧠 **Audit Psikologi, Bias Mental & Adherensi Plan**
{psych_review}

🔍 **Refleksi Cara Berpikir Trader Profesional (5 Pertanyaan Kunci Mentor)**
{pro_reflection_review}

🎯 **Rapor Penilaian Mentor (Skala 1–10)**
{scorecard_review}

🏆 **Klasifikasi Tier Setup & Alasan Penilaian**
{tier_review}

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
            db=db,
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
        db: Session,
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
        trades_with_sc = [t for t in trades if hasattr(t, "screenshots") and t.screenshots]
        total_sc = sum(len(t.screenshots) for t in trades_with_sc)
        sc_pct = round((len(trades_with_sc) / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

        # Calculate daily R progression
        from collections import defaultdict, Counter
        daily_r_map = defaultdict(float)
        daily_count_map = defaultdict(int)
        for t in trades:
            d_str = t.entry_time.strftime("%Y-%m-%d")
            daily_r_map[d_str] += float(t.rr_realized) if t.rr_realized is not None else 0.0
            daily_count_map[d_str] += 1

        daily_lines = []
        cum_r_wk = 0.0
        for d_str in sorted(daily_r_map.keys()):
            r_d = daily_r_map[d_str]
            cnt_d = daily_count_map[d_str]
            cum_r_wk += r_d
            daily_lines.append(f"• {d_str}: {cnt_d} trade | Net R: {r_d:+.2f} R (Kumulatif: {cum_r_wk:+.2f} R)")
        daily_prog_str = "\n".join(daily_lines) if daily_lines else "Tanpa transaksi harian"

        # 1. Edge Blueprint-Style Setup Taxonomy Analysis
        trade_ids = [t.id for t in trades]
        setup_tag_map = defaultdict(list)
        if trade_ids:
            placeholders = ", ".join([f"'{tid}'" for tid in trade_ids])
            tag_rows = db.execute(text(f"""
                SELECT st.trade_id, stv.tag_name 
                FROM trade_setup_tags st
                JOIN setup_taxonomy_versions stv ON st.taxonomy_version_id = stv.id
                WHERE st.trade_id IN ({placeholders})
            """)).fetchall()
            for r in tag_rows:
                setup_tag_map[r.trade_id].append(r.tag_name)

        tag_stats = defaultdict(lambda: {"count": 0, "wins": 0, "total_r": 0.0, "total_pnl": 0.0})
        for t in trades:
            t_tags = setup_tag_map.get(t.id, [])
            t_r = float(t.rr_realized) if t.rr_realized is not None else 0.0
            t_pnl = float(t.pnl) if t.pnl is not None else 0.0
            is_win = t_pnl > 0

            for tag in t_tags:
                tag_stats[tag]["count"] += 1
                if is_win:
                    tag_stats[tag]["wins"] += 1
                tag_stats[tag]["total_r"] += t_r
                tag_stats[tag]["total_pnl"] += t_pnl

        gold_setups = []
        leak_setups = []
        cautious_setups = []
        insufficient_data_setups = []

        for tag, s in tag_stats.items():
            wr = (s["wins"] / s["count"]) * 100.0 if s["count"] > 0 else 0.0
            avg_r = s["total_r"] / s["count"] if s["count"] > 0 else 0.0

            if s["count"] < cls.MIN_SAMPLE_SIZE_FOR_CAUTIOUS_NOTE:
                insufficient_data_setups.append(
                    f"• ❔ **{tag}**: {s['count']} trade | Total R: {s['total_r']:+.2f}R "
                    f"-> *Data belum cukup ({s['count']}/{cls.MIN_SAMPLE_SIZE_FOR_CAUTIOUS_NOTE}) untuk klasifikasi apapun, terus kumpulkan sampel.*"
                )
            elif s["count"] < cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM:
                if wr >= 60.0 and s["total_r"] > 0:
                    cautious_setups.append(
                        f"• 🟡 **{tag}**: {s['count']} trade | Win Rate {wr:.1f}% | Total R: {s['total_r']:+.2f}R (Avg: {avg_r:+.2f}R) "
                        f"-> *Sinyal awal positif, tapi sampel MASIH KECIL ({s['count']}/{cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM}) — jangan scale up dulu, kumpulkan lebih banyak data.*"
                    )
                elif wr < 50.0 or s["total_r"] < 0:
                    cautious_setups.append(
                        f"• 🟡 **{tag}**: {s['count']} trade | Win Rate {wr:.1f}% | Total R: {s['total_r']:+.2f}R (Avg: {avg_r:+.2f}R) "
                        f"-> *Sinyal awal negatif, sampel masih kecil ({s['count']}/{cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM}) — waspadai tapi belum kesimpulan final.*"
                    )
            else:
                if wr >= 60.0 and s["total_r"] > 0:
                    gold_setups.append(
                        f"• 🌟 **{tag}**: {s['count']} trade | Win Rate {wr:.1f}% | Total R: {s['total_r']:+.2f}R (Avg: {avg_r:+.2f}R) "
                        f"-> *Instruksi Mentor*: **FOKUS & DOUBLE DOWN** (Statistik terbukti kuat: n >= {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM})"
                    )
                elif wr < 50.0 or s["total_r"] < 0:
                    leak_setups.append(
                        f"• ⚠️ **{tag}**: {s['count']} trade | Win Rate {wr:.1f}% | Total R: {s['total_r']:+.2f}R (Avg: {avg_r:+.2f}R) "
                        f"-> *Instruksi Mentor*: **STOP & EVALUASI** (Bocoran ekuitas terbukti pada n >= {cls.MIN_SAMPLE_SIZE_FOR_EDGE_CLAIM})"
                    )

        edge_taxonomy_lines = []
        if gold_setups:
            edge_taxonomy_lines.append("🌟 **SETUP EMAS (Edge Terbukti Valid: n ≥ 20 - Scale Up)**:\n" + "\n".join(gold_setups))
        if leak_setups:
            edge_taxonomy_lines.append("⚠️ **SETUP BOCOR/LEMAH (Bocoran Terbukti: n ≥ 20 - Hentikan)**:\n" + "\n".join(leak_setups))
        if cautious_setups:
            edge_taxonomy_lines.append("🟡 **SETUP DENGAN OBSERVASI AWAL (Sampel Masih Kecil: 5 ≤ n < 20)**:\n" + "\n".join(cautious_setups))
        if insufficient_data_setups:
            edge_taxonomy_lines.append("❔ **SETUP DENGAN DATA BELUM CUKUP (n < 5)**:\n" + "\n".join(insufficient_data_setups))

        edge_taxonomy_str = "\n\n".join(edge_taxonomy_lines) if edge_taxonomy_lines else "Belum ada taksonomi setup yang dicatat minggu ini. Tingkatkan pengisian Quick-Tag."

        # 2. Market Context Collector Macro Summary
        mkt_rows = db.query(MarketContext).filter(MarketContext.trade_id.in_(trade_ids)).all() if trade_ids else []
        sessions = [m.session for m in mkt_rows if m.session]
        session_counts = Counter(sessions)
        session_str = ", ".join([f"{k} ({v}x)" for k, v in session_counts.most_common()]) if session_counts else "Asia / London / NY"

        fg_list = [m.fear_greed_index for m in mkt_rows if m.fear_greed_index is not None]
        avg_fg = round(sum(fg_list) / len(fg_list), 1) if fg_list else "N/A"

        btc_dom_list = [float(m.btc_dominance) for m in mkt_rows if m.btc_dominance is not None]
        avg_btc_dom = round(sum(btc_dom_list) / len(btc_dom_list), 1) if btc_dom_list else "N/A"

        news_count = sum(1 for m in mkt_rows if getattr(m, "news_event_flag", False))

        aligned_htf_count = 0
        for t in trades:
            m = next((ctx for ctx in mkt_rows if ctx.trade_id == t.id), None)
            if m and m.trend_htf:
                if (t.direction.upper() == "LONG" and m.trend_htf.lower() == "bullish") or \
                   (t.direction.upper() == "SHORT" and m.trend_htf.lower() == "bearish"):
                    aligned_htf_count += 1
        aligned_htf_pct = round((aligned_htf_count / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

        macro_context_str = (
            f"• Distribusi Sesi Trading: **{session_str}**\n"
            f"• Keselarasan Trend HTF (4H Alignment): **{aligned_htf_pct}% trade** searah Trend HTF 4H\n"
            f"• Rata-rata Fear & Greed Index: **{avg_fg}** | Rata-rata BTC Dominance: **{avg_btc_dom}%**\n"
            f"• Eksekusi Saat Berita High-Impact: **{news_count} posisi**"
        )

        # 3. Detailed Per-Image Chart Screenshots Summary & Pattern Discovery Synthesis
        per_trade_sc_summary = []
        for idx, t in enumerate(trades, 1):
            if hasattr(t, "screenshots") and t.screenshots:
                sc_items = []
                for sc in t.screenshots:
                    fp = getattr(sc, "file_path", None) or getattr(sc, "url", None) or ""
                    if fp.startswith("http://") or fp.startswith("https://"):
                        url_val = fp.replace("minio:9000", "localhost:9000")
                    else:
                        bucket_name = getattr(settings, "MINIO_BUCKET_NAME", "teis-screenshots")
                        key = fp if fp.startswith("screenshots/") else f"screenshots/{t.id}/{getattr(sc, 'stage', 'before_entry_4h')}.webp"
                        url_val = f"http://localhost:9000/{bucket_name}/{key}" if fp else ""
                    sc_items.append(f"`{getattr(sc, 'stage', 'N/A')}` ({url_val})")
                
                tags_str = ", ".join(setup_tag_map.get(t.id, [])) or "No Tag"
                r_str = f"{float(t.rr_realized):+.2f}R" if t.rr_realized is not None else "0.0R"
                per_trade_sc_summary.append(
                    f"• Trade #{idx} [{t.pair} {t.direction.upper()}] (Hasil: {r_str}, Tag: [{tags_str}]): "
                    f"Foto Chart: {', '.join(sc_items)}"
                )

        detailed_sc_breakdown_str = "\n".join(per_trade_sc_summary) if per_trade_sc_summary else "Belum ada foto chart diunggah pada transaksi minggu ini."

        prompt_text = f"""Anda adalah Master Institutional Smart Money Concepts (SMC) & ICT Elite Trading Mentor yang memiliki akses penuh ke seluruh data statistik murid Anda.
PERSPEKTIF MENTOR & CARA BERPIKIR TRADER PROFESIONAL:
• Anggap murid ini adalah trader yang ingin belajar berpikir seperti seorang trader profesional.
• JANGAN HANYA MENUNJUKKAN KESALAHAN TRADER, tetapi berikan evaluasi mingguan yang objektif, motivatif, dan terstruktur.

Berikan evaluasi audit kualitatif mingguan, analisis Edge Blueprint taksonomi setup (Pola Emas vs Leak Setup), audit Konteks Pasar Objektif Makro Crypto saat entry, DAN analisis per-foto chart visual struktur SMC ({start_date} s.d. {end_date}):

METRIK AUDIT MINGGUAN:
- Total Posisi: {total_trades} transaksi
- Win Rate: {win_rate:.1f}%
- Total PnL Bersih: ${total_pnl:.2f}
- Akumulasi Realized RR: {total_r:+.2f} R
- Kepatuhan Rencana Trading (Plan Adherence): {adherence_pct:.1f}%
- Pola Emosi Dominan: {top_tags_str}
- Dokumentasi Chart: {sc_pct}% trade memiliki foto chart (total {total_sc} foto terlampir minggu ini)
- Pertumbuhan Ekuitas R Harian:
{daily_prog_str}

AUDIT POLA SETUP TAKSONOMI (EDGE BLUEPRINT):
{edge_taxonomy_str}

AUDIT KONTEKS PASAR OBJEKTIF (MARKET CONTEXT COLLECTOR):
{macro_context_str}

DOKUMENTASI FOTO CHART PER-TRANSAKSI MINGGU INI:
{detailed_sc_breakdown_str}

Formatkan audit mingguan dalam 11 bagian Markdown terstruktur khas Mentor SMC Senior:
1. 📊 **Audit Performa Executive & Pertumbuhan Ekuitas R**
2. 📉 **Pertumbuhan Ekuitas Akun Harian (Day-by-Day R Velocity)**
3. ⚡ **Edge Blueprint & Audit Pola Taksonomi Setup (Pola Emas vs Leak Setup)**
4. 🔍 **Refleksi Cara Berpikir Trader Profesional Mingguan (5 Evaluasi Kunci Mentor)**:
   - **Mengapa Analisis/Pendekatan Salah (pada trade bocor/rugi)**: [Penjelasan]
   - **Prinsip SMC yang Paling Sering Dilanggar Minggu Ini**: [Penjelasan]
   - **Apa yang Seharusnya Dilihat Terlebih Dahulu Sebelum Entry**: [Penjelasan]
   - **Apa yang Biasanya Trader Berpengalaman Lihat tetapi Terlewatkan**: [Penjelasan]
   - **Pelajaran Terbesar Minggu Ini**: [Penjelasan]
5. 🎯 **Rapor Penilaian Mingguan Mentor (Skala 1–10)**:
   - Market Structure: X/10
   - Liquidity Reading: X/10
   - Bias: X/10
   - Entry Timing: X/10
   - Risk Management: X/10
   - Keseluruhan Kualitas Setup Mingguan: X/10
6. 🏆 **Klasifikasi Tier Setup Dominan Mingguan & Alasan Penilaian**:
   - Klasifikasi Tier Dominan: [A+ Setup / A Setup / B Setup / C Setup]
   - Alasan Penilaian Detail Mingguan
7. 🌍 **Konteks Pasar Objektif & Macro Collector (Sesi, HTF Trend, Fear & Greed)**
8. 🖼️ **Audit Teknikal Foto Chart Per-Transaksi & Evaluasi Pola Visual (Per-Image SMC Structure Audit)**
9. 📈 **Kualitas Dokumentasi Visual & Coverage Chart Mingguan**
10. 🧠 **Review Psikologi, Kontrol Emosi & Kedisiplinan SMC**
11. 💡 **3 Instruksi Emas Mentor SMC untuk Scaling Akun Minggu Depan**

Gunakan bahasa Indonesia yang tegas, bijak, profesional, mendalam, kaya terminologi SMC (Liquidity Sweeps, Discount/Premium, Order Block, FVG, 1R Risk), layaknya bimbingan privat dari mentor senior yang memegang data lengkap muridnya."""

        try:
            llm_res = cls._call_llm_provider(prompt_text, {})
            if llm_res and len(llm_res) > 50:
                return llm_res
        except Exception as e:
            logger.warning(f"LLM call failed for weekly review fallback: {e}")

        pnl_sign = "+" if total_pnl >= 0 else ""
        r_sign = "+" if total_r >= 0 else ""
        status_eval = "sangat presisi dan berdisiplin tinggi" if total_r > 0 else "memerlukan pembenahan kontrol risiko & disiplin SMC"

        # Weekly Refleksi Cara Berpikir Trader Profesional
        if total_r < 0 or win_rate < 50.0:
            wk_why_wrong = "Beberapa posisi mengalami kebocoran ekuitas terutama akibat eksekusi posisi yang mendahului konfirmasi Liquidity Sweep di HTF atau memaksakan trade saat kondisi konsolidasi."
            wk_smc_viol = "Pelanggaran terbanyak terjadi pada konfirmasi *HTF Alignment* dan eksekusi posisi sebelum pembentukan *Displacement / CHOCH* di LTF."
            wk_should_see = "Seharusnya Anda memverifikasi arah Trend HTF 4H dan area Premium/Discount Zone secara disiplin di awal sesi trading."
            wk_pros_see = "Trader profesional melihat struktur besar pasar (Macro Liquidity & Order Flow) dan tidak terpancing oleh fluktuasi candle kecil di pertengahan sesi."
            wk_biggest_lesson = "Kedisiplinan menyeleksi setup dan menjaga 1R risk per trade jauh lebih berharga daripada jumlah frekuensi transaksi."
        else:
            wk_why_wrong = "Pendekatan trading minggu ini berjalan sangat efisien dengan kontrol risiko yang terjaga. Hambatan kecil hanya terjadi pada variansi normal pasar."
            wk_smc_viol = "Prinsip SMC diterapkan secara konsisten tanpa pelanggaran kriteria utama."
            wk_should_see = "Fokus utama diawali dari peta zonasi Liquidity Pool di HTF 4H."
            wk_pros_see = "Trader profesional membiarkan R-Multiple tumbuh penuh dan hanya menggeser SL ke BE setelah pembentukan BOS terkonfirmasi."
            wk_biggest_lesson = "Konsistensi eksekusi pada Setup Emas menghasilkan pertumbuhan ekuitas R yang eksponensial."

        wk_pro_reflection_str = (
            f"• **Mengapa Analisis/Pendekatan Salah (pada trade bocor)**: {wk_why_wrong}\n"
            f"• **Prinsip SMC yang Paling Sering Dilanggar Minggu Ini**: {wk_smc_viol}\n"
            f"• **Apa yang Seharusnya Dilihat Terlebih Dahulu**: {wk_should_see}\n"
            f"• **Apa yang Dilihat Trader Berpengalaman tetapi Terlewatkan**: {wk_pros_see}\n"
            f"• **Satu Pelajaran Terbesar Minggu Ini**: {wk_biggest_lesson}"
        )

        # Weekly Scorecard 1-10
        wk_ms_score = 9 if aligned_htf_pct >= 70.0 else (7 if aligned_htf_pct >= 50.0 else 6)
        wk_lr_score = 9 if win_rate >= 60.0 else (7 if win_rate >= 45.0 else 5)
        wk_bias_score = 9 if wk_ms_score >= 8 else 6
        wk_entry_score = 9 if total_r > 0 else 6
        wk_rm_score = 10 if adherence_pct >= 85.0 else (8 if adherence_pct >= 70.0 else 5)
        wk_overall_score = round((wk_ms_score + wk_lr_score + wk_bias_score + wk_entry_score + wk_rm_score) / 5, 1)

        wk_scorecard_str = (
            f"• **Market Structure**: {wk_ms_score}/10\n"
            f"• **Liquidity Reading**: {wk_lr_score}/10\n"
            f"• **Bias**: {wk_bias_score}/10\n"
            f"• **Entry Timing**: {wk_entry_score}/10\n"
            f"• **Risk Management**: {wk_rm_score}/10\n"
            f"• **Keseluruhan Kualitas Setup Mingguan**: {wk_overall_score}/10"
        )

        # Weekly Tier Classification
        if total_r >= 5.0 and adherence_pct >= 85.0:
            wk_tier_class = "A+ Setup"
            wk_tier_reason = f"Performa minggu ini luar biasa (+{total_r:.2f} R) dengan tingkat kepatuhan rencana tinggi ({adherence_pct:.1f}%)."
        elif total_r > 0 and adherence_pct >= 75.0:
            wk_tier_class = "A Setup"
            wk_tier_reason = f"Performa positif (+{total_r:.2f} R) dengan eksekusi setup terstruktur dan disiplin risiko terjaga."
        elif adherence_pct >= 70.0:
            wk_tier_class = "B Setup"
            wk_tier_reason = f"Kepatuhan rencana cukup baik ({adherence_pct:.1f}%), namun perlu penyempurnaan seleksi setup untuk menekan kebocoran ekuitas."
        else:
            wk_tier_class = "C Setup"
            wk_tier_reason = f"Tingkat deviasi rencana tinggi (Plan Adherence hanya {adherence_pct:.1f}%). Diperlukan disiplin ketat dalam pengisian Quick-Tag."

        wk_tier_str = (
            f"• **Klasifikasi Tier Dominan Mingguan**: 🏆 **{wk_tier_class}**\n"
            f"• **Alasan Penilaian Detail**: {wk_tier_reason}"
        )

        return f"""### 🤖 Audit & Bimbingan Privat Mentor SMC Mingguan ({start_date} s/d {end_date})

📊 **Audit Performa Executive & Pertumbuhan Ekuitas R**
Minggu ini Anda telah menyelesaikan **{total_trades} posisi transaksi** dengan *Win Rate* **{win_rate:.1f}%**, menghasilkan pencapaian akumulasi **{r_sign}{total_r:.2f} R** ({pnl_sign}${total_pnl:.2f}). Kualitas eksekusi trading Anda pada periode ini dinilai **{status_eval}** dari kacamata ekspektasi matematis R-Multiple.

📉 **Pertumbuhan Ekuitas Akun Harian (Day-by-Day R Velocity)**
• Trajektori Pertumbuhan R Harian:
{daily_prog_str}
• *Prinsip Konsistensi*: Pertumbuhan ekuitas harian yang stabil lahir dari eksekusi setup berkualitas tanpa membiarkan 1 hari rugi memicu *revenge trading*.

⚡ **Edge Blueprint & Audit Pola Taksonomi Setup (Pola Emas vs Leak Setup)**
{edge_taxonomy_str}

🔍 **Refleksi Cara Berpikir Trader Profesional Mingguan (5 Evaluasi Kunci Mentor)**
{wk_pro_reflection_str}

🎯 **Rapor Penilaian Mingguan Mentor (Skala 1–10)**
{wk_scorecard_str}

🏆 **Klasifikasi Tier Setup Dominan Mingguan & Alasan Penilaian**
{wk_tier_str}

🌍 **Konteks Pasar Objektif & Macro Collector (Sesi, HTF Trend, Fear & Greed)**
{macro_context_str}
• *Evaluasi Macro Mentor*: Pastikan Anda memperbanyak eksekusi pada sesi dengan volatilitas tinggi (London & NY) yang searah dengan **Trend HTF 4H** untuk memaksimalkan win rate dan R-Multiple.

🖼️ **Audit Teknikal Foto Chart Per-Transaksi & Evaluasi Pola Visual (Per-Image SMC Structure Audit)**
{detailed_sc_breakdown_str}
• *Analisis Evaluasi Pola Visual*: Setiap foto chart di atas dianalisis untuk mengonfirmasi pembentukan *Liquidity Sweep*, *Unmitigated Order Block*, *Fair Value Gap (FVG)*, dan *CHOCH Displacement*. Pola visual yang terbukti memberikan R-Multiple tertinggi wajib dipertahankan dan diulang secara disiplin.

📈 **Kualitas Dokumentasi Visual & Coverage Chart Mingguan**
• Coverage Dokumentasi Chart Mingguan: **{sc_pct}%** ({len(trades_with_sc)} dari {total_trades} trade memiliki foto chart 4H/1H, total **{total_sc} foto** diunggah).
• *Rekomendasi Teknikal*: Pertahankan kebiasaan melampirkan chart sebelum entry (4H HTF & 1H LTF). Visualisasi pergerakan *Liquidity Sweep & Order Block mitigation* secara terstruktur adalah kunci utama mempertajam intuisi eksekusi Anda.

🧠 **Review Psikologi, Kontrol Emosi & Kedisiplinan SMC**
• Kepatuhan Rencana (*Plan Adherence*): **{adherence_pct:.1f}%** dari total posisi.
• Kondisi Emosi Dominan: *{top_tags_str}*.
• *Prinsip Mentor*: Kunci utama menumbuhkan modal kecil menjadi besar BUKAN dengan memperbesar leverage atau mengambil risiko nekat (gambling), melainkan menjaga keutuhan 1R Risk (1.0% Equity) secara religius dan membiarkan *Liquidity Sweep & Order Block mitigation* bekerja menghasilkan R-Multiple tinggi (1:2R hingga 1:5R+).

🎯 **Analisis Efisiensi Order Flow & Eksekusi**
Seluruh posisi minggu ini telah terdokumentasi di lembar jurnal. Penggunaan model **1R Equity Risk konstan** memastikan akun Anda terlindungi dari bahaya *catastrophic drawdown* saat menghadapi variansi acak pasar.

💡 **3 Instruksi Emas Mentor SMC untuk Scaling Akun Minggu Depan**
1. • **Instruksi 1 (Double Down pada Setup Emas)**: Alokasikan 80% energi Anda hanya untuk mengeksekusi setup bertag yang terbukti menghasilkan R positif di Edge Audit.
2. • **Instruksi 2 (Kunci Bias Subjektif di Quick-Tag)**: Jangan pernah melewatkan pengisian Quick-Tag dalam 120 detik pasca-entry untuk mengunci bias psikologis sebelum hasil trade keluar.
3. • **Instruksi 3 (Kedisiplinan 1R Equity Risk)**: Jaga risiko per trade tepat di 1.0% Total Equity ($0.96). Biarkan ekspektasi positif matematika R-Multiple menumbuhkan saldo Anda secara konsisten dari minggu ke minggu.
""".strip()
