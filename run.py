import uvicorn
import socket
import select
import threading
import sys
import os
import time

from app.ssl_helper import ensure_ssl_certs
from app.main import app

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def pipe_sockets(s1, s2):
    socks = [s1, s2]
    try:
        while True:
            r, _, _ = select.select(socks, [], [], 60)
            if not r:
                break
            for s in r:
                data = s.recv(16384)
                if not data:
                    return
                target = s2 if s is s1 else s1
                target.sendall(data)
    except Exception:
        pass
    finally:
        try:
            s1.close()
        except Exception:
            pass
        try:
            s2.close()
        except Exception:
            pass

def start_multiplexer(listen_host, listen_port, http_port, https_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((listen_host, listen_port))
    server.listen(128)

    while True:
        try:
            client_sock, addr = server.accept()
            # Ilk bayti kontrol et (tuketmeden peek et)
            first_byte = client_sock.recv(1, socket.MSG_PEEK)
            # 0x16 (22) TLS ClientHello (HTTPS) baytidir
            target_port = https_port if first_byte == b'\x16' else http_port

            backend_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_sock.connect(("127.0.0.1", target_port))

            t = threading.Thread(target=pipe_sockets, args=(client_sock, backend_sock), daemon=True)
            t.start()
        except Exception:
            pass

if __name__ == "__main__":
    local_ip = get_local_ip()
    public_port = 8000
    internal_http_port = 8080
    internal_https_port = 8443

    # SSL sertifikalarini hazirla
    ssl_certfile, ssl_keyfile = ensure_ssl_certs(local_ip)

    print("=" * 70)
    print("           SAROS DEPO - AKILLI DUAL (HTTP + HTTPS) SUNUCU")
    print("=" * 70)
    print(f" * Bilgisayardan : http://localhost:{public_port}  veya  https://localhost:{public_port}")
    print(f" * Telefondan    : https://{local_ip}:{public_port} (Kamera için önerilen)")
    print(f"                   veya http://{local_ip}:{public_port}")
    print("-" * 70)
    print(" [ÖZELLİK: OTOMATİK PROTOKOL ALGILAMA]")
    print(f" Port {public_port} hem düz HTTP hem de şifreli HTTPS isteklerini")
    print(" otomatik tanır; 'Failed to fetch' veya SSL protokol hatası vermez!")
    print("=" * 70)

    # 1. Dahili HTTP sunucusu
    def run_http_backend():
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=internal_http_port,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        server.run()

    # 2. Dahili HTTPS sunucusu
    def run_https_backend():
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=internal_https_port,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        server.run()

    t_http = threading.Thread(target=run_http_backend, daemon=True)
    t_https = threading.Thread(target=run_https_backend, daemon=True)
    t_http.start()
    t_https.start()

    # Sunucularin ayaga kalkmasini bekle
    time.sleep(0.8)

    # 3. Port 8000 Multiplexer (Ana thread uzerinde calisir)
    start_multiplexer("0.0.0.0", public_port, internal_http_port, internal_https_port)
