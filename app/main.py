import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List

from app.database import db_session, init_db, hash_password
from app.photo_service import save_material_photo, delete_material_photo, UPLOAD_DIR
from app.qr_service import generate_qr_image, generate_label_pdf
from app.excel_export import export_db_to_excel
from app.backup_service import create_backup_zip

app = FastAPI(title="Saros Depo QR Stok Takip Sistemi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Statik dosyalari ve fotograflari sun
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/fotograflar", StaticFiles(directory=UPLOAD_DIR), name="fotograflar")

@app.on_event("startup")
def on_startup():
    init_db()

# ---- PYDANTIC SEMALARI ----
class MalzemeGuncelleme(BaseModel):
    ad: str
    marka: Optional[str] = None
    tip_aciklama: Optional[str] = None
    lokasyon_id: int
    raf_no: Optional[str] = None
    birim: Optional[str] = "adet"
    raf_omru: Optional[str] = None
    yp_kodu: Optional[str] = None
    sap_durumu: Optional[str] = None
    yp_sm_dv: Optional[str] = None
    duran_varlik_turu: Optional[str] = None
    uretici_kodu: Optional[str] = None

class StokHareketiGiris(BaseModel):
    tip: str # 'GIRIS' veya 'CIKIS'
    miktar: float
    teslim_alan: Optional[str] = None
    teslim_eden: Optional[str] = None
    sebep: Optional[str] = None
    kullanici: Optional[str] = "Saha"

class LoginRequest(BaseModel):
    kullanici_adi: str
    sifre: str

class SifreDegistirRequest(BaseModel):
    kullanici_adi: str
    eski_sifre: str
    yeni_sifre: str

# ---- API ENDPOINT'LERI ----

@app.post("/api/oturum")
@app.post("/api/auth/login")
def login(req: LoginRequest):
    code = req.kullanici_adi.strip()
    norm_code = code.replace("i", "İ").replace("ı", "I").upper()
    with db_session() as conn:
        user = conn.execute("""
            SELECT id, kullanici_adi, ad_soyad, sifre_hash, aktif
            FROM kullanicilar
            WHERE kullanici_adi = ? OR kullanici_adi = ? OR UPPER(kullanici_adi) = ?
        """, (code, norm_code, code.upper())).fetchone()

        if not user or not user["aktif"]:
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı!")

        entered_hash = hash_password(req.sifre)
        if entered_hash != user["sifre_hash"]:
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı!")

        return {
            "status": "ok",
            "kullanici": {
                "id": user["id"],
                "kullanici_adi": user["kullanici_adi"],
                "ad_soyad": user["ad_soyad"]
            }
        }

@app.post("/api/sifre")
@app.post("/api/auth/sifre-degistir")
def sifre_degistir(req: SifreDegistirRequest):
    code = req.kullanici_adi.strip()
    norm_code = code.replace("i", "İ").replace("ı", "I").upper()
    if not req.yeni_sifre or len(req.yeni_sifre.strip()) < 3:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 3 karakter olmalıdır.")

    with db_session() as conn:
        user = conn.execute("""
            SELECT id, kullanici_adi, ad_soyad, sifre_hash
            FROM kullanicilar
            WHERE kullanici_adi = ? OR kullanici_adi = ? OR UPPER(kullanici_adi) = ?
        """, (code, norm_code, code.upper())).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı!")

        if hash_password(req.eski_sifre) != user["sifre_hash"]:
            raise HTTPException(status_code=400, detail="Mevcut şifreniz hatalı!")

        new_hash = hash_password(req.yeni_sifre)
        conn.execute("UPDATE kullanicilar SET sifre_hash = ? WHERE id = ?", (new_hash, user["id"]))

        return {"status": "ok", "message": "Şifreniz başarıyla güncellendi."}

@app.get("/api/kullanicilar")
@app.get("/api/auth/kullanicilar")
def list_kullanicilar():
    with db_session() as conn:
        rows = conn.execute("SELECT id, kullanici_adi, ad_soyad FROM kullanicilar WHERE aktif = 1 ORDER BY id ASC").fetchall()
        return rows

@app.get("/api/hareketler")
def list_hareketler(
    q: Optional[str] = None,
    tip: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    with db_session() as conn:
        query = """
            SELECT h.*, 
                   m.ad as malzeme_adi, m.qr_kod, m.birim, m.marka, m.raf_no,
                   l.ad as lokasyon_adi, l.kod as lokasyon_kod
            FROM stok_hareketleri h
            JOIN malzemeler m ON m.id = h.malzeme_id
            JOIN lokasyonlar l ON l.id = m.lokasyon_id
            WHERE 1=1
        """
        params = []
        if tip and tip in ("GIRIS", "CIKIS"):
            query += " AND h.tip = ?"
            params.append(tip)

        if q:
            pattern = f"%{q.strip()}%"
            query += """ AND (
                m.ad LIKE ? OR m.qr_kod LIKE ? OR h.kullanici LIKE ? 
                OR h.teslim_alan LIKE ? OR h.teslim_eden LIKE ? OR h.sebep LIKE ?
            )"""
            params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

        query += " ORDER BY h.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return rows

@app.get("/api/stats")
def get_stats():
    with db_session() as conn:
        toplam_malzeme = conn.execute("SELECT COUNT(*) as c FROM malzemeler").fetchone()["c"]
        toplam_stok_miktari = conn.execute("SELECT COALESCE(SUM(miktar), 0) as s FROM malzemeler").fetchone()["s"]
        toplam_adet = conn.execute("SELECT COALESCE(SUM(miktar), 0) as s FROM malzemeler WHERE birim = 'adet'").fetchone()["s"]
        toplam_metre = conn.execute("SELECT COALESCE(SUM(miktar), 0) as s FROM malzemeler WHERE birim = 'm'").fetchone()["s"]
        toplam_litre = conn.execute("SELECT COALESCE(SUM(miktar), 0) as s FROM malzemeler WHERE birim = 'lt'").fetchone()["s"]
        toplam_lokasyon = conn.execute("SELECT COUNT(*) as c FROM lokasyonlar").fetchone()["c"]
        toplam_hareket = conn.execute("SELECT COUNT(*) as c FROM stok_hareketleri").fetchone()["c"]
        fotografli_sayisi = conn.execute("SELECT COUNT(DISTINCT malzeme_id) as c FROM fotograflar").fetchone()["c"]
        fotografsiz_sayisi = toplam_malzeme - fotografli_sayisi
        return {
            "toplam_malzeme": toplam_malzeme,
            "toplam_stok_miktari": int(toplam_stok_miktari),
            "toplam_adet": int(toplam_adet),
            "toplam_metre": int(toplam_metre),
            "toplam_litre": int(toplam_litre),
            "toplam_lokasyon": toplam_lokasyon,
            "toplam_hareket": toplam_hareket,
            "fotografli_sayisi": fotografli_sayisi,
            "fotografsiz_sayisi": fotografsiz_sayisi
        }

@app.get("/api/lokasyonlar")
def list_lokasyonlar():
    with db_session() as conn:
        rows = conn.execute("""
            SELECT l.*, COUNT(m.id) as malzeme_sayisi
            FROM lokasyonlar l
            LEFT JOIN malzemeler m ON m.lokasyon_id = l.id
            GROUP BY l.id
            ORDER BY l.id
        """).fetchall()
        return rows

@app.get("/api/malzemeler")
def list_malzemeler(
    q: Optional[str] = None,
    lokasyon_id: Optional[int] = None,
    fotografsiz: Optional[bool] = False,
    hareketler: Optional[bool] = False,
    kullanicilar: Optional[bool] = False,
    tip: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    if kullanicilar:
        return list_kullanicilar()
    if hareketler:
        return list_hareketler(q=q, tip=tip, limit=limit, offset=offset)

    with db_session() as conn:
        query = """
            SELECT m.*, l.ad as lokasyon_adi, l.kod as lokasyon_kod,
                   f.kucuk_resim_yolu as foto_thumb, f.dosya_yolu as foto_ana
            FROM malzemeler m
            JOIN lokasyonlar l ON l.id = m.lokasyon_id
            LEFT JOIN fotograflar f ON f.malzeme_id = m.id AND f.ana_fotograf = 1
            WHERE 1=1
        """
        params = []

        if q:
            query += " AND (m.ad LIKE ? OR m.marka LIKE ? OR m.tip_aciklama LIKE ? OR m.qr_kod LIKE ? OR m.yp_kodu LIKE ? OR m.raf_no LIKE ?)"
            pattern = f"%{q.strip()}%"
            params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

        if lokasyon_id:
            query += " AND m.lokasyon_id = ?"
            params.append(lokasyon_id)

        if fotografsiz:
            query += " AND f.id IS NULL"

        query += " ORDER BY m.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return rows

@app.get("/api/malzemeler/{id}")
def get_malzeme_detay(id: int):
    with db_session() as conn:
        m = conn.execute("""
            SELECT m.*, l.ad as lokasyon_adi, l.kod as lokasyon_kod
            FROM malzemeler m
            JOIN lokasyonlar l ON l.id = m.lokasyon_id
            WHERE m.id = ?
        """, (id,)).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail="Malzeme bulunamadi")

        fotos = conn.execute("SELECT * FROM fotograflar WHERE malzeme_id = ? ORDER BY ana_fotograf DESC, id DESC", (id,)).fetchall()
        hareketler = conn.execute("SELECT * FROM stok_hareketleri WHERE malzeme_id = ? ORDER BY id DESC LIMIT 15", (id,)).fetchall()

        return {
            **m,
            "fotograflar": fotos,
            "hareketler": hareketler
        }

@app.get("/api/malzemeler/qr/{qr_kod}")
def get_malzeme_by_qr(qr_kod: str):
    clean_code = qr_kod.strip()
    # URL icinden kod cikarimi: orn https://.../m/SRS-ANA-00001
    if "/m/" in clean_code:
        clean_code = clean_code.split("/m/")[-1]
    
    with db_session() as conn:
        m = conn.execute("""
            SELECT m.*, l.ad as lokasyon_adi, l.kod as lokasyon_kod
            FROM malzemeler m
            JOIN lokasyonlar l ON l.id = m.lokasyon_id
            WHERE m.qr_kod = ?
        """, (clean_code,)).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail="Bu QR kod sistemde kayitli degil.")

        fotos = conn.execute("SELECT * FROM fotograflar WHERE malzeme_id = ? ORDER BY ana_fotograf DESC, id DESC", (m["id"],)).fetchall()
        hareketler = conn.execute("SELECT * FROM stok_hareketleri WHERE malzeme_id = ? ORDER BY id DESC LIMIT 10", (m["id"],)).fetchall()

        return {
            **m,
            "fotograflar": fotos,
            "hareketler": hareketler
        }

@app.post("/api/malzemeler")
async def create_malzeme(
    request: Request
):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if "eski_sifre" in body and "yeni_sifre" in body:
            return sifre_degistir(SifreDegistirRequest(**body))
        if "kullanici_adi" in body and "sifre" in body:
            return login(LoginRequest(**body))
        raise HTTPException(status_code=400, detail="Gecersiz JSON islem formati")

    # Multipart/form-data: Normal yeni malzeme kaydi
    form = await request.form()
    ad = form.get("ad")
    if not ad:
        raise HTTPException(status_code=400, detail="Malzeme adi zorunludur")

    lokasyon_id = int(form.get("lokasyon_id", 0))
    marka = form.get("marka")
    tip_aciklama = form.get("tip_aciklama")
    miktar = float(form.get("miktar", 0.0) or 0.0)
    birim = form.get("birim", "adet")
    raf_no = form.get("raf_no")
    raf_omru = form.get("raf_omru")
    yp_kodu = form.get("yp_kodu")
    teslim_alan = form.get("teslim_alan")
    teslim_eden = form.get("teslim_eden")
    sebep = form.get("sebep")
    kullanici = form.get("kullanici", "Saha")
    foto = form.get("foto")

    with db_session() as conn:
        lok = conn.execute("SELECT * FROM lokasyonlar WHERE id = ?", (lokasyon_id,)).fetchone()
        if not lok:
            raise HTTPException(status_code=400, detail="Gecersiz lokasyon")

        # Siradaki QR kodu uret
        seq_row = conn.execute("SELECT COUNT(*) as c FROM malzemeler WHERE lokasyon_id = ?", (lokasyon_id,)).fetchone()
        next_seq = (seq_row["c"] or 0) + 1
        qr_kod = f"SRS-{lok['kod']}-{next_seq:05d}"

        # Cakisirsa unique olana kadar arttir
        while conn.execute("SELECT 1 FROM malzemeler WHERE qr_kod = ?", (qr_kod,)).fetchone():
            next_seq += 1
            qr_kod = f"SRS-{lok['kod']}-{next_seq:05d}"

        cur = conn.execute("""
            INSERT INTO malzemeler (
                qr_kod, lokasyon_id, ad, marka, tip_aciklama,
                miktar, birim, miktar_bilinmiyor, raf_no, raf_omru, yp_kodu,
                kaynak
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'manuel')
        """, (qr_kod, lokasyon_id, str(ad).strip(), marka, tip_aciklama, miktar, birim, raf_no, raf_omru, yp_kodu))
        malzeme_id = cur.lastrowid

        # Ilk hareket
        if miktar > 0:
            conn.execute("""
                INSERT INTO stok_hareketleri (
                    malzeme_id, tip, miktar, onceki_miktar, sonraki_miktar,
                    teslim_alan, teslim_eden, sebep, kullanici
                ) VALUES (?, 'GIRIS', ?, 0, ?, ?, ?, ?, ?)
            """, (malzeme_id, miktar, miktar, teslim_alan, teslim_eden, sebep or "Yeni Malzeme Kaydı", kullanici or "Sistem (Yeni Kayıt)"))

    # Foto yukleme
    if foto and hasattr(foto, "filename") and foto.filename:
        content = await foto.read()
        if len(content) > 0:
            save_material_photo(malzeme_id, content, foto.filename)

    return {"status": "ok", "id": malzeme_id, "qr_kod": qr_kod}

@app.put("/api/malzemeler/{id}")
def update_malzeme(id: int, guncelleme: MalzemeGuncelleme):
    with db_session() as conn:
        m = conn.execute("SELECT * FROM malzemeler WHERE id = ?", (id,)).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail="Malzeme bulunamadi")

        conn.execute("""
            UPDATE malzemeler SET
                ad = ?, marka = ?, tip_aciklama = ?, lokasyon_id = ?,
                raf_no = ?, birim = ?, raf_omru = ?, yp_kodu = ?,
                sap_durumu = ?, yp_sm_dv = ?, duran_varlik_turu = ?, uretici_kodu = ?,
                guncelleme_tarihi = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            guncelleme.ad.strip(), guncelleme.marka, guncelleme.tip_aciklama, guncelleme.lokasyon_id,
            guncelleme.raf_no, guncelleme.birim, guncelleme.raf_omru, guncelleme.yp_kodu,
            guncelleme.sap_durumu, guncelleme.yp_sm_dv, guncelleme.duran_varlik_turu, guncelleme.uretici_kodu,
            id
        ))
        return {"status": "ok", "id": id}

@app.post("/api/malzemeler/{id}/hareket")
def create_stok_hareketi(id: int, hareket: StokHareketiGiris):
    if hareket.miktar <= 0:
        raise HTTPException(status_code=400, detail="Miktar 0'dan buyuk olmalidir.")

    with db_session() as conn:
        m = conn.execute("SELECT * FROM malzemeler WHERE id = ?", (id,)).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail="Malzeme bulunamadi")

        mevcut_stok = m["miktar"] or 0.0

        if hareket.tip == "GIRIS":
            yeni_stok = mevcut_stok + hareket.miktar
        elif hareket.tip == "CIKIS":
            if mevcut_stok < hareket.miktar:
                raise HTTPException(
                    status_code=400,
                    detail=f"Yetersiz stok! Mevcut: {mevcut_stok} {m['birim']}, istenen cikis: {hareket.miktar} {m['birim']}."
                )
            yeni_stok = mevcut_stok - hareket.miktar
        else:
            raise HTTPException(status_code=400, detail="Gecersiz hareket tipi (GIRIS veya CIKIS olmali)")

        # Stok miktarini guncelle
        conn.execute("""
            UPDATE malzemeler SET
                miktar = ?, miktar_bilinmiyor = 0, guncelleme_tarihi = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (yeni_stok, id))

        # Hareketi kaydet
        conn.execute("""
            INSERT INTO stok_hareketleri (
                malzeme_id, tip, miktar, onceki_miktar, sonraki_miktar,
                teslim_alan, teslim_eden, sebep, kullanici
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id, hareket.tip, hareket.miktar, mevcut_stok, yeni_stok,
            hareket.teslim_alan, hareket.teslim_eden, hareket.sebep, hareket.kullanici or "Saha"
        ))

        return {
            "status": "ok",
            "malzeme_id": id,
            "onceki_miktar": mevcut_stok,
            "yeni_miktar": yeni_stok,
            "birim": m["birim"]
        }

@app.post("/api/malzemeler/{id}/fotograf")
def upload_fotograf(id: int, foto: UploadFile = File(...)):
    with db_session() as conn:
        m = conn.execute("SELECT * FROM malzemeler WHERE id = ?", (id,)).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail="Malzeme bulunamadi")

    content = foto.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Dosya bos olamaz")

    res = save_material_photo(id, content, foto.filename)
    return res

@app.delete("/api/fotograflar/{photo_id}")
def delete_foto(photo_id: int):
    success = delete_material_photo(photo_id)
    if not success:
        raise HTTPException(status_code=404, detail="Fotograf bulunamadi")
    return {"status": "ok"}

@app.get("/api/qr/{qr_kod}.png")
def get_qr_png(qr_kod: str):
    png_bytes = generate_qr_image(qr_kod)
    return Response(content=png_bytes, media_type="image/png")

@app.get("/api/etiketler/pdf")
def get_etiket_pdf(lokasyon_id: Optional[int] = None):
    with db_session() as conn:
        query = """
            SELECT m.*, l.ad as lokasyon_adi, l.kod as lokasyon_kod
            FROM malzemeler m
            JOIN lokasyonlar l ON l.id = m.lokasyon_id
        """
        params = []
        if lokasyon_id:
            query += " WHERE m.lokasyon_id = ?"
            params.append(lokasyon_id)
        query += " ORDER BY m.id ASC"

        items = conn.execute(query, params).fetchall()
        if not items:
            raise HTTPException(status_code=404, detail="Basılacak malzeme bulunamadı")

        pdf_bytes = generate_label_pdf(items)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=qr_etiketler.pdf"}
        )

@app.get("/api/excel/disa-aktar")
def download_excel():
    export_file = os.path.join(BASE_DIR, "data", "ambar_yerlesim_guncel.xlsx")
    export_db_to_excel(export_file)
    return FileResponse(
        export_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="FRM-OPR.GNL-02_Ambar_Guncel.xlsx"
    )

@app.get("/api/malzemeler/{id}/etiket.pdf")
def get_single_label_pdf(id: int):
    with db_session() as conn:
        m = conn.execute("""
            SELECT m.*, l.ad as lokasyon_adi, l.kod as lokasyon_kod
            FROM malzemeler m
            JOIN lokasyonlar l ON l.id = m.lokasyon_id
            WHERE m.id = ?
        """, (id,)).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail="Malzeme bulunamadı")

        pdf_bytes = generate_label_pdf([m])
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=etiket_{m['qr_kod']}.pdf"}
        )

@app.get("/api/yedek/indir")
def download_backup():
    zip_bytes, filename = create_backup_zip()
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---- FRONTEND SAYFALARI (SPA / HTML) ----
@app.get("/")
def get_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(index_file)

@app.get("/m/{qr_kod}")
def get_by_url(qr_kod: str):
    # Telefonun kendi kamerasindan okunan QR linki buraya duser
    index_file = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(index_file)
