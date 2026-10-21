import urllib.request
import os

url = "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"
target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "js", "html5-qrcode.min.js")

try:
    print("Downloading html5-qrcode...")
    urllib.request.urlretrieve(url, target)
    print(f"Downloaded to {target}, size: {os.path.getsize(target)} bytes")
except Exception as e:
    print("Download error:", e)
