# Application Agent

[English](README.md) · **Türkçe**

Kendi bilgisayarında çalışan bir iş başvurusu asistanı. Kriterlerine uyan ilanları bulur, her ilanı
profiline göre puanlar ve uygun olanlar için bir **başvuru paketi** hazırlar: ilana göre uyarlanmış CV (PDF),
ön yazı, başvuru formunda çıkabilecek sorulara hazır cevaplar ve bir uyum analizi.

**Başvuruyu her zaman sen yaparsın.** Uygulama hiçbir başvuru formunu doldurmaz ve göndermez.

Her şey kendi bilgisayarında çalışır. Profilin, CV'n ve ilan verilerin yerel bir SQLite veritabanında
kalır. Barındırılan bir servis, hesap ya da API anahtarı yoktur: dil modeli çağrıları, zaten oturum açtığın
**Claude Code** veya **Codex** CLI üzerinden yapılır.

## İçindekiler

- [Özellikler](#özellikler)
- [Nasıl çalışır](#nasıl-çalışır)
- [Teknoloji](#teknoloji)
- [Gerekenler](#gerekenler)
- [Hızlı kurulum](#hızlı-kurulum)
- [Uygulamayı kullanma](#uygulamayı-kullanma)
- [Yapılandırma](#yapılandırma)
- [Kaynaklar](#kaynaklar)
- [Telefondan kullanım](#telefondan-kullanım)
- [Demo modu (LLM gerekmez)](#demo-modu-llm-gerekmez)
- [Geliştirme ve testler](#geliştirme-ve-testler)
- [Klasör yapısı](#klasör-yapısı)
- [Gizlilik ve güvenlik](#gizlilik-ve-güvenlik)
- [Sorun giderme](#sorun-giderme)
- [Katkı](#katkı)
- [Lisans](#lisans)

## Özellikler

- **Profil ve projeler tek yerde.** Mevcut CV'ni (PDF, DOCX, TXT veya MD) yükle, LLM düzenlenebilir bir
  profile dönüştürsün. Projeleri elle ekleyebilir ya da JSON dosyalarından toplu içe aktarabilirsin.
- **Otomatik ilan arama.** Şirket kariyer sayfalarından, genel ilan sitelerinden ve iş alarmı
  e-postalarından ilan toplar. Günlük zamanlamayla ya da istediğin an çalışır.
- **Önce ucuz ön filtre, sonra LLM puanı.** Ücretsiz bir anahtar kelime / konum / seviye filtresi,
  LLM'e göndermeden önce bariz uyumsuzları eler. Pozisyon ve konum eşleştirmesi Türkçe ve İngilizce
  yazımları tanır.
- **Gerekçeli puan.** Her ilan 0–100 arası puan ve kısa bir açıklama alır; neden o sırada olduğunu görürsün.
- **Her ilan için başvuru paketi.**
  - İlana göre uyarlanmış, PDF'e çevrilmiş CV (Playwright ile Chromium).
  - O şirkete ve role özel ön yazı.
  - Olası form sorularına hazır cevaplar. Maaş gibi bilinemeyen konular doldurulacak şablon olarak kalır.
  - Uyum analizi: eşleşen ve eksik yetenekler, öne çıkarılan projeler.
- **Dürüst kalır.** Uyarlama adımı yalnızca kendi profilindeki bilgileri kullanacak şekilde tasarlandı ve
  uydurma ayrıntıları ayıklar. Yine de göndermeden önce sonucu mutlaka oku
  (bkz. [Gizlilik ve güvenlik](#gizlilik-ve-güvenlik)).
- **CV dili ilana uyar** (`auto`, `tr` veya `en`).
- **Başvuru takibi.** Her ilan `new`, `applied`, `skipped`, `interview`, `rejected` ve `offer` durumlarından
  geçer.
- **Link ya da yapıştırılmış metinle ilan ekleme.** Bir sayfa okunamazsa (ör. giriş ekranı arkasında),
  ilan metnini yapıştırabilirsin.
- **Telefona yüklenebilir.** Arayüz bir PWA. Tailscale ile gerçek bir uygulama gibi yükleyip kendi
  bilgisayarını backend olarak kullanabilirsin.

## Nasıl çalışır

```
┌──────────────────────┐   REST/JSON    ┌──────────────────────────────────────────┐
│  frontend (React)    │ ─────────────▶ │  backend (FastAPI)                       │
│  profil editörü      │                │  ├─ api/        HTTP katmanı             │
│  ilan listesi        │ ◀───────────── │  ├─ sources/    ilan kaynakları          │
│  başvuru paketi      │                │  ├─ llm/        puanlama, uyarlama       │
│  ayarlar             │                │  ├─ render/     CV → PDF                 │
└──────────────────────┘                │  ├─ search/     akış + zamanlayıcı       │
                                        │  └─ db/         SQLite                   │
                                        └──────────────────────────────────────────┘
```

Bir tarama şu adımlardan geçer:

1. Etkin olan her kaynaktan ilanları **topla**.
2. Ücretsiz ön filtreyle **ele** (pozisyon, konum, seviye, hariç tutulan kelimeler, ilan yaşı).
3. Kalanları LLM ile toplu halde **puanla** (her taramada `SEARCH_MAX_SCORED_PER_RUN` ile sınırlı).
4. Sonuçları **kaydet**. Daha önce görülen ilanlar tekrar puanlanmaz, bu yüzden ikinci tarama hızlı biter.
5. Asgari puanın üstündeki her ilan için arka planda **paket hazırla**.

Frontend ile backend arasındaki tek bağımlılık REST API'dir. Örnek veriler
[`contracts/examples/`](contracts/examples) altındadır ve mock modu ile testlerde kullanılır.

## Teknoloji

| Parça | Teknoloji |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLModel + SQLite, APScheduler, httpx, BeautifulSoup |
| Belgeler | pypdf ve python-docx (CV okuma), Jinja2 + Playwright/Chromium (CV → PDF, JavaScript ile yüklenen sayfalar) |
| LLM | Claude Code CLI veya Codex CLI, JSON şemasıyla alt süreç olarak çağrılır. API anahtarı yok. |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, React Router, vite-plugin-pwa |
| Araçlar | Python için [uv](https://docs.astral.sh/uv/), frontend için npm, pytest ve Node'un yerleşik test çalıştırıcısı |

## Gerekenler

| Araç | Neden | Kontrol |
|---|---|---|
| Git | Repoyu çekmek | `git --version` |
| [uv](https://docs.astral.sh/uv/) | Python'u ve backend'i kurar | `uv --version` |
| Node.js 22 | Arayüzü derlemek | `node --version` |
| Claude Code **veya** Codex CLI, oturum açık | Tüm LLM çağrıları (abonelik kullanılır) | `claude -p "merhaba"` veya `codex exec "merhaba"` |
| Tailscale (isteğe bağlı) | Telefondan kullanım | `tailscale status` |

Test edilen platformlar macOS ve Windows. Windows'ta Claude Code ayrıca Git for Windows (Git Bash) ister ve
aşağıdaki komutlar PowerShell'de çalıştırılmalı. Linux test edilmedi.

## Hızlı kurulum

```bash
git clone git@github.com:yusufcetn/application-agent.git
cd application-agent

cd backend
uv sync
uv run playwright install chromium
cd ../frontend
npm ci
npm run build
cd ..
```

Kök dizindeki `.env.example` dosyasını `.env` adıyla kopyala ve en az şunları ayarla:

```ini
# claude veya codex: hangi CLI'da oturumun açıksa
LLM_PROVIDER=claude
# Boş bırakırsan CLI'ın varsayılan modeli kullanılır; ya da ör. sonnet / opus
LLM_MODEL=
# Sadece telefondan erişim için: uzun, rastgele bir değer (aşağıya bak)
API_TOKEN=
```

Telefondan erişeceksen bir `API_TOKEN` üret:

```bash
cd backend
uv run python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Uygulamayı başlat:

```bash
cd backend
uv run uvicorn app.main:app --port 8000
```

<http://127.0.0.1:8000> adresini aç. Backend hem API'yi hem derlenmiş arayüzü sunar. API dokümantasyonu
<http://127.0.0.1:8000/docs> adresinde.

Repoyu güncelledikten sonra (`git pull`):

```bash
cd backend && uv sync
cd ../frontend && npm ci && npm run build
```

Ardından backend'i yeniden başlat.

Verilerin `data/app.db` ve `data/packages/` altında durur. Bu klasör git'e girmez, ara sıra yedeğini al.

## Uygulamayı kullanma

Her adım için "neye bakmalı" listesi içeren ayrıntılı ilk çalıştırma rehberi [KURULUM.md](KURULUM.md)
dosyasında. Kısaca:

1. **Profil:** *CV yükle* butonuna bas, çıkan taslağı kontrol et, aktar ve kaydet.
2. **Projeler:** Somut maddeler ve teknolojilerle iki üç proje ekle ya da
   [`contracts/examples/project.json`](contracts/examples/project.json) biçimindeki JSON dosyalarını içe
   aktar. Aynı dosyayı tekrar içe aktarmak mevcut projeleri kopyalamaz, günceller.
3. **Link ile ilan ekle:** Paket üretimini gerçek bir ilanda dene. En kolayı Greenhouse, Lever ve şirket
   kariyer sayfaları. Uyarlanmış CV'de gerçekte yapmadığın bir şey olmadığından emin ol.
4. **Ayarlar:** Hedef pozisyonlar, konumlar, seviye, asgari puan (70 iyi bir başlangıç) ve Greenhouse,
   Lever, Ashby için şirket kısa adları. Kaydet, sonra **Şimdi tara**.
5. **Listeyi incele,** bir ilanı aç, ön yazıyı ve cevapları kopyala, PDF'i aç ve şirketin kendi sitesinden
   başvur. İlanı "başvuruldu" olarak işaretle.

Arayüz şu an Türkçe.

## Yapılandırma

Ayarlar ortam değişkenlerinden ya da kök dizindeki `.env` dosyasından okunur. Yaygın olanlar
[`.env.example`](.env.example) içinde.

| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `LLM_PROVIDER` | `claude` | `claude` veya `codex` |
| `LLM_MODEL` | boş | CLI'a verilen model adı. Boş = CLI'ın varsayılanı |
| `LLM_TIMEOUT_SECONDS` | `300` | Tek bir LLM çağrısının zaman aşımı |
| `LLM_MAX_CONCURRENCY` | `2` | Paralel LLM çağrısı sayısı |
| `CLAUDE_BIN` / `CODEX_BIN` | `claude` / `codex` | CLI `PATH`'te değilse tam yolu |
| `SEARCH_MAX_AGE_DAYS` | `30` | Bundan eski ilanlar yok sayılır |
| `SEARCH_MAX_SCORED_PER_RUN` | `40` | CLI kullanımını sınırlamak için taramada LLM'e gönderilen ilan sayısı |
| `SCHEDULER_ENABLED` | `true` | Backend açıkken günlük taramayı çalıştır |
| `API_TOKEN` | boş | Başka cihazlardan erişim için gerekli. Boş = sadece bu bilgisayar |
| `IMAP_HOST` / `IMAP_PORT` | `imap.gmail.com` / `993` | İş alarmı e-postaları için posta kutusu |
| `IMAP_USER` / `IMAP_PASSWORD` | boş | Posta kutusu girişi. Gmail için [uygulama şifresi](https://myaccount.google.com/apppasswords) kullan |
| `IMAP_FOLDER` | `INBOX` | Okunacak klasör |
| `EMAIL_LOOKBACK_DAYS` | `3` | Alarm e-postaları için geriye dönük gün sayısı |
| `EMAIL_ALERT_SENDERS` | LinkedIn, Kariyer.net, Indeed, Glassdoor | İş alarmı sayılan gönderen alan adları (JSON listesi) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` / `ADZUNA_COUNTRY` | boş / boş / `gb` | Adzuna API bilgileri ve ülke |
| `DATA_DIR` / `DATABASE_URL` | `data/` / `data/` içinde SQLite | Verilerin saklandığı yer |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | İzin verilen kaynaklar (JSON listesi), frontend geliştirmesi için |

Arama tercihleri (pozisyonlar, konumlar, seviye, hariç tutulan kelimeler, asgari puan, CV dili, hangi
kaynakların açık olduğu ve zamanlama) uygulamanın **Ayarlar** sayfasından düzenlenir ve veritabanında
saklanır. Zamanlama bir cron ifadesidir; varsayılan `0 8 * * *` (her gün 08:00).

## Kaynaklar

| Kaynak | Gerekli | Not |
|---|---|---|
| Greenhouse | Ayarlarda şirket kısa adları | `job-boards.greenhouse.io/<ad>` → `<ad>` |
| Lever | Ayarlarda şirket kısa adları | `jobs.lever.co/<ad>` → `<ad>` |
| Ashby | Ayarlarda şirket kısa adları | `jobs.ashbyhq.com/<ad>` → `<ad>` |
| RemoteOK | hiçbir şey | varsayılan olarak açık |
| Remotive | hiçbir şey | varsayılan olarak açık |
| Arbeitnow | hiçbir şey | varsayılan olarak açık |
| Adzuna | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | varsayılan olarak kapalı |
| İş alarmı e-postaları | `IMAP_USER`, `IMAP_PASSWORD` | varsayılan olarak kapalı. LinkedIn, Kariyer.net, Indeed, Glassdoor |

Şirket kariyer sayfaları genellikle en alakalı ilanları getirir; ilgilendiğin şirketlerin kısa adlarını ekle.

**İş alarmı e-postaları.** Posta kutusu **salt okunur** açılır: hiçbir e-posta okundu olarak
işaretlenmez, silinmez ya da gönderilmez; her e-posta bir kez işlenir. Alarm e-postaları yalnızca kısa bir
özet içerir, bu yüzden tam metin paket hazırlanırken ilan sayfasından alınır. Bir site bunu giriş
ekranıyla engellerse paket sebebi gösterir; ilan metnini yapıştırıp paketi yeniden oluşturabilirsin.

**Zamanlayıcı** yalnızca backend çalışırken işler. Bilgisayar zamanlanan saatte uykudaysa, uyandıktan sonra
12 saat içinde bir kez çalışır.

## Telefondan kullanım

Telefonun, kendi bilgisayarındaki backend'e [Tailscale](https://tailscale.com) üzerinden bağlanır. Backend
internete ya da ev ağına açılmaz; yalnızca kendi Tailscale cihazların ulaşabilir.

1. Bilgisayara ve telefona Tailscale'i kur, aynı hesapla giriş yap.
2. `.env` dosyasına uzun, rastgele bir `API_TOKEN` yaz, frontend'i derle ve backend'i başlat
   ([Hızlı kurulum](#hızlı-kurulum)).
3. Başka bir terminalde, tailnet içinde HTTPS ile yayınla:
   ```bash
   tailscale serve --bg 8000
   ```
   Komut `https://<bilgisayar-adın>.<tailnet>.ts.net` gibi bir adres yazar. Durumu `tailscale serve status`
   ile gör; kapatmak için `tailscale serve --https=443 off`.
4. Telefonda Tailscale açıkken bu adresi Chrome'da aç, `API_TOKEN` değerini bir kez gir, sonra Chrome
   menüsünden **Uygulamayı yükle** (ya da **Ana ekrana ekle**) seç. Gerçek bir uygulama gibi tam ekran açılır.

**`tailscale funnel` kullanma.** Funnel adresi herkese açar; `serve` ise özel tutar. `API_TOKEN` boşken
Tailscale üzerinden gelen istekler reddedilir (HTTP 403), yani anahtarı ayarlamayı unutsan bile veriler
kapalı kalır. Telefon yalnızca bilgisayar açıkken, uyanıkken ve backend çalışırken bağlanabilir.

## Demo modu (LLM gerekmez)

Arayüzü LLM ya da gerçek verin olmadan denemek için ayrı bir demo veritabanı oluştur. Profil, projeler,
ayarlar, bir tarama ve farklı durumlarda yedi ilan oluşturur (gerçek PDF'li hazır paket, hatalı paket,
paketsiz, başvurulmuş, mülakat, manuel).

macOS / Linux:

```bash
cd backend
export DATA_DIR=../data-demo DATABASE_URL=sqlite:///../data-demo/app.db
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):

```powershell
cd backend
$env:DATA_DIR="../data-demo"; $env:DATABASE_URL="sqlite:///../data-demo/app.db"
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload --port 8000
```

Frontend'in backend gerektirmeyen bir **mock modu** da var. `frontend/.env.development.local` dosyasına
`VITE_USE_MOCK=true` yaz ve Vite'ı yeniden başlat. Bkz. [frontend/README.md](frontend/README.md).

## Geliştirme ve testler

Backend'i ve frontend geliştirme sunucusunu iki terminalde çalıştır:

```bash
# terminal 1
cd backend
uv run uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
npm ci
npm run dev
```

<http://localhost:5173> adresini aç. `/api` istekleri 8000 portundaki backend'e yönlendirilir.

```bash
cd backend && uv run pytest        # backend testleri
cd frontend && npm test            # frontend testleri
cd frontend && npm run build       # tip kontrolü ve üretim derlemesi
```

Backend testleri gerçek bir CLI çağırmaz; sahte script'lerle çalışır. Daha fazla ayrıntı:
[backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md),
[frontend/TESTING.md](frontend/TESTING.md) ve tasarım notları [frontend/DESIGN.md](frontend/DESIGN.md).
Projenin ilk planı ve API sözleşmesi [plan.md](plan.md) dosyasında.

## Klasör yapısı

| Yol | İçerik |
|---|---|
| `backend/app/api/` | HTTP endpoint'leri (profil, projeler, ilanlar, arama, ayarlar) |
| `backend/app/llm/` | LLM çalıştırıcı, CV içe aktarma, ilan çıkarma, puanlama, uyarlama |
| `backend/app/sources/` | İlan kaynakları ve kaynak kaydı |
| `backend/app/search/` | Ön filtre, arama akışı, zamanlayıcı |
| `backend/app/jobs/` | İlan sayfalarını indirme ve normalleştirme |
| `backend/app/render/` | CV HTML şablonu ve PDF üretimi |
| `backend/app/services/` | Paket üretim akışı |
| `backend/scripts/` | Demo veri oluşturma |
| `backend/tests/` | Backend testleri |
| `frontend/src/` | React sayfaları, API istemcisi, mock API |
| `contracts/examples/` | API sözleşmesi örnek JSON'ları |
| `profile.example/` | Örnek profil ve proje formatı |

## Gizlilik ve güvenlik

- **Verilerin yerel kalır.** Veritabanı ve üretilen dosyalar git'e girmeyen `data/` altındadır; `.env`,
  `profile/` ve `profile*.zip` de öyle. Kişisel CV ve proje dosyalarını `profile/` içinde tut.
- **Bilgisayarından çıkanlar:** Claude ya da Codex CLI'a giden metin (puanlama ve uyarlama için profilin ve
  ilan) ile ilan kaynaklarına ve ilan sayfalarına yapılan normal web istekleri.
- **API anahtarı saklanmaz.** LLM erişimi, zaten sahip olduğun CLI oturumudur. `.env` içindeki tek gizli
  değerler isteğe bağlıdır: telefon erişim anahtarı, posta kutusu uygulama şifresi ve Adzuna anahtarları.
- **Göndermeden önce her şeyi oku.** LLM çıktısı yanlış olabilir. CV'yi, ön yazıyı ve cevapları gerçeğe göre
  kontrol et ve yanlış olanı düzelt. Gönderdiğin şeyin sorumluluğu sende.
- **Kullandığın sitelere saygı göster.** Açtığın kaynakların kullanım koşullarına bak ve tarama sıklığını
  makul tut.

`.env` dosyanı asla commit'leme. Bir anahtar ya da şifre sızarsa değiştir.

## Sorun giderme

| Belirti | Sebep ve çözüm |
|---|---|
| CLI için "komutu bulunamadı" (HTTP 503) | CLI kurulu değil ya da `PATH`'te değil. `.env` içinde `CLAUDE_BIN` / `CODEX_BIN` ile tam yolunu ver |
| "Failed to authenticate" (HTTP 502) | CLI oturumu kapanmış. `claude` çalıştırıp `/login` yap (ya da `codex login`) |
| Telefonda "Uzaktan erişim için API_TOKEN ayarlanmalı" | `API_TOKEN` boş ya da ayarladıktan sonra backend yeniden başlatılmamış |
| Telefonda anahtar ekranı sürekli geri geliyor | `API_TOKEN` değişmiş. Yeni anahtarı gir |
| Telefonda HTTP 502 | Backend kapalı, Tailscale hâlâ açık. Backend'i başlat |
| Paket hazırlanamadı | Sebep altında yazar. İlan metni okunamadıysa metni yapıştır ve yeniden oluştur |
| Port 8000 kullanımda | `--port 8001` ile başlat ve `tailscale serve --bg 8001` kullan |

## Katkı

Issue ve pull request'ler memnuniyetle karşılanır. Pull request açmadan önce backend testlerini, frontend
testlerini ve `npm run build` komutunu çalıştır. Lütfen commit'lere kişisel veri, CV, `.env` dosyası ya da
anahtar koyma.

## Lisans

[MIT](LICENSE)
