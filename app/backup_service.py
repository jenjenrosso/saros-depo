import os
import zipfile
import io
import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def create_backup_zip() -> tuple[bytes, str]:
    """
    Veritabani ve yuklenen fotograflarin tamamini tek bir ZIP dosyasinda paketler.
    """
    buf = io.BytesIO()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Saros_Depo_Yedek_{timestamp}.zip"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # SQLite dosyasi
        db_path = os.path.join(DATA_DIR, "saros_depo.db")
        if os.path.exists(db_path):
            zf.write(db_path, arcname="saros_depo.db")

        # Fotograflar klasoru
        photos_dir = os.path.join(DATA_DIR, "fotograflar")
        if os.path.exists(photos_dir):
            for root, dirs, files in os.walk(photos_dir):
                for f in files:
                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, DATA_DIR)
                    zf.write(file_path, arcname=rel_path)

    buf.seek(0)
    return buf.getvalue(), filename
