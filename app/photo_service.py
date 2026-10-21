import os
import uuid
from PIL import Image, ImageOps
from app.database import db_session

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fotograflar")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_material_photo(malzeme_id: int, file_bytes: bytes, filename: str) -> dict:
    """
    Kamera veya formdan gelen fotografi EXIF yonunu duzelterek kaydeder,
    1280px standart ve 300px kucuk resim (thumbnail) uretir.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    file_id = f"{malzeme_id}_{uuid.uuid4().hex[:8]}"
    main_filename = f"{file_id}{ext}"
    thumb_filename = f"{file_id}_thumb{ext}"

    main_path = os.path.join(UPLOAD_DIR, main_filename)
    thumb_path = os.path.join(UPLOAD_DIR, thumb_filename)

    import io
    img = Image.open(io.BytesIO(file_bytes))
    
    # EXIF rotasyonunu duzelt
    img = ImageOps.exif_transpose(img)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Ana gorsel - max 1280px
    img_main = img.copy()
    img_main.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
    img_main.save(main_path, quality=85, optimize=True)

    # Kucuk resim - max 300px
    img_thumb = img.copy()
    img_thumb.thumbnail((300, 300), Image.Resampling.LANCZOS)
    img_thumb.save(thumb_path, quality=80, optimize=True)

    rel_main = f"/fotograflar/{main_filename}"
    rel_thumb = f"/fotograflar/{thumb_filename}"

    with db_session() as conn:
        # Yeni yuklenen fotografi en guncel ana fotograf yap
        conn.execute("UPDATE fotograflar SET ana_fotograf = 0 WHERE malzeme_id = ?", (malzeme_id,))

        cur = conn.execute("""
            INSERT INTO fotograflar (malzeme_id, dosya_yolu, kucuk_resim_yolu, ana_fotograf)
            VALUES (?, ?, ?, 1)
        """, (malzeme_id, rel_main, rel_thumb))
        photo_id = cur.lastrowid

    return {
        "id": photo_id,
        "dosya_yolu": rel_main,
        "kucuk_resim_yolu": rel_thumb,
        "ana_fotograf": 1
    }

def delete_material_photo(photo_id: int):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM fotograflar WHERE id = ?", (photo_id,)).fetchone()
        if not row:
            return False
        
        main_file = os.path.join(UPLOAD_DIR, os.path.basename(row["dosya_yolu"]))
        thumb_file = os.path.join(UPLOAD_DIR, os.path.basename(row["kucuk_resim_yolu"])) if row.get("kucuk_resim_yolu") else None
        
        if os.path.exists(main_file):
            try: os.remove(main_file)
            except: pass
        if thumb_file and os.path.exists(thumb_file):
            try: os.remove(thumb_file)
            except: pass

        conn.execute("DELETE FROM fotograflar WHERE id = ?", (photo_id,))
        
        # Eger silinen fotograf ana fotograf idiyse, kalan en son fotografi ana fotograf yap
        if row["ana_fotograf"] == 1:
            conn.execute("""
                UPDATE fotograflar SET ana_fotograf = 1
                WHERE id = (SELECT id FROM fotograflar WHERE malzeme_id = ? ORDER BY id DESC LIMIT 1)
            """, (row["malzeme_id"],))
            
        return True
