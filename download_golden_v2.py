import subprocess
import os

files = [
  {"name": "虎尾糖廠附屬醫院（生機廚房）-1-manual.JPG", "id": "1eoq_fp_CYMMThovEkQn1CEe0L0JWz4sa"},
  {"name": "虎尾糖廠附屬醫院（生機廚房）-2-manual.JPG", "id": "1NT2j8pXPKDN8ui2AFVILVozmq37wtXId"},
  {"name": "虎尾糖廠附屬醫院（生機廚房）-3-manual.JPG", "id": "1k9yVAXe2lnk9vLQvOQyzMJq7MLiNJ9BF"},
  {"name": "虎尾糖廠附屬醫院（生機廚房）-4-manual.JPG", "id": "1DJ_mWH4Kkbec_BAYokwfsKeiG9aYcYbp"},
  {"name": "虎尾糖廠附屬醫院（生機廚房）-5-manual.JPG", "id": "1nDxyWl_rQ0A-Nc0mtktCzuwfcHEtjnG5"}
]

os.makedirs("data/golden", exist_ok=True)

for f in files:
    url = f"https://drive.google.com/uc?export=download&id={f['id']}"
    dest = os.path.join("data/golden", f["name"])
    print(f"Downloading {f['name']}...")
    subprocess.run(["curl", "-L", url, "-o", dest], check=True)
