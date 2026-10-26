# ESTÜ Erasmus+ staj ilanı takibi

Her gün 08:33'te (TR) UİB duyurularını tarar. Yeni bir Erasmus+ staj **başvuru** ilanı ya da dil sınavı sonuç duyurusu çıkarsa Telegram'dan mesaj atar.

## Kurulum
1. Telegram'da **@BotFather** → `/newbot` → bot token'ını al.
2. Botuna bir mesaj at, sonra `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini aç ve `"chat":{"id": ...}` değerini al.
3. GitHub'da yeni bir repo aç (private olabilir), bu klasördeki dosyaları yükle.
4. Repo → Settings → Secrets and variables → Actions → iki secret ekle:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Actions sekmesi → "ESTU staj ilani takibi" → **Run workflow**. "✅ Takip çalışıyor" mesajı gelirse kurulum tamam.
