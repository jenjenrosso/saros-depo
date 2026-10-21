import os
import io
import qrcode
from qrcode.image.pil import PilImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# Turkce karakter destekli TrueType font tanimlama
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
REGULAR_FONT_PATH = os.path.join(FONTS_DIR, "arial.ttf")
BOLD_FONT_PATH = os.path.join(FONTS_DIR, "arialbd.ttf")

FONT_NAME = "Helvetica"
FONT_BOLD_NAME = "Helvetica-Bold"

try:
    if os.path.exists(REGULAR_FONT_PATH) and os.path.exists(BOLD_FONT_PATH):
        pdfmetrics.registerFont(TTFont("SarosFont", REGULAR_FONT_PATH))
        pdfmetrics.registerFont(TTFont("SarosFont-Bold", BOLD_FONT_PATH))
        FONT_NAME = "SarosFont"
        FONT_BOLD_NAME = "SarosFont-Bold"
    elif os.path.exists(r"C:\Windows\Fonts\arial.ttf"):
        pdfmetrics.registerFont(TTFont("SarosFont", r"C:\Windows\Fonts\arial.ttf"))
        pdfmetrics.registerFont(TTFont("SarosFont-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
        FONT_NAME = "SarosFont"
        FONT_BOLD_NAME = "SarosFont-Bold"
except Exception as e:
    print("Font yükleme hatası, Helvetica'ya dönülüyor:", e)

def generate_qr_image(content: str, box_size: int = 10, border: int = 2) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def truncate_text(canvas_obj, text: str, font_name: str, font_size: float, max_width: float) -> str:
    """Metin genisligi max_width'i asiyorsa sonuna '...' koyarak kisaltir."""
    if not text:
        return ""
    if canvas_obj.stringWidth(text, font_name, font_size) <= max_width:
        return text
    while len(text) > 1 and canvas_obj.stringWidth(text + "...", font_name, font_size) > max_width:
        text = text[:-1]
    return text + "..."

def wrap_text(canvas_obj, text: str, font_name: str, font_size: float, max_width: float, max_lines: int = 2) -> list:
    """
    Ekipman adinin kesilmemesi icin kelime bazli satir bolme yapar (2 satira kadar).
    """
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        if canvas_obj.stringWidth(test_line, font_name, font_size) <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(truncate_text(canvas_obj, word, font_name, font_size, max_width))
                current_line = []
            if len(lines) >= max_lines:
                break

    if current_line and len(lines) < max_lines:
        lines.append(" ".join(current_line))
    elif current_line and len(lines) == max_lines:
        last = lines[-1] + " " + " ".join(current_line)
        lines[-1] = truncate_text(canvas_obj, last, font_name, font_size, max_width)

    return lines

def generate_label_pdf(items: list) -> bytes:
    """
    Malzeme listesini A4 sayfasina 3 sutun x 8 satir (24 etiket/sayfa) etiket seklinde dizer.
    - Dikdortgen sinir cizgileri kaldirildi (baskida temiz gorunum).
    - Ekipman adlari kesilmeden tam cikar (gerektiginde 2 satira sarar).
    - Etiketler arasi bosluk %5 azaltilarak icerik genisletildi.
    - Turkce karakterleri eksiksiz basar (ı, İ, ş, Ş, ğ, Ğ, ç, Ç, ö, Ö, ü, Ü).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4 # 595.27 x 841.89 points

    cols = 3
    rows = 8
    margin_x = 18
    margin_y = 22
    slot_w = (width - 2 * margin_x) / cols
    slot_h = (height - 2 * margin_y) / rows

    # Etiketler arasi bosluk %5 azaltildi (scale 0.90 yerine 0.95)
    scale = 0.95
    box_w = slot_w * scale
    box_h = slot_h * scale
    pad_x = (slot_w - box_w) / 2.0
    pad_y = (slot_h - box_h) / 2.0

    for idx, item in enumerate(items):
        page_idx = idx % (cols * rows)
        if idx > 0 and page_idx == 0:
            c.showPage()

        c_idx = page_idx % cols
        r_idx = page_idx // cols

        slot_x = margin_x + c_idx * slot_w
        slot_y = height - margin_y - (r_idx + 1) * slot_h

        box_x = slot_x + pad_x
        box_y = slot_y + pad_y

        # NOT: Kullanici talebiyle dikdortgen cerceve cizgisi kaldirildi (temiz yapiskanli etiket baskisi)

        # QR Kod uret
        qr_bytes = generate_qr_image(item.get("qr_kod", ""), box_size=4, border=1)
        qr_img = io.BytesIO(qr_bytes)
        img_reader = ImageReader(qr_img)

        # QR Ciz (sol taraf)
        qr_size = box_h - 10
        qr_x = box_x + 3
        qr_y = box_y + 5
        c.drawImage(img_reader, qr_x, qr_y, width=qr_size, height=qr_size)

        # Bilgi Metinleri (sag taraf)
        text_x = qr_x + qr_size + 7
        max_text_w = box_w - qr_size - 10

        # Malzeme Adi (Bold - Kesilmeden tam cikar, uzunsa 2 satira sarar)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD_NAME, 7.5)
        raw_ad = (item.get("ad") or "").strip()
        ad_lines = wrap_text(c, raw_ad, FONT_BOLD_NAME, 7.5, max_text_w, max_lines=2)

        if len(ad_lines) >= 2:
            c.drawString(text_x, box_y + box_h - 13, ad_lines[0])
            c.drawString(text_x, box_y + box_h - 22, ad_lines[1])
            curr_y = box_y + box_h - 33
        elif len(ad_lines) == 1:
            c.drawString(text_x, box_y + box_h - 15, ad_lines[0])
            curr_y = box_y + box_h - 28
        else:
            curr_y = box_y + box_h - 25

        # Marka (6.5pt)
        c.setFont(FONT_NAME, 6.5)
        c.setFillColor(colors.HexColor("#334155"))
        raw_marka = f"Marka: {item.get('marka') or '-'}"
        marka = truncate_text(c, raw_marka, FONT_NAME, 6.5, max_text_w)
        c.drawString(text_x, curr_y, marka)

        # Lokasyon (6.5pt)
        curr_y -= 10
        lok_val = item.get("lokasyon_adi") or item.get("lokasyon_kod") or "-"
        raw_lok = f"Lok: {lok_val}"
        lok = truncate_text(c, raw_lok, FONT_NAME, 6.5, max_text_w)
        c.drawString(text_x, curr_y, lok)

        # Raf No (6.5pt)
        curr_y -= 10
        raw_raf = f"Raf: {item.get('raf_no') or '-'}"
        raf = truncate_text(c, raw_raf, FONT_NAME, 6.5, max_text_w)
        c.drawString(text_x, curr_y, raf)

        # QR Kod Metni (Bold - 7pt)
        c.setFont(FONT_BOLD_NAME, 7.5)
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.drawString(text_x, box_y + 6, item.get("qr_kod", ""))

    c.save()
    return buf.getvalue()
