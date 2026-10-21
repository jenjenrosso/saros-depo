import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "saros_depo.db")

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db_session() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS lokasyonlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,
            ad TEXT NOT NULL,
            excel_sayfa TEXT
        );

        CREATE TABLE IF NOT EXISTS malzemeler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qr_kod TEXT UNIQUE NOT NULL,
            lokasyon_id INTEGER NOT NULL,
            ad TEXT NOT NULL,
            marka TEXT,
            tip_aciklama TEXT,
            miktar REAL DEFAULT 0,
            birim TEXT DEFAULT 'adet',
            miktar_bilinmiyor INTEGER DEFAULT 0,
            raf_no TEXT,
            giris_tarihi TEXT,
            cikis_tarihi TEXT,
            raf_omru TEXT,
            yp_kodu TEXT,
            sap_durumu TEXT,
            yp_sm_dv TEXT,
            duran_varlik_turu TEXT,
            uretici_kodu TEXT,
            kaynak TEXT DEFAULT 'excel',
            excel_satir_no INTEGER,
            olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
            guncelleme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lokasyon_id) REFERENCES lokasyonlar(id)
        );

        CREATE TABLE IF NOT EXISTS stok_hareketleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            malzeme_id INTEGER NOT NULL,
            tip TEXT NOT NULL, -- 'GIRIS', 'CIKIS', 'DUZELTME'
            miktar REAL NOT NULL,
            onceki_miktar REAL NOT NULL,
            sonraki_miktar REAL NOT NULL,
            teslim_alan TEXT,
            teslim_eden TEXT,
            sebep TEXT,
            kullanici TEXT DEFAULT 'Saha',
            tarih TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (malzeme_id) REFERENCES malzemeler(id)
        );

        CREATE TABLE IF NOT EXISTS fotograflar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            malzeme_id INTEGER NOT NULL,
            dosya_yolu TEXT NOT NULL,
            kucuk_resim_yolu TEXT,
            ana_fotograf INTEGER DEFAULT 1,
            yuklenme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (malzeme_id) REFERENCES malzemeler(id)
        );

        CREATE INDEX IF NOT EXISTS idx_malzemeler_qr ON malzemeler(qr_kod);
        CREATE INDEX IF NOT EXISTS idx_malzemeler_lokasyon ON malzemeler(lokasyon_id);
        CREATE INDEX IF NOT EXISTS idx_hareketler_malzeme ON stok_hareketleri(malzeme_id);
        CREATE INDEX IF NOT EXISTS idx_fotograflar_malzeme ON fotograflar(malzeme_id);
        """)

if __name__ == "__main__":
    init_db()
    print("Veritabani basariyla olusturuldu:", DB_PATH)
