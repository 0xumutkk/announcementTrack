"""ESTÜ UİB duyurularında yeni Erasmus+ staj ilanı var mı kontrol eder, varsa Telegram'a yollar."""
import json, os, re, sys, urllib.request
from datetime import date
from html.parser import HTMLParser

BASE = "https://uib.eskisehir.edu.tr"
PAGES = [f"{BASE}/tr/Duyuru?page={p}&type=all" for p in (1, 2, 3)]
STATE_FILE = "seen.json"
SINCE = date(2026, 10, 27)  # bundan eski duyurular yok sayılır

# Staj ilanı: "staj" + (başvuru|ilan) geçen, liste/asil-yedek olmayan başlıklar
STAJ_RE = re.compile(r"staj", re.I)
BASVURU_RE = re.compile(r"başvuru|basvuru|ilan", re.I)
LISTE_RE = re.compile(r"asil|yedek|sıralı|sirali|liste|oryantasyon|hibelendirme", re.I)
DIL_RE = re.compile(r"yabancı dil sınavı.*(nihai|sınav sonuçları)", re.I)

AYLAR = {"oca": 1, "şub": 2, "mar": 3, "nis": 4, "may": 5, "haz": 6,
         "tem": 7, "ağu": 8, "eyl": 9, "eki": 10, "kas": 11, "ara": 12}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items, self._href, self._buf = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if "/Duyuru/Detay/" in href:
                self._href, self._buf = href, []

    def handle_data(self, data):
        if self._href:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            text = re.sub(r"\s+", " ", " ".join(self._buf)).strip()
            if len(text) > 20:
                self.items.append((self._href, text))
            self._href = None


def parse_date(text):
    m = re.search(r"(\d{1,2})\s*([A-Za-zÇĞİÖŞÜçğıöşü]{3})\w*\s*(\d{4})", text)
    if not m:
        return None
    ay = AYLAR.get(m.group(2).lower().replace("i̇", "i"))
    try:
        return date(int(m.group(3)), ay, int(m.group(1))) if ay else None
    except ValueError:
        return None


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def telegram(msg):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram bilgileri yok, mesaj:\n" + msg)
        return
    data = json.dumps({"chat_id": chat, "text": msg, "disable_web_page_preview": False}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def main():
    seen = set(json.load(open(STATE_FILE))) if os.path.exists(STATE_FILE) else set()
    items = {}
    try:
        for url in PAGES:
            p = LinkParser()
            p.feed(fetch(url))
            for href, text in p.items:
                items.setdefault(href, text)
    except Exception as e:
        telegram(f"⚠️ ESTÜ UİB sayfasına ulaşılamadı: {e}")
        sys.exit(1)

    if not items:
        telegram("⚠️ ESTÜ UİB sayfası açıldı ama duyuru bulunamadı (site yapısı değişmiş olabilir).")
        sys.exit(1)

    new = []
    for href, text in items.items():
        if href in seen:
            continue
        d = parse_date(text)
        if d and d < SINCE:
            continue
        link = href if href.startswith("http") else BASE + href
        if STAJ_RE.search(text) and BASVURU_RE.search(text) and not LISTE_RE.search(text):
            new.append(f"🔔 ESTÜ Erasmus+ staj ilanı yayınlandı!\n{text[:300]}\n{link}")
        elif DIL_RE.search(text):
            new.append(f"📝 Dil sınavı sonucu duyurusu:\n{text[:200]}\n{link}")
        else:
            continue
        seen.add(href)

    for msg in new:
        telegram(msg)
    print(f"{len(items)} duyuru tarandı, {len(new)} bildirim gönderildi.")
    if os.environ.get("HEARTBEAT") == "1" and not new:
        telegram(f"✅ Takip çalışıyor: {len(items)} duyuru tarandı, yeni Erasmus+ staj ilanı yok.")
    json.dump(sorted(seen), open(STATE_FILE, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
