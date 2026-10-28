"""ESTÜ UİB duyurularında yeni Erasmus+ staj ilanı var mı kontrol eder, varsa Telegram'a yollar.
Saatte bir çalışır: Telegram'dan /kontrol komutu geldiyse hemen tarar, ayrıca günde bir kez (08:00 TR sonrası) otomatik tarar."""
import json, os, re, sys, urllib.request
from datetime import date, datetime, timezone, timedelta
from html.parser import HTMLParser

BASE = "https://uib.eskisehir.edu.tr"
PAGES = [f"{BASE}/tr/Duyuru?page={p}&type=all" for p in (1, 2, 3)]
STATE_FILE = "state.json"
SINCE = date(2026, 10, 27)  # bundan eski duyurular yok sayılır
DAILY_HOUR_TR = 8           # günlük otomatik tarama saati (TR)
TR = timezone(timedelta(hours=3))

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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


def http(url, data=None):
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
               "Accept-Language": "tr-TR,tr;q=0.9"}
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def telegram(msg):
    if not TOKEN or not CHAT_ID:
        print("Telegram bilgileri yok, mesaj:\n" + msg)
        return
    http(f"https://api.telegram.org/bot{TOKEN}/sendMessage", {"chat_id": CHAT_ID, "text": msg})


def kontrol_istendi_mi(state):
    """Telegram'da yeni /kontrol komutu var mı bakar; okunan mesajları işaretler."""
    if not TOKEN:
        return False
    try:
        r = json.loads(http(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={state.get('offset', 0)}&timeout=0"))
    except Exception as e:
        print("getUpdates hatası:", e)
        return False
    istendi = False
    for u in r.get("result", []):
        state["offset"] = u["update_id"] + 1
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) == str(CHAT_ID) and (msg.get("text") or "").strip().lower().startswith("/kontrol"):
            istendi = True
    return istendi


def tara(state, heartbeat):
    seen = set(state.get("seen", []))
    items = {}
    try:
        for url in PAGES:
            p = LinkParser()
            p.feed(http(url))
            for href, text in p.items:
                items.setdefault(href, text)
    except Exception as e:
        telegram(f"⚠️ ESTÜ UİB sayfasına ulaşılamadı: {e}")
        return
    if not items:
        telegram("⚠️ ESTÜ UİB sayfası açıldı ama duyuru bulunamadı (site yapısı değişmiş olabilir).")
        return

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
    if heartbeat and not new:
        telegram(f"✅ Takip çalışıyor: {len(items)} duyuru tarandı, yeni Erasmus+ staj ilanı yok.")
    print(f"{len(items)} duyuru tarandı, {len(new)} bildirim gönderildi.")
    state["seen"] = sorted(seen)


def main():
    state = json.load(open(STATE_FILE)) if os.path.exists(STATE_FILE) else {}
    if not state and os.path.exists("seen.json"):  # eski sürümden geçiş
        state["seen"] = json.load(open("seen.json"))

    now = datetime.now(TR)
    today = now.date().isoformat()
    manuel = os.environ.get("HEARTBEAT") == "1"
    komut = kontrol_istendi_mi(state)
    gunluk = now.hour >= DAILY_HOUR_TR and state.get("last_daily") != today

    if manuel or komut:
        tara(state, heartbeat=True)
    elif gunluk:
        tara(state, heartbeat=True)
    else:
        print("Yapılacak bir şey yok.")
    if gunluk:
        state["last_daily"] = today

    json.dump(state, open(STATE_FILE, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
