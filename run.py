import uvicorn
import socket
import sys
import os
from app.ssl_helper import ensure_ssl_certs

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    use_ssl = "--ssl" in sys.argv

    ssl_keyfile = None
    ssl_certfile = None
    protocol = "http"

    if use_ssl:
        ssl_certfile, ssl_keyfile = ensure_ssl_certs(local_ip)
        protocol = "https"

    print("=" * 65)
    print("      SAROS DEPO - QR KODLU STOK TAKİP SİSTEMİ")
    print("=" * 65)
    print(f" Bilgisayardan erişim : {protocol}://localhost:{port}")
    print(f" Telefondan erişim    : {protocol}://{local_ip}:{port}")
    print("-" * 65)

    if use_ssl:
        print(" [MOD: HTTPS AKTİF] Telefon kamerasının açılması için güvenli bağlantı sağlandı.")
        print("  * Telefondan girerken 'Gelişmiş -> Siteye İlerle (Güvensiz)' diyerek bir kere onaylayınız.")
    else:
        print(" [MOD: STANDART HTTP]")
        print("  * Telefon tarayıcısında kameranın engellenmemesi için:")
        print("    1) 'python run.py --ssl' komutuyla HTTPS modunda başlatabilir,")
        print("    2) Veya Chrome Android'de chrome://flags üzerinden bu IP'ye izin verebilirsiniz.")
    print("=" * 65)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_excludes=["data/*", "*.db", "data/fotograflar/*", "*.zip", "*.xlsx"],
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile
    )
