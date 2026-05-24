import subprocess
import os

files = [
  {"name": "創新全莖苗機械種蔗紀念碑-1-manual.jpg", "id": "12F6Hbv7Ckx1Av35NZ8oZGq8u8KOG19do"},
  {"name": "引進南非參壹零蔗種紀念碑-1-manual.jpg", "id": "1ejGhDRMvu0c7jk6XBVh30udPLk555-nU"},
  {"name": "涌翠閣-1-commons.jpg", "id": "1BeLRzRIdhAkfNZtYwsK2Se65MxVFwTwZ"},
  {"name": "臥龍山碑-1-manual.JPG", "id": "1O9qvdCK2Z21sNYCxMprMM2zVMRWYsv3T"},
  {"name": "莊敬自強紀念碑-1-manual.jpg", "id": "1U6bh09yzyGV7vdyEwP7cEG31epZX5EtV"},
  {"name": "虎尾溪鐵橋-1-commons.jpg", "id": "1xXnIw6YCu9ws1tUz49NTN_Q2MJgv0U5R"},
  {"name": "虎尾溪鐵橋-2-commons.jpg", "id": "1vOKQAH1sYEj9txbgOGjBGexXjbQgJvxT"},
  {"name": "虎尾糖廠-1-commons.png", "id": "1H5rZIIGiL2vKkuPSMM9KAS0EfMsmg16x"},
  {"name": "虎尾糖廠-2-commons.jpg", "id": "1ag5qb-zvDIwsqmjywYAjAoCPMXLuQ1oH"},
  {"name": "虎尾糖廠第三公差宿舍-1-commons.jpg", "id": "14qCmgzLK2880829Z7JgQtwrWaoicDIK6"},
  {"name": "虎尾糖廠酒精槽-1-commons.jpg", "id": "1XJYVaFBpt8QTTbbDsYKOS-fqSkA1ywwf"},
  {"name": "虎尾糖廠酒精槽-2-commons.jpg", "id": "1Ngoh1r6-FtFvy567hMIfEpvYUl-UEys9"},
  {"name": "虎尾鐵橋-1-wiki.jpg", "id": "1fGr_iYpxyxbv8LEFrzX9SbeSBNRPvrmQ"},
  {"name": "虎尾鐵橋-2-commons.jpg", "id": "1LpG-5Zb7ZTZZPO1-3wfDza66izkTVcN0"},
  {"name": "虎尾驛-0-manual.jpg", "id": "1okCv2rx2-i9f_yRp0mfJZhR4dvEv2gBT"},
  {"name": "虎尾驛-1-wiki.jpg", "id": "1oZtLPBxVet7-v5Z812tOe61LYgaedDhy"},
  {"name": "虎尾驛-2-commons.jpg", "id": "1tGyDcXqS4zAszlgGAPtRJRu6ox-Vq4j3"},
  {"name": "雙手萬能碑-1-manual.JPG", "id": "1O5vn89TOaDm3B2hgiJ5EFEhXZMFu9wdl"},
  {"name": "雙手萬能碑-2-manual.JPG", "id": "1SSDfW_b6Hq3YgVqeFT6_9PW1cvXBfZI9"},
  {"name": "雲林布袋戲館-1-commons.jpg", "id": "1fS1jhI21n40wVyJynowsgf9Y3Tt6ew5b"},
  {"name": "雲林布袋戲館-2-commons.jpg", "id": "1nT0yzvpQAMlDsuwUHDp2I4QcyX8bbpko"},
  {"name": "雲林故事館-1-commons.jpg", "id": "1_hHzq81Y6kFIVfZ5-7wTdm7FFHUDwVqz"},
  {"name": "雲林故事館-2-commons.jpg", "id": "1dPhMRPcEU8B9GA-05Yf5WRusBs4owrQN"},
  {"name": "養身之道健身十訣-1-manual.jpg", "id": "1yO-jEtgdkI_dQEShRTdbIOkmD6Q-fuz8"},
  {"name": "養身之道健身十訣-2-manual.jpg", "id": "146T48qM-EfKKd-D9LAl1ysAZyPwVYUAR"}
]

for f in files:
    url = f"https://drive.google.com/uc?export=download&id={f['id']}"
    dest = os.path.join("data/golden", f["name"])
    print(f"Downloading {f['name']}...")
    subprocess.run(["curl", "-L", url, "-o", dest], check=True)
