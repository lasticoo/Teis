import os
import sys
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from features_data import FEATURES

# Define colors
COLOR_DARK_PURPLE = (30, 16, 54)      # #1e1036
COLOR_INDIGO_PURPLE = (80, 50, 120)   # #503278
COLOR_TEAL = (0, 150, 136)            # #009688
COLOR_NEUTRAL_DARK = (44, 44, 44)     # #2c2c2c
COLOR_NEUTRAL_LIGHT = (245, 245, 248) # #f5f5f8
COLOR_WHITE = (255, 255, 255)
COLOR_GREY = (128, 128, 128)
COLOR_LIGHT_TEAL = (224, 242, 241)    # For callout boxes

def clean_pdf_text(text):
    if not isinstance(text, str):
        return text
    replacements = {
        "\u2014": "-", # em dash
        "\u2013": "-", # en dash
        "\u2019": "'", # right single quotation mark
        "\u201c": '"', # left double quotation mark
        "\u201d": '"', # right double quotation mark
        "\u2192": "->", # right arrow
        "\u2714": "[v]", # heavy check mark
        "\u2713": "[v]", # check mark
        "\u2717": "[x]", # ballot x
        "\u274c": "[x]", # cross mark
        "\u26a0": "[!]", # warning sign
        "\u2197": "^", # up-right arrow
        "\u2198": "v", # down-right arrow
        "\u2265": ">=", # greater than or equal
        "\u2264": "<=", # less than or equal
        "\u2212": "-", # minus sign
        "\u2022": "-", # bullet
        "\u00b1": "+/-", # plus-minus
        "\u2010": "-", # hyphen
        "\uf04e": "[v]",
        "\uf00c": "[v]",
        "\uf00d": "[x]",
        "\u25b2": "^",
        "\u25bc": "v",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # encode to latin-1 and back to ignore other characters if any
    return text.encode("latin-1", "replace").decode("latin-1")

class TEIS_Spec_PDF(FPDF):
    def __init__(self):
        super().__init__(orientation="portrait", unit="mm", format="A4")
        self.set_margins(15, 20, 15)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        if self.page_no() > 2:
            self.set_font("helvetica", "I", 8)
            self.set_text_color(*COLOR_GREY)
            # Use XPos and YPos to avoid deprecation warnings
            self.cell(100, 10, "Trading Edge Intelligence System (TEIS) - Spesifikasi Pengembangan", 0, 0, "L")
            self.cell(80, 10, f"Halaman {self.page_no()}", 0, 0, "R")
            self.ln(10)
            self.set_draw_color(*COLOR_INDIGO_PURPLE)
            self.set_line_width(0.2)
            self.line(15, 18, 195, 18)
            self.ln(2)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.set_text_color(*COLOR_GREY)
            self.cell(0, 10, "Dokumen Spesifikasi Teknis TEIS v1.4 - Rahasia & Terbatas", 0, 0, "C")

    def draw_cover_page(self):
        self.add_page()
        self.set_fill_color(*COLOR_DARK_PURPLE)
        self.rect(0, 0, 210, 297, "F")
        
        self.ln(30)
        self.set_font("helvetica", "B", 28)
        self.set_text_color(*COLOR_WHITE)
        self.multi_cell(0, 12, "TRADING EDGE\nINTELLIGENCE SYSTEM", align="C")
        self.ln(10)
        
        self.set_draw_color(*COLOR_TEAL)
        self.set_line_width(1.5)
        self.line(40, self.get_y(), 170, self.get_y())
        self.ln(15)
        
        self.set_font("helvetica", "B", 14)
        self.set_text_color(*COLOR_TEAL)
        self.multi_cell(0, 8, "DOKUMEN SPESIFIKASI PENGEMBANGAN APLIKASI\nBERBASIS FITUR (FDD)", align="C")
        self.ln(20)
        
        self.set_font("helvetica", "", 10)
        self.set_text_color(220, 220, 220)
        desc = ("Analisis komprehensif, spesifikasi fungsional, skema database, "
                "API endpoint, dan petunjuk implementasi Agentic AI untuk "
                "pengembangan modular sistem Trading Edge Intelligence System (TEIS).")
        self.set_x(25)
        self.multi_cell(160, 6, desc, align="C")
        self.ln(30)
        
        self.set_fill_color(45, 30, 75)
        self.set_y(155)
        self.rect(25, 155, 160, 55, "F")
        self.set_y(160)
        
        self.set_text_color(*COLOR_WHITE)
        self.set_font("helvetica", "B", 10)
        self.set_x(28)
        self.cell(154, 6, "DIPERSIAPKAN SEBAGAI PERAN:", 0, 0, "L")
        self.ln(6)
        self.set_font("helvetica", "", 9)
        self.set_text_color(200, 200, 200)
        self.set_x(28)
        self.cell(154, 5, "- Senior Business Analyst & Product Manager (Ruang Lingkup & Alur Bisnis)", 0, 0, "L")
        self.ln(5)
        self.set_x(28)
        self.cell(154, 5, "- System Analyst & Software Architect (Skema DB, API, Struktur Modular)", 0, 0, "L")
        self.ln(5)
        self.set_x(28)
        self.cell(154, 5, "- Senior Software Engineer (Best Practices, Validasi, Penanganan Error)", 0, 0, "L")
        self.ln(7)
        
        self.set_text_color(*COLOR_TEAL)
        self.set_font("helvetica", "B", 9)
        self.set_x(28)
        self.cell(154, 5, "Versi Dokumen: 1.4 (Sesuai Audit Mockup & Skema Database)", 0, 0, "L")
        self.ln(5)
        self.set_font("helvetica", "", 9)
        self.set_text_color(200, 200, 200)
        self.set_x(28)
        self.cell(154, 5, "Tanggal Pembuatan: 20 Juli 2026", 0, 0, "L")

    def draw_toc_page(self, features):
        self.add_page()
        self.set_font("helvetica", "B", 18)
        self.set_text_color(*COLOR_DARK_PURPLE)
        self.cell(0, 10, "DAFTAR ISI & STRUKTUR DOKUMEN", 0, 0, "L")
        self.ln(10)
        
        self.set_draw_color(*COLOR_TEAL)
        self.set_line_width(0.8)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(5)
        
        self.set_font("helvetica", "", 10)
        self.set_text_color(*COLOR_NEUTRAL_DARK)
        
        intro_text = (
            "Dokumen ini memuat spesifikasi teknis lengkap untuk Trading Edge Intelligence System (TEIS). "
            "Setiap fitur didokumentasikan secara mandiri dengan alur sebagai berikut:\n"
            "   Analisis Fitur -> Ringkasan & Alur Bisnis -> Dokumentasi Teknis -> Prompt AI -> Catatan Implementasi\n\n"
            "Berikut adalah daftar fitur yang tercakup dalam dokumen spesifikasi ini:"
        )
        self.multi_cell(0, 5, clean_pdf_text(intro_text))
        self.ln(5)
        
        self.set_font("helvetica", "B", 10)
        self.cell(0, 6, "Tahap 1 - Analisis Dokumentasi & Prinsip Desain", 0, 0, "L")
        self.ln(6)
        self.cell(0, 6, "Tahap 2 - Identifikasi Seluruh Fitur", 0, 0, "L")
        self.ln(8)
        
        self.cell(0, 6, "Tahap 3 - Spesifikasi Fitur Secara Berurutan:", 0, 0, "L")
        self.ln(6)
        self.set_font("helvetica", "", 9)
        for idx, feat in enumerate(features):
            name = clean_pdf_text(feat["name"])
            self.cell(0, 5, f"   Fitur {idx+1}: {name}", 0, 0, "L")
            self.ln(5)
        
        self.ln(5)
        self.set_fill_color(*COLOR_NEUTRAL_LIGHT)
        self.rect(15, self.get_y(), 180, 25, "F")
        self.set_y(self.get_y() + 2)
        self.set_font("helvetica", "B", 9)
        self.set_text_color(*COLOR_INDIGO_PURPLE)
        self.set_x(18)
        self.cell(174, 5, "TEKNOLOGI STACK SISTEM:", 0, 0, "L")
        self.ln(5)
        self.set_font("helvetica", "", 8.5)
        self.set_text_color(*COLOR_NEUTRAL_DARK)
        self.set_x(18)
        self.cell(174, 4, "- Backend: Python 3.12 (FastAPI untuk REST API, Celery + Redis untuk Background Job & Scheduler)", 0, 0, "L")
        self.ln(4)
        self.set_x(18)
        self.cell(174, 4, "- Database & ORM: MySQL 8 (InnoDB, UTF8MB4), SQLAlchemy 2.x, Migrasi Alembic", 0, 0, "L")
        self.ln(4)
        self.set_x(18)
        self.cell(174, 4, "- Frontend & Storage: React (Vite, Responsive Web App), MinIO (S3-Compatible Object Storage)", 0, 0, "L")

    def write_heading1(self, text):
        self.ln(6)
        self.set_font("helvetica", "B", 14)
        self.set_text_color(*COLOR_DARK_PURPLE)
        self.multi_cell(0, 8, clean_pdf_text(text))
        self.set_draw_color(*COLOR_TEAL)
        self.set_line_width(0.5)
        self.line(15, self.get_y(), 100, self.get_y())
        self.ln(4)

    def write_heading2(self, text):
        self.ln(4)
        self.set_font("helvetica", "B", 11)
        self.set_text_color(*COLOR_INDIGO_PURPLE)
        self.multi_cell(0, 6, clean_pdf_text(text))
        self.ln(2)

    def write_heading3(self, text):
        self.ln(2)
        self.set_font("helvetica", "B", 9.5)
        self.set_text_color(*COLOR_NEUTRAL_DARK)
        self.multi_cell(0, 5, clean_pdf_text(text))
        self.ln(1)

    def write_paragraph(self, text):
        self.set_font("helvetica", "", 9)
        self.set_text_color(*COLOR_NEUTRAL_DARK)
        self.multi_cell(0, 4.5, clean_pdf_text(text))
        self.ln(2)

    def write_bullet(self, text, indent=5):
        self.set_font("helvetica", "", 9)
        self.set_text_color(*COLOR_NEUTRAL_DARK)
        self.set_x(15 + indent)
        self.multi_cell(0, 4.5, f"- {clean_pdf_text(text)}")
        self.ln(1.5)

    def write_callout(self, text, type_str="NOTE"):
        self.ln(2)
        self.set_fill_color(*COLOR_NEUTRAL_LIGHT)
        self.set_draw_color(*COLOR_TEAL)
        self.set_line_width(0.6)
        self.set_font("helvetica", "I", 8.5)
        self.multi_cell(180, 4.5, f"[{type_str}] {clean_pdf_text(text)}", border="L", fill=True)
        self.ln(3)

    def write_code_block(self, code_text):
        self.ln(2)
        self.set_fill_color(*COLOR_NEUTRAL_LIGHT)
        self.set_font("courier", "", 7.5)
        self.set_text_color(50, 50, 60)
        self.multi_cell(180, 4, clean_pdf_text(code_text), border=1, fill=True)
        self.ln(3)
        self.set_font("helvetica", "", 9)
        self.set_text_color(*COLOR_NEUTRAL_DARK)

def generate_markdown(features):
    md_content = "# DOKUMEN SPESIFIKASI PENGEMBANGAN APLIKASI - TEIS (TRADING EDGE INTELLIGENCE SYSTEM)\n\n"
    md_content += "## Tahap 1 - Analisis Dokumentasi & Prinsip Desain\n\n"
    md_content += (
        "Trading Edge Intelligence System (TEIS) dirancang sebagai sistem pencatatan (journaling) "
        "dan analitik personal untuk trading manual futures crypto di Binance. Sistem ini bersifat "
        "closed-loop, di mana hasil analitik akan membantu trader memvalidasi edge kualitatif mereka, "
        "dan data trade baru akan terus menyempurnakan statistik tersebut.\n\n"
        "### Prinsip Desain Utama:\n"
        "1. **Non-intrusive capture**: Trader harus dapat mengisi Quick-Tag dalam waktu <15 detik.\n"
        "2. **Immutable snapshot**: Data subjektif (setup, psikologi) akan dikunci permanen setelah "
        "window koreksi 60 detik berlalu.\n"
        "3. **Separation of concerns**: Sistem terpisah total dari bot trading lainnya.\n"
        "4. **Insight, bukan sinyal**: Menampilkan statistik historis-deskriptif, bukan instruksi transaksi otomatis.\n"
        "5. **Satuan R**: Mengukur performa murni dalam satuan R-multiple untuk memisahkan keputusan sizing dari kualitas setup.\n\n"
        "### Bagian yang Membutuhkan Klarifikasi (Needs Clarification) & Rekomendasi:\n"
        "- *Kriteria Trend HTF/LTF*: Slope EMA50 naik dihitung dari minimal 3 candlestick terakhir.\n"
        "- *Uji Robustness*: Menggeser target profit dan stop loss sebesar +/- 5% dan +/- 10% untuk memverifikasi expectancy.\n"
        "- *FDR Target*: Dikonfigurasi default 5% (tingkat kepercayaan 95%).\n\n"
    )
    md_content += "## Tahap 2 - Identifikasi Seluruh Fitur\n\n"
    md_content += "Sistem dibagi menjadi 15 fitur utama yang akan dikembangkan secara bertahap:\n"
    for idx, feat in enumerate(features):
        md_content += f"{idx+1}. **{feat['name']}**\n"
    md_content += "\n---\n\n"

    md_content += "## Tahap 3 - Spesifikasi Fitur Secara Berurutan\n\n"
    
    for idx, feat in enumerate(features):
        md_content += f"# Fitur {idx+1} - {feat['name']}\n\n"
        
        md_content += "## A. Ringkasan Fitur\n\n"
        md_content += f"{feat['summary']}\n\n"
        
        md_content += "## B. Dokumentasi Lengkap Fitur\n\n"
        
        d = feat["doc"]
        md_content += f"### 1. Nama Fitur\n{d['nama_fitur']}\n\n"
        md_content += f"### 2. Tujuan\n{d['tujuan']}\n\n"
        md_content += f"### 3. Deskripsi\n{d['deskripsi']}\n\n"
        md_content += f"### 4. Business Flow\n{d['business_flow']}\n\n"
        md_content += f"### 5. Aktor\n{d['aktor']}\n\n"
        md_content += f"### 6. Hak Akses\n{d['hak_akses']}\n\n"
        
        md_content += "### 7. Input\n"
        for inp in d["input_fields"]:
            md_content += f"- **{inp['name']}** ({inp['type']}): Validasi: {inp['validation']}. Wajib: {'Ya' if inp['required'] else 'Tidak'}.\n"
        md_content += "\n"
        
        md_content += f"### 8. Output\n{d['output']}\n\n"
        md_content += f"### 9. Business Rules\n{d['business_rules']}\n\n"
        md_content += f"### 10. Validasi\n{d['validasi']}\n\n"
        md_content += f"### 11. Edge Cases\n{d['edge_cases']}\n\n"
        md_content += f"### 12. Error Handling\n{d['error_handling']}\n\n"
        md_content += f"### 13. Database\n{d['database']}\n\n"
        md_content += f"### 14. API\n{d['api']}\n\n"
        md_content += f"### 15. UI/UX\n{d['ui_ux']}\n\n"
        md_content += f"### 16. Security\n{d['security']}\n\n"
        md_content += f"### 17. Dependencies\n{d['dependencies']}\n\n"
        md_content += f"### 18. Acceptance Criteria\n{d['acceptance_criteria']}\n\n"
        
        md_content += "## C. Prompt Agentic AI Untuk Implementasi Fitur Ini\n\n"
        md_content += "```text\n" + feat["prompt"] + "\n```\n\n"
        
        md_content += "## D. Catatan Implementasi\n\n"
        md_content += f"{feat['notes']}\n\n"
        md_content += "---\n\n"
        
    return md_content

def build_pdf_from_features(features):
    pdf = TEIS_Spec_PDF()
    pdf.draw_cover_page()
    pdf.draw_toc_page(features)
    
    # Page 3: General Document Analysis
    pdf.add_page()
    pdf.write_heading1("TAHAP 1 - ANALISIS DOKUMENTASI & PRINSIP DESAIN")
    pdf.write_paragraph(
        "Trading Edge Intelligence System (TEIS) dirancang sebagai sistem pencatatan (journaling) "
        "dan analitik personal untuk trading manual futures crypto di Binance. Sistem ini bersifat "
        "closed-loop, di mana hasil analitik akan membantu trader memvalidasi edge kualitatif mereka, "
        "dan data trade baru akan terus menyempurnakan statistik tersebut."
    )
    
    pdf.write_heading2("Prinsip Desain Utama:")
    pdf.write_bullet("Non-intrusive capture: Trader harus dapat mengisi Quick-Tag dalam waktu <15 detik.")
    pdf.write_bullet("Immutable snapshot: Data subjektif (setup, psikologi) akan dikunci permanen setelah window koreksi 60 detik berlalu.")
    pdf.write_bullet("Separation of concerns: Sistem terpisah total dari bot trading lainnya.")
    pdf.write_bullet("Insight, bukan sinyal: Menampilkan statistik historis-deskriptif, bukan instruksi transaksi otomatis.")
    pdf.write_bullet("Satuan R: Mengukur performa murni dalam satuan R-multiple untuk memisahkan keputusan sizing dari kualitas setup.")
    
    pdf.write_heading2("Pemisahan Data Objektif vs Subjektif:")
    pdf.write_paragraph(
        "Sistem secara tegas memisahkan data objektif (data pasar nyata dari Binance API seperti entry/exit price, fee, klines) "
        "dari data subjektif (penilaian kualitatif trader seperti setup yang digunakan, bias arah mental, dan status emosi). "
        "Hal ini penting untuk menghindari hindsight bias (kecenderungan merasa sudah mengetahui hasil akhir sebelum trade selesai)."
    )
    
    pdf.write_heading2("Bagian yang Membutuhkan Klarifikasi (Needs Clarification) & Rekomendasi:")
    pdf.write_paragraph(
        "1. Kriteria Trend HTF/LTF: EMA50 di HTF (4 Jam) dan LTF (1 Jam). Rekomendasi: Gunakan slope kemiringan EMA50 dari 3 candlestick terakhir."
    )
    pdf.write_paragraph(
        "2. Uji Robustness Edge: Rekomendasi: Geser target profit dan stop loss sebesar +/- 5% dan +/- 10% untuk memverifikasi kestabilan expectancy."
    )
    pdf.write_paragraph(
        "3. FDR Target Rate: Target FDR 5-10%. Rekomendasi: Jadikan target FDR sebagai parameter konfigurasi default di angka 5%."
    )
    
    pdf.ln(5)
    pdf.write_heading1("TAHAP 2 - IDENTIFIKASI SELURUH FITUR")
    pdf.write_paragraph("Berdasarkan dokumen perencanaan dan audit desain teknis, diidentifikasi 15 fitur pengembangan berikut:")
    for idx, feat in enumerate(features):
        pdf.write_bullet(f"Fitur {idx+1}: {feat['name']}")
        
    # Phase 3: Features
    for idx, feat in enumerate(features):
        pdf.add_page()
        pdf.write_heading1(f"FITUR {idx+1} - {feat['name'].upper()}")
        
        pdf.write_heading2("A. Ringkasan Fitur")
        pdf.write_paragraph(feat["summary"])
        
        pdf.write_heading2("B. Dokumentasi Lengkap Fitur")
        d = feat["doc"]
        
        pdf.write_heading3("1. Nama Fitur")
        pdf.write_paragraph(d["nama_fitur"])
        
        pdf.write_heading3("2. Tujuan")
        pdf.write_paragraph(d["tujuan"])
        
        pdf.write_heading3("3. Deskripsi")
        pdf.write_paragraph(d["deskripsi"])
        
        pdf.write_heading3("4. Business Flow")
        pdf.write_paragraph(d["business_flow"])
        
        pdf.write_heading3("5. Aktor")
        pdf.write_paragraph(d["aktor"])
        
        pdf.write_heading3("6. Hak Akses")
        pdf.write_paragraph(d["hak_akses"])
        
        pdf.write_heading3("7. Input")
        for inp in d["input_fields"]:
            req_str = "Wajib" if inp["required"] else "Opsional"
            pdf.write_bullet(f"{inp['name']} ({inp['type']}) - Validasi: {inp['validation']} ({req_str})")
        pdf.ln(2)
        
        pdf.write_heading3("8. Output")
        pdf.write_paragraph(d["output"])
        
        pdf.write_heading3("9. Business Rules")
        pdf.write_paragraph(d["business_rules"])
        
        pdf.write_heading3("10. Validasi")
        pdf.write_paragraph(d["validasi"])
        
        pdf.write_heading3("11. Edge Cases")
        pdf.write_paragraph(d["edge_cases"])
        
        pdf.write_heading3("12. Error Handling")
        pdf.write_paragraph(d["error_handling"])
        
        pdf.write_heading3("13. Database")
        pdf.write_paragraph(d["database"])
        
        pdf.write_heading3("14. API")
        pdf.write_paragraph(d["api"])
        
        pdf.write_heading3("15. UI/UX")
        pdf.write_paragraph(d["ui_ux"])
        
        pdf.write_heading3("16. Security")
        pdf.write_paragraph(d["security"])
        
        pdf.write_heading3("17. Dependencies")
        pdf.write_paragraph(d["dependencies"])
        
        pdf.write_heading3("18. Acceptance Criteria")
        pdf.write_paragraph(d["acceptance_criteria"])
        
        # New page for the Prompt to keep layout clean
        pdf.add_page()
        pdf.write_heading2("C. Prompt Agentic AI Untuk Implementasi Fitur")
        pdf.write_callout("Salin prompt di bawah ini untuk digunakan oleh AI Coding Agent Anda.", "INSTRUKSI AI")
        pdf.write_code_block(feat["prompt"])
        
        pdf.write_heading2("D. Catatan Implementasi")
        pdf.write_paragraph(feat["notes"])
        
    return pdf

if __name__ == "__main__":
    print("Mulai membuat dokumen Markdown...")
    md_content = generate_markdown(FEATURES)
    md_path = "C:\\Users\\lastico\\.gemini\\antigravity-ide\\scratch\\teis\\spesifikasi_teis.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Dokumen Markdown berhasil ditulis ke {md_path}")
    
    print("Mulai membuat dokumen PDF...")
    pdf = build_pdf_from_features(FEATURES)
    pdf_path = "C:\\Users\\lastico\\.gemini\\antigravity-ide\\scratch\\teis\\Spesifikasi_Pengembangan_TEIS.pdf"
    pdf.output(pdf_path)
    print(f"Dokumen PDF berhasil ditulis ke {pdf_path}")
