import os
import io
import qrcode
from qrcode.image.pil import PilImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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

def generate_label_pdf(items: list) -> bytes:
    """
    Malzeme listesini A4 sayfasina 3 sutun x 8 satir (24 etiket/sayfa) etiket seklinde dizer.
    Her etikette: QR kod, Malzeme Adi, Lokasyon, Raf No, QR Kodu metni yer alir.
    Turkce karakterleri eksiksiz basar (ı, İ, ş, Ş, ğ, Ğ, ç, Ç, ö, Ö, ü, Ü).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4 # 595.27 x 841.89 points

    cols = 3
    rows = 8
    margin_x = 20
    margin_y = 25
    label_w = (width - 2 * margin_x) / cols
    label_h = (height - 2 * margin_y) / rows

    for idx, item in enumerate(items):
        page_idx = idx % (cols * rows)
        if idx > 0 and page_idx == 0:
            c.showPage()

        c_idx = page_idx % cols
        r_idx = page_idx // cols

        x = margin_x + c_idx * label_w
        y = height - margin_y - (r_idx + 1) * label_h

        # Etiket cercevesi
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(0.5)
        c.roundRect(x + 2, y + 2, label_w - 4, label_h - 4, 4, stroke=1, fill=0)

        # QR Kod uret
        qr_bytes = generate_qr_image(item.get("qr_kod", ""), box_size=4, border=1)
        qr_img = io.BytesIO(qr_bytes)
        from reportlab.lib.utils import ImageReader
        img_reader = ImageReader(qr_img)

        # QR Ciz (sol taraf)
        qr_size = label_h - 14
        c.drawImage(img_reader, x + 6, y + 7, width=qr_size, height=qr_size)

        # Bilgi Metinleri (sag taraf)
        text_x = x + qr_size + 10
        max_text_w = label_w - qr_size - 14
        
        # Malzeme Adi (Bold)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD_NAME, 8)
        raw_ad = item.get("ad") or ""
        ad = truncate_text(c, raw_ad, FONT_BOLD_NAME, 8, max_text_w)
        c.drawString(text_x, y + label_h - 18, ad)

        # Marka
        c.setFont(FONT_NAME, 7)
        c.setFillColor(colors.HexColor("#334155"))
        raw_marka = f"Marka: {item.get('marka') or '-'}"
        marka = truncate_text(c, raw_marka, FONT_NAME, 7, max_text_w)
        c.drawString(text_x, y + label_h - 30, marka)

        # Lokasyon
        lok_val = item.get("lokasyon_adi") or item.get("lokasyon_kod") or "-"
        raw_lok = f"Lok: {lok_val}"
        lok = truncate_text(c, raw_lok, FONT_NAME, 7, max_text_w)
        c.drawString(text_x, y + label_h - 42, lok)

        # Raf No
        raw_raf = f"Raf: {item.get('raf_no') or '-'}"
        raf = truncate_text(c, raw_raf, FONT_NAME, 7, max_text_w)
        c.drawString(text_x, y + label_h - 54, raf)

        # QR Kod Metni
        c.setFont(FONT_BOLD_NAME, 7.5)
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.drawString(text_x, y + 10, item.get("qr_kod", ""))

    c.save()
    return buf.getvalue()
