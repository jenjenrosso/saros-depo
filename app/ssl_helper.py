import os
import datetime
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

SSL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ssl")

def ensure_ssl_certs(local_ip: str) -> tuple[str, str]:
    os.makedirs(SSL_DIR, exist_ok=True)
    cert_file = os.path.join(SSL_DIR, "cert.pem")
    key_file = os.path.join(SSL_DIR, "key.pem")

    if os.path.exists(cert_file) and os.path.exists(key_file):
        return cert_file, key_file

    print(f"[*] Yerel SSL sertifikasi olusturuluyor (IP: {local_ip})...")

    # Private key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Subject & Issuer
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Saros Depo"),
        x509.NameAttribute(NameOID.COMMON_NAME, local_ip),
    ])

    # Alt names (IP and localhost)
    san_list = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))
    ]
    try:
        san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
    except Exception:
        pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[OK] SSL sertifikasi hazirlandi: {cert_file}")
    return cert_file, key_file
