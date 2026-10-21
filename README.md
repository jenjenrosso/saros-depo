# Saros Depo - QR Kodlu Stok Takip ve Yönetim Sistemi

Saros RES Ambar Yerleşim Formundaki (`FRM-OPR.GNL-02`) 13 ambar lokasyonu ve 730 malzemenin telefonla QR kod okutularak stok giriş/çıkışının yapıldığı, fotoğraflı ve mobil öncelikli ambar takip sistemi.

---

## 🚀 Hızlı Başlatma

Terminalde proje dizininde aşağıdaki komutlardan birini çalıştırın:

### 1. Standart Mod (HTTP)
```bash
python run.py
```
- Bilgisayardan: `http://localhost:8000`
- Telefondan: `http://<BİLGİSAYAR_IP>:8000`

### 2. Güvenli Mod (HTTPS - Telefon Kamerası İçin Önerilen)
```bash
python run.py --ssl
```
- Bilgisayarınızın yerel IP'si için otomatik SSL sertifikası üretilir.
- Telefondan: `https://<BİLGİSAYAR_IP>:8000`
- *(İlk girişte tarayıcıdaki "Gelişmiş -> Siteye İlerle" uyarısını onaylayınız).*

---

## 📱 Temel Özellikler

1. **Doğrudan Canlı Kamera ile QR Okuma:**
   - "QR KOD OKUT" butonuna basıldığı an telefonun arka kamerası canlı olarak açılır.
   - Dosya/galeri seçici açılmaz; QR çerçeveye girdiği an otomatik okunur, telefon titrer ve bip sesiyle stok ekranına geçer.
   - Depo karanlık ortamları için **🔦 Fener (Flaş)** açma/kapama desteği mevcuttur.

2. **Malzeme Ekle & Malzeme Düş Ekranı:**
   - Mevcut ambar stoku büyük puntoyla gösterilir.
   - Miktar artırma/azaltma butonları (`-1`, `+1`, `-5`, `+5`, `-10`, `+10`).
   - Teslim alan, teslim eden, hareket sebebi alanları.
   - 🟢 **STOK GİRİŞİ** ve 🔴 **STOK ÇIKIŞI** butonları.
   - **Yetersiz stok koruması:** Mevcut stoktan fazla çıkış yapılması otomatik engellenir.
   - Alt kısımda geçmiş stok hareketleri listelenir.

3. **Fotoğraf Yönetimi ve Düzenleme:**
   - Mevcut 730 malzeme başlangıçta fotoğrafsızdır.
   - Listede **"📷 Fotoğrafsızlar"** filtresine basarak eksik ürünler tek tek filtrelenebilir.
   - Düzenleme ekranında *"Kamerayı Aç ve Fotoğraf Çek"* butonuna basıldığında doğrudan telefon kamerası açılarak malzeme fotoğraflanır ve otomatik optimize edilir (1280px + 300px thumbnail).

4. **Yeni Malzeme Kaydı:**
   - Listede olmayan bir malzeme eklendiğinde sistem otomatik olarak sıradaki QR kodunu (`SRS-XXX-00000`) üretir.
   - Kayıt anında kameradan fotoğraf eklenebilir.

5. **A4 Yazdırılabilir QR Etiketleri:**
   - Lokasyon bazında veya tekil malzeme için A4 etiket kağıdına uygun (sayfa başına 24 adet) PDF çıktısı alınabilir.

6. **Güncel Excel Export:**
   - Sistemdeki güncel stokları ve hareketleri orijinal `FRM-OPR.GNL-02` Excel formatında tek tıkla indirir.

7. **Sistem Yedeği (ZIP):**
   - SQLite veritabanı ve yüklenen tüm fotoğrafları tek tıkla ZIP olarak yedekler.

8. **PWA (Progressive Web App):**
   - Telefondan tarayıcı menüsünden *"Ana Ekrana Ekle"* denildiğinde telefon uygulaması gibi tam ekran çalışır.

---

## 🧪 Testleri Çalıştırma

Tüm işlevleri otomatik test etmek için:
```bash
python -m unittest tests.test_flow
```
*(7/7 test: stats, QR bulma, stok giriş, stok çıkış, yetersiz stok engeli, yeni malzeme, etiket PDF, excel export, zip yedek).*
