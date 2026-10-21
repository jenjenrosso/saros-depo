import os
from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "icons")
os.makedirs(ICONS_DIR, exist_ok=True)

def create_icon(size, filename):
    img = Image.new("RGBA", (size, size), color=(37, 99, 235, 255))
    draw = ImageDraw.Draw(img)
    
    # Kutu ciz
    margin = size * 0.15
    draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=size * 0.12, fill=(30, 58, 138, 255))
    
    # Ic beyaz kareler (QR benzeri sembol)
    inner_m = size * 0.28
    draw.rectangle([inner_m, inner_m, size - inner_m, size - inner_m], fill=(255, 255, 255, 255))
    center_m = size * 0.38
    draw.rectangle([center_m, center_m, size - center_m, size - center_m], fill=(37, 99, 235, 255))

    img.save(os.path.join(ICONS_DIR, filename))
    print(f"Olusturuldu: {filename} ({size}x{size})")

if __name__ == "__main__":
    create_icon(192, "icon-192.png")
    create_icon(512, "icon-512.png")
