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

def generate_label_pdf(items: list) -> bytes:
    """
    Malzeme listesini A4 sayfasina 3 sutun x 8 satir (24 etiket/sayfa) etiket seklinde dizer.
    Mevcut yerlerinde %10 kucultulmus (daha guvenli etiket payi ile) olarak cizer.
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
    slot_w = (width - 2 * margin_x) / cols
    slot_h = (height - 2 * margin_y) / rows

    # %10 Kucultme olcegi: etiket kutusu ve icerigi yuvasinda %10 daha kompakt (scale = 0.90)
    scale = 0.90
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

        # Mevcut yerinde %10 kucultulmus ve ortalanmis etiket koordinatlari
        box_x = slot_x + pad_x
        box_y = slot_y + pad_y

        # Etiket cercevesi
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(0.5)
        c.roundRect(box_x, box_y, box_w, box_h, 3.5, stroke=1, fill=0)

        # QR Kod uret
        qr_bytes = generate_qr_image(item.get("qr_kod", ""), box_size=4, border=1)
        qr_img = io.BytesIO(qr_bytes)
        img_reader = ImageReader(qr_img)

        # QR Ciz (sol taraf - orantili kucultuldu)
        qr_size = box_h - 12
        qr_x = box_x + 6
        qr_y = box_y + 6
        c.drawImage(img_reader, qr_x, qr_y, width=qr_size, height=qr_size)

        # Bilgi Metinleri (sag taraf)
        text_x = qr_x + qr_size + 8
        max_text_w = box_w - qr_size - 14
        
        # Malzeme Adi (Bold - 7.5pt)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD_NAME, 7.5)
        raw_ad = item.get("ad") or ""
        ad = truncate_text(c, raw_ad, FONT_BOLD_NAME, 7.5, max_text_w)
        c.drawString(text_x, box_y + box_h - 16, ad)

        # Marka (6.5pt)
        c.setFont(FONT_NAME, 6.5)
        c.setFillColor(colors.HexColor("#334155"))
        raw_marka = f"Marka: {item.get('marka') or '-'}"
        marka = truncate_text(c, raw_marka, FONT_NAME, 6.5, max_text_w)
        c.drawString(text_x, box_y + box_h - 27, marka)

        # Lokasyon (6.5pt)
        lok_val = item.get("lokasyon_adi") or item.get("lokasyon_kod") or "-"
        raw_lok = f"Lok: {lok_val}"
        lok = truncate_text(c, raw_lok, FONT_NAME, 6.5, max_text_w)
        c.drawString(text_x, box_y + box_h - 38, lok)

        # Raf No (6.5pt)
        raw_raf = f"Raf: {item.get('raf_no') or '-'}"
        raf = truncate_text(c, raw_raf, FONT_NAME, 6.5, max_text_w)
        c.drawString(text_x, box_y + box_h - 49, raf)

        # QR Kod Metni (Bold - 7pt)
        c.setFont(FONT_BOLD_NAME, 7)
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.drawString(text_x, box_y + 8, item.get("qr_kod", ""))

    c.save()
    return buf.getvalue()
