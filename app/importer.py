import os
import re
import datetime
import openpyxl
from app.database import init_db, db_session

EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kaynak", "ambar_yerlesim.xlsx")

LOCATION_CODES = {
    "ANA TM - RAFLAR": "ANA",
    "DEPO-2 TAKIM TEZGAHI": "DP2",
    "Y.P KUTU-1": "YK1",
    "Y.P KUTU-2": "YK2",
    "Y.P KUTU-3": "YK3",
    "Y.P KUTU-4": "YK4",
    "YP KODLULAR": "YPK",
    "KONTEYNER": "KNT",
    "ARABALI TAKIM DOLABI": "ATD",
    "GES DEPO": "GES",
    "IT DOLABI": "ITD",
    "XLPE Kablo Depo Alanı": "XLP",
    "TALİ TM": "TAL",
}

def parse_quantity_and_unit(raw_val):
    """
    Sayisal veya metin iceren ADET hucresini miktar (float), birim (str) ve bilinmiyor (bool) seklinde ayristirir.
    Ornekler:
      5 -> 5.0, 'adet', False
      '50 m' -> 50.0, 'm', False
      '220LT' -> 220.0, 'lt', False
      '-' -> 0.0, 'adet', True
      None -> 0.0, 'adet', True
    """
    if raw_val is None:
        return 0.0, "adet", 1
    
    if isinstance(raw_val, (int, float)):
        return float(raw_val), "adet", 0

    s = str(raw_val).strip()
    if not s or s == "-":
        return 0.0, "adet", 1

    # Sayi + Birim tespiti: orn 50 m, 150 M, 220LT, 20 m
    m = re.match(r"^([\d\.,]+)\s*([a-zA-ZçğıöşüÇĞİÖŞÜ]+)?$", s)
    if m:
        num_str = m.group(1).replace(",", ".")
        unit_str = (m.group(2) or "adet").strip().lower()
        try:
            return float(num_str), unit_str, 0
        except ValueError:
            pass

    return 0.0, "adet", 1

def format_date(d):
    if d is None:
        return None
    if isinstance(d, datetime.datetime):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, datetime.date):
        return d.strftime("%Y-%m-%d")
    s = str(d).strip()
    return s if s else None

def clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None

def import_excel_to_db(excel_file=EXCEL_PATH):
    init_db()
    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"Excel dosyasi bulunamadi: {excel_file}")

    wb = openpyxl.load_workbook(excel_file, data_only=True)
    
    total_imported = 0
    stats = {}

    with db_session() as conn:
        # Once lokasyonlari kaydet/guncelle
        lokasyon_map = {}
        for sheet_name, code in LOCATION_CODES.items():
            conn.execute(
                "INSERT INTO lokasyonlar (kod, ad, excel_sayfa) VALUES (?, ?, ?) ON CONFLICT(kod) DO UPDATE SET ad=excluded.ad, excel_sayfa=excluded.excel_sayfa",
                (code, sheet_name, sheet_name)
            )
            row = conn.execute("SELECT id FROM lokasyonlar WHERE kod = ?", (code,)).fetchone()
            lokasyon_map[sheet_name] = (row["id"], code)

        for sheet_name in wb.sheetnames:
            if sheet_name not in LOCATION_CODES:
                print(f"[ATLANDI] Sayfa: {sheet_name} (malzeme listesi disi)")
                continue

            ws = wb[sheet_name]
            lok_id, lok_code = lokasyon_map[sheet_name]

            # Baslik satirini bul
            header_row_idx = None
            col_map = {}
            for r in range(1, 15):
                row_vals = [clean_str(cell.value) for cell in ws[r]]
                if any(v and "MALZEMENİN ADI" in v for v in row_vals):
                    header_row_idx = r
                    for c_idx, val in enumerate(row_vals):
                        if val:
                            col_map[val.strip()] = c_idx
                    break

            if not header_row_idx:
                print(f"[UYARI] {sheet_name} baslik satiri bulunamadi!")
                continue

            name_col = col_map.get("MALZEMENİN ADI")
            marka_col = col_map.get("MARKA")
            tip_col = col_map.get("TİPİ-AÇIKLAMA")
            adet_col = col_map.get("ADET")
            raf_col = col_map.get("RAF NO")
            giris_col = col_map.get("GİRİŞ T.")
            cikis_col = col_map.get("ÇIKIŞ T.")
            teslim_a_col = col_map.get("TESLİM A.")
            teslim_e_col = col_map.get("TESLİM E.")
            raf_omru_col = col_map.get("RAF ÖMRÜ")
            sebep_col = col_map.get("GİRİŞ-ÇIKIŞ SEBEBİ")

            # GES DEPO ozel alanlar
            sap_col = col_map.get("SAP dışında tutulan stok")
            yp_col = col_map.get("Duran Varlık Kodu & YP KODU")
            yp_sm_col = col_map.get("YP&SM&DV")
            dv_tur_col = col_map.get("Duran Varlık Türü")
            uretici_col = col_map.get("ÜRETİCİ KODU")

            sheet_count = 0
            seq = 1

            for row_idx in range(header_row_idx + 1, ws.max_row + 1):
                raw_row = [c.value for c in ws[row_idx]]
                
                # Malzeme adi kontrolu
                raw_name = raw_row[name_col] if name_col is not None and name_col < len(raw_row) else None
                malzeme_adi = clean_str(raw_name)

                # Bos satir veya sayfa sonu imza satirlari ("Teslim Eden", vb.)
                if not malzeme_adi:
                    continue
                if any(term in malzeme_adi.upper() for term in ["HAZIRLAYAN", "ONAYLAYAN", "FORM NO", "KONTROL EDEN"]):
                    continue

                marka = clean_str(raw_row[marka_col]) if marka_col is not None and marka_col < len(raw_row) else None
                tip_aciklama = clean_str(raw_row[tip_col]) if tip_col is not None and tip_col < len(raw_row) else None
                raw_adet = raw_row[adet_col] if adet_col is not None and adet_col < len(raw_row) else None
                miktar, birim, miktar_bilinmiyor = parse_quantity_and_unit(raw_adet)
                
                raf_no = clean_str(raw_row[raf_col]) if raf_col is not None and raf_col < len(raw_row) else None
                giris_tarihi = format_date(raw_row[giris_col]) if giris_col is not None and giris_col < len(raw_row) else None
                cikis_tarihi = format_date(raw_row[cikis_col]) if cikis_col is not None and cikis_col < len(raw_row) else None
                teslim_alan = clean_str(raw_row[teslim_a_col]) if teslim_a_col is not None and teslim_a_col < len(raw_row) else None
                teslim_eden = clean_str(raw_row[teslim_e_col]) if teslim_e_col is not None and teslim_e_col < len(raw_row) else None
                raf_omru = clean_str(raw_row[raf_omru_col]) if raf_omru_col is not None and raf_omru_col < len(raw_row) else None
                sebep = clean_str(raw_row[sebep_col]) if sebep_col is not None and sebep_col < len(raw_row) else None

                # GES DEPO ozel alanlar
                sap_durumu = clean_str(raw_row[sap_col]) if sap_col is not None and sap_col < len(raw_row) else None
                yp_kodu = clean_str(raw_row[yp_col]) if yp_col is not None and yp_col < len(raw_row) else None
                yp_sm_dv = clean_str(raw_row[yp_sm_col]) if yp_sm_col is not None and yp_sm_col < len(raw_row) else None
                duran_varlik_turu = clean_str(raw_row[dv_tur_col]) if dv_tur_col is not None and dv_tur_col < len(raw_row) else None
                uretici_kodu = clean_str(raw_row[uretici_col]) if uretici_col is not None and uretici_col < len(raw_row) else None

                qr_kod = f"SRS-{lok_code}-{seq:05d}"
                seq += 1

                # DB Ekle
                cur = conn.execute("""
                    INSERT INTO malzemeler (
                        qr_kod, lokasyon_id, ad, marka, tip_aciklama,
                        miktar, birim, miktar_bilinmiyor, raf_no,
                        giris_tarihi, cikis_tarihi, raf_omru,
                        yp_kodu, sap_durumu, yp_sm_dv, duran_varlik_turu, uretici_kodu,
                        kaynak, excel_satir_no
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'excel', ?)
                """, (
                    qr_kod, lok_id, malzeme_adi, marka, tip_aciklama,
                    miktar, birim, miktar_bilinmiyor, raf_no,
                    giris_tarihi, cikis_tarihi, raf_omru,
                    yp_kodu, sap_durumu, yp_sm_dv, duran_varlik_turu, uretici_kodu,
                    row_idx
                ))
                malzeme_id = cur.lastrowid

                # Ilk stok hareketi (GIRIS)
                if miktar > 0:
                    conn.execute("""
                        INSERT INTO stok_hareketleri (
                            malzeme_id, tip, miktar, onceki_miktar, sonraki_miktar,
                            teslim_alan, teslim_eden, sebep, kullanici, tarih
                        ) VALUES (?, 'GIRIS', ?, 0, ?, ?, ?, ?, 'Sistem (Ilk Aktarim)', COALESCE(?, CURRENT_TIMESTAMP))
                    """, (
                        malzeme_id, miktar, miktar,
                        teslim_alan, teslim_eden,
                        sebep or "Excel Envanter Aktarimi",
                        giris_tarihi
                    ))

                sheet_count += 1
                total_imported += 1

            stats[sheet_name] = sheet_count
            print(f"[OK] {sheet_name:25}: {sheet_count} malzeme aktarildi.")

    print("=" * 60)
    print(f"TOPLAM AKTARILAN MALZEME: {total_imported}")
    return stats

if __name__ == "__main__":
    import_excel_to_db()
