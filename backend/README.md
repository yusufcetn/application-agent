# Backend

FastAPI + SQLite. LLM çağrıları yerelde oturum açılmış **Claude Code** veya **Codex** CLI
üzerinden yapılır; API anahtarı gerekmez.

## Kurulum

```bash
cd backend
uv sync
uv run playwright install chromium
```

Chromium, CV'yi PDF'e çevirmek ve JavaScript ile yüklenen ilan sayfalarını okumak için kullanılıyor.

Proje kökündeki `.env.example` dosyasını `.env` adıyla kopyala ve `LLM_PROVIDER` değerini seç
(`claude` veya `codex`). [uv](https://docs.astral.sh/uv/) macOS ve Windows'ta aynı şekilde çalışır.

Seçtiğin CLI'da oturum açık olmalı:

- Claude Code: `claude` çalıştırıp `/login`
- Codex: `codex login`

**Windows notları**

- Claude Code Windows'ta Git for Windows (Git Bash) ister.
- Backend CLI'ı bulamazsa `.env` içinde tam yolunu ver, ör. `CLAUDE_BIN=C:\Users\ad\AppData\Roaming\npm\claude.cmd`.

## Çalıştırma

```bash
uv run uvicorn app.main:app --reload --port 8000
```

API dokümantasyonu: http://localhost:8000/docs

## Demo veri (LLM olmadan arayüz testi)

Arayüzü test etmek için LLM'e ihtiyaç duymadan her durumda veri oluşturur: profil, projeler, ayarlar,
bir tarama ve 7 ilan (hazır paket ve gerçek PDF, hatalı paket, paketsiz, başvurulmuş, mülakat, manuel).
Gerçek veriye dokunmamak için ayrı bir klasör kullanır.

macOS / Linux:

```bash
export DATA_DIR=../data-demo DATABASE_URL=sqlite:///../data-demo/app.db
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):

```powershell
$env:DATA_DIR="../data-demo"; $env:DATABASE_URL="sqlite:///../data-demo/app.db"
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload --port 8000
```

## Testler

```bash
uv run pytest
```

Testler CLI'ları gerçekten çağırmaz; sahte script'lerle çalışır.

## Yapı

| Yol | İçerik |
|---|---|
| `app/schemas.py` | API sözleşmesi modelleri (`contracts/examples` ile birebir) |
| `app/db.py` | SQLite tabloları |
| `app/api/` | HTTP endpoint'leri |
| `app/llm/runner.py` | Claude Code / Codex CLI ile JSON şemalı LLM çağrısı |
| `app/llm/profile_import.py` | CV dosyası → profil |
| `app/llm/job_extract.py` | İlan sayfası metni → ilan bilgileri |
| `app/llm/tailor.py` | İlana özel CV, ön yazı, cevaplar, puan (+ uydurma bilgi ayıklama) |
| `app/jobs/fetch.py` | İlan sayfasını indirme (HTTP, gerekirse Chromium) |
| `app/render/` | CV HTML şablonu ve PDF üretimi |
| `app/services/packages.py` | Başvuru paketi üretim akışı (arka planda çalışır) |
| `app/sources/` | İlan kaynakları (Greenhouse, Lever, Ashby, RemoteOK, Remotive, Arbeitnow, Adzuna) |
| `app/search/filters.py` | Ücretsiz ön filtre ve ilgi sıralaması |
| `app/llm/score.py` | İlanları toplu halde puanlama |
| `app/search/service.py` | Tarama akışı: kaynaklar → filtre → puan → kayıt → paket |
| `app/search/scheduler.py` | Günlük otomatik tarama |
| `app/sources/email_alerts.py` | İş alarmı e-postalarını IMAP ile okuma |
| `app/llm/alert_extract.py` | Alarm e-postasındaki ilanları çıkarma |

## Otomatik tarama

Tarama ayarlardaki `schedule_cron` saatinde (varsayılan her gün 08:00) çalışır, ama **sadece backend
açıkken**. Bilgisayar o saatte uykudaysa açıldıktan sonra 12 saat içinde bir kez çalışır.

Greenhouse / Lever / Ashby için şirketin kariyer sayfası adresindeki kısa adı ayarlara ekle:
`job-boards.greenhouse.io/anthropic` → `anthropic`, `jobs.lever.co/palantir` → `palantir`,
`jobs.ashbyhq.com/ramp` → `ramp`.

## İş alarmı e-postaları

LinkedIn, Kariyer.net, Indeed veya Glassdoor'dan gelen iş alarmı e-postalarındaki ilanlar da taramaya
katılabilir. Posta kutusu **salt okunur** açılır: e-postalar okundu olarak işaretlenmez, hiçbir şey
silinmez veya gönderilmez. Her e-posta bir kez işlenir.

Gmail için kurulum:

1. Google hesabında 2 adımlı doğrulamayı aç.
2. https://myaccount.google.com/apppasswords adresinden bir uygulama şifresi oluştur.
3. `.env` dosyasına `IMAP_USER` (e-posta adresin) ve `IMAP_PASSWORD` (uygulama şifresi) yaz.
4. Ayarlarda `email_alerts` seçeneğini aç.

Başka bir e-posta sağlayıcısı kullanıyorsan `IMAP_HOST` değerini değiştir.

Alarm e-postalarında ilanın sadece kısa bir özeti bulunur. Tam metin, paket hazırlanırken ilan
sayfasından bir kez okunur. LinkedIn sayfayı giriş ekranıyla kapatırsa paket hata sebebini gösterir;
ilan metnini yapıştırıp paketi yeniden oluşturabilirsin.

## Telefondan kullanım (Tailscale)

Herkes kendi bilgisayarındaki backend'i kendi telefonundan kullanır. Bağlantı Tailscale üzerinden
kurulur: backend internete ya da ev ağına açılmaz, sadece senin Tailscale cihazların ulaşabilir.

1. Bilgisayara ve telefona Tailscale'i kur, aynı hesapla giriş yap.
2. `.env` dosyasına uzun, rastgele bir `API_TOKEN` yaz. Örnek üretmek için:
   `uv run python -c "import secrets; print(secrets.token_urlsafe(24))"`
3. Frontend'i derle (`frontend` klasöründe `npm run build`) ve backend'i başlat
   (`uv run uvicorn app.main:app --port 8000`). Backend derlenmiş arayüzü de sunar.
4. Tailscale ile HTTPS adres ver:
   ```bash
   tailscale serve --bg 8000
   ```
   Komut `https://<bilgisayar-adı>.<tailnet>.ts.net` gibi bir adres yazar. Durumu görmek için
   `tailscale serve status`, kapatmak için `tailscale serve --https=443 off`.
5. Telefonda bu adresi Chrome'da aç, erişim anahtarını bir kez gir, sonra menüden
   **Ana ekrana ekle** de. Uygulama gibi tam ekran açılır.

Dikkat:

- **`tailscale funnel` kullanma.** Funnel adresi herkese açar; `serve` sadece senin cihazlarına açar.
- `API_TOKEN` boşken Tailscale üzerinden gelen istekler reddedilir (403). Böylece anahtar
  unutulsa bile veriler açılmaz.
- Telefon, bilgisayar açık ve backend çalışıyorken bağlanabilir.
