import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.database import db_session

class TestDepoSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_stats(self):
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data["toplam_malzeme"], 730)
        self.assertEqual(data["toplam_lokasyon"], 13)
        print("\n[TEST] Stats OK:", data)

    def test_02_get_material_by_qr(self):
        # Ilk malzemenin QR kodu
        res = self.client.get("/api/malzemeler/qr/SRS-ANA-00001")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["qr_kod"], "SRS-ANA-00001")
        self.assertEqual(data["ad"], "Radyatör Isıtıcı")
        print("[TEST] QR Bulma OK:", data["ad"], "Miktar:", data["miktar"])

    def test_03_stock_movement_in_out(self):
        # Test icin malzeme getir
        res = self.client.get("/api/malzemeler/qr/SRS-ANA-00001")
        m = res.json()
        mat_id = m["id"]
        initial_qty = m["miktar"]

        # 1. STOK GIRISI (+5)
        res_in = self.client.post(f"/api/malzemeler/{mat_id}/hareket", json={
            "tip": "GIRIS",
            "miktar": 5,
            "teslim_alan": "Ahmet Y.",
            "teslim_eden": "Mehmet K.",
            "sebep": "Test Girisi"
        })
        self.assertEqual(res_in.status_code, 200)
        data_in = res_in.json()
        self.assertEqual(data_in["yeni_miktar"], initial_qty + 5)
        print(f"[TEST] Stok Giris OK: {initial_qty} -> {data_in['yeni_miktar']}")

        # 2. STOK CIKISI (-2)
        res_out = self.client.post(f"/api/malzemeler/{mat_id}/hareket", json={
            "tip": "CIKIS",
            "miktar": 2,
            "teslim_alan": "Ali T.",
            "sebep": "Saha Montaj"
        })
        self.assertEqual(res_out.status_code, 200)
        data_out = res_out.json()
        self.assertEqual(data_out["yeni_miktar"], initial_qty + 3)
        print(f"[TEST] Stok Cikis OK: {data_in['yeni_miktar']} -> {data_out['yeni_miktar']}")

        # 3. YETERSIZ STOK ENGELI (Mevcuttan cok cikmaya calis)
        res_fail = self.client.post(f"/api/malzemeler/{mat_id}/hareket", json={
            "tip": "CIKIS",
            "miktar": 99999,
            "sebep": "Gecersiz Talep"
        })
        self.assertEqual(res_fail.status_code, 400)
        print("[TEST] Yetersiz Stok Korumasi Basariyla Devreye Girdi (400 Bad Request)")

        # Geri al (stoku eski haline dondur)
        self.client.post(f"/api/malzemeler/{mat_id}/hareket", json={
            "tip": "CIKIS",
            "miktar": 3,
            "sebep": "Test Sifirlama"
        })

    def test_04_create_new_material(self):
        # Yeni malzeme ekle
        res = self.client.post("/api/malzemeler", data={
            "ad": "Test Sayısal Multimetre Probu",
            "lokasyon_id": 1, # ANA TM
            "marka": "Fluke",
            "tip_aciklama": "TL175 TwistGuard",
            "miktar": 10,
            "birim": "adet",
            "raf_no": "99",
            "teslim_alan": "Murat S.",
            "sebep": "Yeni Satın Alma"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["qr_kod"].startswith("SRS-ANA-"))
        print("[TEST] Yeni Malzeme Olusturuldu. Atanan QR:", data["qr_kod"])

        # QR ile geri oku
        res_fetch = self.client.get(f"/api/malzemeler/qr/{data['qr_kod']}")
        self.assertEqual(res_fetch.status_code, 200)
        fetched = res_fetch.json()
        self.assertEqual(fetched["ad"], "Test Sayısal Multimetre Probu")
        self.assertEqual(fetched["miktar"], 10)

        # Temizlik
        with db_session() as conn:
            conn.execute("DELETE FROM stok_hareketleri WHERE malzeme_id = ?", (data["id"],))
            conn.execute("DELETE FROM malzemeler WHERE id = ?", (data["id"],))

    def test_05_pdf_label_generation(self):
        res = self.client.get("/api/etiketler/pdf?lokasyon_id=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/pdf")
        self.assertTrue(len(res.content) > 1000)
        print(f"[TEST] PDF Etiket Sayfasi Uretildi, Boyut: {len(res.content)} bytes")

    def test_06_excel_export(self):
        res = self.client.get("/api/excel/disa-aktar")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.content) > 50000)
        print(f"[TEST] Excel Dosyasi Disa Aktarildi, Boyut: {len(res.content)} bytes")

    def test_07_single_label_and_backup(self):
        # 1. Tekil etiket testi
        res_label = self.client.get("/api/malzemeler/1/etiket.pdf")
        self.assertEqual(res_label.status_code, 200)
        self.assertEqual(res_label.headers["content-type"], "application/pdf")
        self.assertTrue(len(res_label.content) > 1000)
        print(f"[TEST] Tekil Etiket PDF OK, Boyut: {len(res_label.content)} bytes")

        # 2. Sistem ZIP yedek testi
        res_backup = self.client.get("/api/yedek/indir")
        self.assertEqual(res_backup.status_code, 200)
        self.assertEqual(res_backup.headers["content-type"], "application/zip")
        self.assertTrue(len(res_backup.content) > 10000)
        print(f"[TEST] Sistem ve Fotograf ZIP Yedegi OK, Boyut: {len(res_backup.content)} bytes")

if __name__ == "__main__":
    unittest.main()
