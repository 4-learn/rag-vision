import subprocess
import os

files = [
    {"name": "虎尾糖廠附屬醫院（生機廚房）-1.jpg", "id": "1arsQnEyEPtgkuA6tHlechqOUv3CmJAM6"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-2.jpg", "id": "1xrDPSM6LLdPjhj5Z5rpIZECxC2fIUDtR"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-3.jpg", "id": "1GgjczbaIiXO-_m_kbq-OOHQkNO25djE8"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-4.jpg", "id": "1jGrcJDENR6vIfhABZP180c-FJk_jCEZE"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-5.jpg", "id": "1kGfefyoCnuW1GKXtP38JhGjWum2vEz2m"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-6.jpg", "id": "1LamMQPMU-7WNUJINkXyd19x5lP4dh7xW"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-7.jpg", "id": "1NT2j8pXPKDN8ui2AFVILVozmq37wtXId"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-8.jpg", "id": "1k9yVAXe2lnk9vLQvOQyzMJq7MLiNJ9BF"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-9.jpg", "id": "1DJ_mWH4Kkbec_BAYokwfsKeiG9aYcYbp"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-10.jpg", "id": "1nDxyWl_rQ0A-Nc0mtktCzuwfcHEtjnG5"},
    {"name": "虎尾糖廠附屬醫院（生機廚房）-11.jpg", "id": "1eoq_fp_CYMMThovEkQn1CEe0L0JWz4sa"}
]

os.makedirs("data/golden", exist_ok=True)

for f in files:
    url = f"https://drive.google.com/uc?export=download&id={f['id']}"
    dest = os.path.join("data/golden", f["name"])
    print(f"Downloading {f['name']}...")
    subprocess.run(["curl", "-L", url, "-o", dest], check=True)
