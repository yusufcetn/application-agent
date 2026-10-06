# Application Agent — Proje Planı

## 1. Amaç

Kullanıcının CV ve proje bilgilerini tek yerde tutan, kriterlere uyan iş ilanlarını otomatik bulan,
her ilanı profile göre puanlayan ve her ilan için **başvuru paketi** hazırlayan bir sistem:

- İlana göre uyarlanmış CV (PDF)
- İlana özel ön yazı
- Başvuru formunda çıkabilecek sorulara hazır cevaplar
- Uyum analizi: puan, eşleşen ve eksik yetenekler, öne çıkarılan projeler

Başvuruyu kullanıcı **manuel** yapar. Sistem form göndermez.

## 2. Mimari

```
┌──────────────────────┐   REST/JSON    ┌──────────────────────────────────────────┐
│  frontend (React)    │ ─────────────▶ │  backend (FastAPI)                       │
│  - Profil editörü    │                │  ├─ api/        HTTP katmanı             │
│  - İlan listesi      │ ◀───────────── │  ├─ sources/    ilan kaynakları          │
│  - Başvuru paketi    │                │  ├─ llm/        puanlama, uyarlama, yazı │
│  - Ayarlar           │                │  ├─ render/     CV → PDF                 │
└──────────────────────┘                │  ├─ scheduler/  günlük otomatik tarama   │
                                        │  └─ db/         SQLite                   │
                                        └──────────────────────────────────────────┘
```

İki taraf arasındaki **tek bağımlılık API sözleşmesi** (bölüm 5). Sözleşme sabit kaldığı
sürece iki kişi birbirini beklemeden çalışabilir.

## 3. Teknoloji

| Katman | Seçim |
|---|---|
| Frontend | React + TypeScript + Vite, TanStack Query, Tailwind |
| Backend | Python 3.12, FastAPI, Pydantic, SQLModel/SQLite |
| LLM | Claude Code CLI (`claude -p`) veya Codex CLI (`codex exec`), JSON şemalı çıktı. Abonelik kullanılır, API anahtarı gerekmez. Seçim `.env` içindeki `LLM_PROVIDER` ile yapılır |
| PDF | HTML/Jinja2 şablon + Playwright (Chromium) ile PDF (ATS uyumlu, tek kolon). WeasyPrint Windows'ta GTK kurulumu istediği için tercih edilmedi |
| İlan çekme | httpx (API'ler), gerekirse Playwright (ilan sayfası okuma) |
| Zamanlama | APScheduler (her sabah tarama) |

Hem macOS hem Windows'ta çalışmalı: dosya yolları için `pathlib`, metin dosyaları için açıkça `encoding="utf-8"`,
sadece Unix'e özgü araç ve script kullanılmaz.

Portlar: backend `http://localhost:8000`, frontend `http://localhost:5173`.
Frontend `/api` isteklerini Vite proxy ile backend'e yönlendirir.

## 4. Görev Dağılımı

| Alan | Sorumlu | Klasör |
|---|---|---|
| UI | **Arkadaş (B)** | `frontend/` |
| Backend + LLM + ilan kaynakları | **Yusuf (A)** | `backend/` |
| API sözleşmesi + örnek JSON'lar | **Ortak**, değişiklik iki tarafın onayıyla | `contracts/` |

### 4.1 Yusuf (A): Backend + LLM

**Faz 1: İskelet ve profil**
- [x] FastAPI iskeleti, `/api/health`, CORS, `.env` yönetimi
- [x] Pydantic modelleri (`contracts/examples` ile birebir uyumlu)
- [x] SQLite şeması: profile, project, settings (job ve package Faz 2'de)
- [x] `GET/PUT /api/profile`, `/api/projects` CRUD, `GET/PUT /api/settings`
- [x] `POST /api/profile/import`: yüklenen CV (PDF/DOCX/TXT) → LLM ile profile JSON
- [x] LLM katmanı: Claude Code / Codex CLI üzerinden yapılandırılmış çıktı (`app/llm/runner.py`)

**Faz 2: CV üretimi**
- [x] Jinja2 CV şablonu + Playwright ile PDF (TR/EN başlıklar)
- [x] LLM: ilana göre deneyim/proje seçimi ve madde yeniden yazımı (**uydurma yok**: firma, tarih, eğitim profilden gelir; profilde olmayan id ve yetenekler kodda elenir)
- [x] LLM: ön yazı, olası soru-cevaplar, uyum puanı ve analiz (tek çağrı)
- [x] İlan sayfası okuma: önce HTTP, JS ile yüklenen sayfalarda Chromium; schema.org JobPosting verisi kullanılır
- [x] `/api/jobs` uçları: liste/filtre, detay, link ile ekleme (tekrar eden link aynı ilanı döner), PATCH, paket üretimi, paket ve PDF indirme

**Faz 3: İlan bulma**
- [x] Kaynak arayüzü: `JobSource.fetch(settings) -> list[RawJob]` (`app/sources/`)
- [x] Greenhouse / Lever / Ashby (şirket listesi ayarlardan)
- [x] Remote siteler (RemoteOK, Remotive, Arbeitnow)
- [x] Adzuna (API anahtarı ile; açıklamalar kısa olduğu için paket üretirken ilan sayfası okunur)
- [x] Tekilleştirme: normalize edilmiş URL; puanlanıp elenen ilanlar `seen_posting` tablosunda tutulur, tekrar puanlanmaz
- [x] Ücretsiz ön filtre: rol, hariç kelimeler, konum/remote, son 30 gün; profil yetenekleriyle örtüşmeye göre sıralama
- [x] LLM ile toplu uyum puanı (8'li gruplar, tarama başına en fazla 40), seviye filtresi, eşik üstündekiler için otomatik paket
- [x] `POST /api/search/run` + APScheduler ile günlük çalıştırma (sadece sunucu açıkken; bilgisayar uykudaysa 12 saat içinde telafi eder)

**Faz 4: İyileştirme**
- [x] İş alarmı e-postaları (LinkedIn, Kariyer.net, Indeed, Glassdoor): IMAP ile okunur, ilanları LLM çıkarır; her e-posta bir kez işlenir, posta kutusu salt okunur açılır
- [x] Paket hatalarında sebep (`package_error`); sayfası okunamayan ilanlara metin yapıştırıp paketi yeniden oluşturma
- [x] Eski veritabanlarına yeni sütunların otomatik eklenmesi
- [x] LLM çağrılarında eşzamanlılık sınırı (`LLM_MAX_CONCURRENCY`, varsayılan 2)

### 4.2 Arkadaş (B): Frontend

Ekranların ayrıntılı tasarım brifi: [frontend/DESIGN.md](frontend/DESIGN.md)

**Faz 1: İskelet ve mock**
- [ ] Vite + React + TS + Tailwind + TanStack Query kurulumu
- [ ] API client katmanı (`src/api/`); tipler `contracts/examples` yapısına göre
- [ ] Mock modu: `VITE_USE_MOCK=true` iken `contracts/examples/*.json` dönülür (MSW önerilir)
- [ ] Layout + sayfa yönlendirme

**Faz 2: Profil**
- [ ] Profil düzenleme: kişisel bilgi, deneyim, eğitim, yetenekler
- [ ] Proje listesi + ekle/düzenle/sil
- [ ] CV yükleme (import) ekranı: yükle, çıkan profili kontrol et, kaydet

**Faz 3: İlanlar**
- [ ] İlan listesi: puan, firma, pozisyon, konum, durum; filtre ve sıralama
- [ ] "Link ile ilan ekle" formu
- [ ] "Şimdi tara" butonu + çalışma durumu (polling)

**Faz 4: Başvuru paketi**
- [ ] İlan detay: ilan metni | analiz (puan, eşleşen/eksik yetenekler)
- [ ] CV PDF önizleme + indirme
- [ ] Ön yazı ve cevaplar, her biri için kopyala butonu
- [ ] Durum değiştirme: başvurdum / geç / mülakat / red / teklif
- [ ] Ayarlar sayfası: hedef roller, konum, seviye, eşik puan, şirket listesi

**Faz 5: Telefon (PWA)**: ayrıntılar [frontend/DESIGN.md](frontend/DESIGN.md) bölüm 11
- [ ] `npm run build` çıktısı `frontend/dist`; backend bunu aynı adresten sunar (`/api` dışındaki her yol `index.html`'e düşer)
- [ ] Web app manifest + ikonlar (192/512 px) + minimal service worker → "Ana ekrana ekle"
- [ ] Erişim anahtarı ekranı (`/auth/status`, `/auth/login`), 401'de bu ekrana dönüş
- [ ] Mobil görünüm: ilan listesi kart, ilan detayı, kopyala butonları, PDF indirme

## 5. API Sözleşmesi

Tüm yollar `/api` ile başlar. JSON, tarihler ISO 8601 (UTC). Hata formatı:
`{ "detail": "açıklama" }`. Örnek gövdeler `contracts/examples/` altında.

| Metot | Yol | Açıklama | Gövde / Yanıt |
|---|---|---|---|
| GET | `/health` | Sağlık kontrolü | `{ "status": "ok" }` |
| GET | `/profile` | Profili getir | `profile.json` |
| PUT | `/profile` | Profili güncelle | `profile.json` → `profile.json` |
| POST | `/profile/import` | CV dosyasından profil çıkar (multipart `file`) | → `profile.json` (kaydetmez, önizleme) |
| GET | `/projects` | Projeler | `project.json[]` |
| POST | `/projects` | Proje ekle | `project.json` (id'siz) → `project.json` |
| PUT | `/projects/{id}` | Proje güncelle | `project.json` → `project.json` |
| DELETE | `/projects/{id}` | Proje sil | → 204 |
| POST | `/projects/import` | JSON dosyalarından toplu proje (multipart `files`, birden çok; dosya başına tek proje ya da liste) | → `{ "created": project[], "updated": project[], "errors": [{ "file", "message" }] }` |
| GET | `/jobs?status=&min_score=&q=` | İlan listesi | `job.json[]` (description hariç olabilir) |
| GET | `/jobs/{id}` | İlan detayı | `job.json` |
| POST | `/jobs/manual` | Link ile ilan ekle | `{ "url": "..." }` → `job.json` |
| PATCH | `/jobs/{id}` | Durum/not/ilan metni güncelle | `{ "status"?: ..., "notes"?: ..., "description"?: ... }` → `job.json` |
| POST | `/jobs/{id}/package` | Paket üret (asenkron) | → 202 `{ "job_id": "...", "package_status": "generating" }` |
| GET | `/jobs/{id}/package` | Paketi getir | `package.json` (404 = henüz yok) |
| GET | `/jobs/{id}/cv.pdf` | Uyarlanmış CV | `application/pdf` |
| POST | `/search/run` | İlan taramasını başlat | → 202 `search_run.json` |
| GET | `/search/runs?limit=` | Son taramalar (yeniden eskiye) | `search_run.json[]` |
| GET | `/search/runs/{id}` | Tarama durumu | `search_run.json` |
| GET | `/auth/status` | Erişim anahtarı gerekli mi, giriş yapılmış mı | `{ "token_required", "authenticated" }` |
| POST | `/auth/login` | Anahtarla giriş (çerez) | `{ "token": "..." }` → 204 |
| POST | `/auth/logout` | Çıkış | → 204 |
| GET | `/settings` | Arama ayarları | `settings.json` |
| PUT | `/settings` | Ayarları güncelle | `settings.json` → `settings.json` |

**Enum'lar**
- `job.status`: `new` · `applied` · `skipped` · `interview` · `rejected` · `offer`
- `job.package_status`: `none` · `generating` · `ready` · `failed`
- `search_run.status`: `running` · `done` · `failed`
- `job.source`: `manual` · `greenhouse` · `lever` · `ashby` · `remoteok` · `remotive` · `arbeitnow` · `adzuna` · `email`

**Ayrıntılar**
- `GET /profile` ve `GET /settings` veri yokken boş/varsayılan nesne döner (404 değil).
- `GET /jobs` listesinde `description` boş gelir; metin için `GET /jobs/{id}`. `status` birden çok verilebilir: `?status=new&status=applied`.
- `POST /jobs/manual` gövdesi `{ "url": "...", "text"?: "..." }`. `text` isteğe bağlı: sayfa okunamazsa (LinkedIn giriş ekranı gibi) kullanıcı ilan metnini yapıştırır.
  Yeni ilanda 201, aynı link daha önce eklendiyse 200 ve mevcut ilan döner. İlan okunup LLM ile ayrıştırıldığı için **15–30 sn sürebilir**.
  Sayfada ilan bulunamazsa 422. Profil doluysa ve `auto_package` açıksa paket hemen `generating` durumuyla başlar.
- `POST /projects/import`: aynı `id`'ye ya da aynı ada (büyük/küçük harf farkı gözetmeden) sahip proje varsa güncellenir,
  yoksa eklenir; dosyadaki `id` korunur. Hatalı dosya ya da kayıt diğerlerini durdurmaz, `errors` içinde Türkçe sebebiyle döner.
- `POST /jobs/{id}/package` profil boşken 409 döner.
- `package_status: failed` olduğunda `job.package_error` kullanıcıya gösterilecek Türkçe sebebi içerir, aksi halde `null`.
  E-posta alarmından gelen ilanlarda sadece kısa bir özet olur; paket üretilirken ilan sayfası okunur. Sayfa okunamazsa
  (ör. LinkedIn giriş ekranı) hata "İlanın tam metni okunamadı..." olur. Arayüz o zaman ilan metnini yapıştırma alanı
  göstermeli: `PATCH /jobs/{id}` ile `description` gönderip `POST /jobs/{id}/package` ile yeniden denemeli.
- `settings.sources.email_alerts` (bool): iş alarmı e-postalarını tarama. E-posta bilgileri `.env` dosyasında, arayüzde değil.
- **Erişim anahtarı (telefon için):** `.env` içinde `API_TOKEN` tanımlıysa `/api/health` ve `/api/auth/*` dışındaki
  her istek anahtar ister, yoksa **401**. `API_TOKEN` yokken Tailscale üzerinden gelen istek **403** alır.
  - `GET /auth/status` → `{ "token_required": bool, "authenticated": bool }`. Arayüz açılışta bunu çağırır;
    `token_required && !authenticated` ise anahtar giriş ekranını gösterir.
  - `POST /auth/login` `{ "token": "..." }` → 204 ve oturum çerezi (1 yıl). Yanlış anahtar 401.
    Çerez sayesinde `cv.pdf` gibi düz linkler de çalışır; arayüzün header eklemesine gerek yok.
  - `POST /auth/logout` → 204. Herhangi bir istek 401 dönerse arayüz anahtar ekranına dönmeli.
- LLM hataları: CLI kurulu değilse 503, CLI hatası (ör. oturum kapalı) 502.
- `POST /search/run`: yeni tarama 202; zaten çalışan varsa 200 ve o tarama döner; profil boşsa 409.
  Tarama 1–3 dk sürer. `status: done` olduktan sonra eşik üstü ilanların paketleri arka planda hazırlanmaya devam eder.
- `search_run.error` `done` durumunda da dolu olabilir: bir kaynak okunamadıysa uyarıdır (ör. "Bazı kaynaklar okunamadı: remotive: timeout").
- Kenar çubuğundaki "Son tarama" için `GET /search/runs?limit=1`.
- `PUT /settings` geçersiz cron ifadesinde 422 döner. `seniority` değerleri: `intern`, `junior`, `mid`, `senior`, `lead`.
- Paket üretimi Sonnet ile yaklaşık 1 dakika sürer.

Uzun süren işlemler (paket üretimi, tarama) 202 döner. Frontend ilgili GET'i 2–3 sn aralıkla
yoklar ve durum `ready`/`done`/`failed` olunca durur.

## 6. Klasör Yapısı

```
Application-agent/
├── plan.md
├── README.md
├── contracts/examples/      # sözleşme örnekleri: frontend mock + backend test fixture
├── profile.example/         # örnek profil (gerçek profil repoya girmez)
├── backend/
│   ├── app/{api,sources,llm,render,scheduler,db}/
│   ├── templates/cv.html
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/{api,pages,components,mocks}/
│   └── package.json
└── data/                    # SQLite + üretilen PDF'ler (gitignore)
```

## 7. Çalışma Kuralları

- **Branch:** `main` korumalı. İşler `feat/ui-...` veya `feat/be-...` branch'lerinde yapılır, PR ile birleşir.
- **Sözleşme değişikliği:** `contracts/` veya plan.md bölüm 5'e dokunan PR'ı iki taraf da onaylar.
  Önce sözleşme PR'ı, sonra implementasyon.
- **Klasör sahipliği:** A `frontend/`, B `backend/` klasörüne dokunmaz (gerekirse issue açar).
  Böylece merge çakışması neredeyse olmaz.
- **Gizli bilgi:** API anahtarları `.env` dosyasında durur, repoya girmez. `.env.example` güncel tutulur.
- **Kişisel veri:** gerçek CV ve profil `data/` altında kalır (gitignore). Repoda sadece `profile.example/` bulunur.
- **LLM kuralı:** üretilen CV sadece profildeki gerçek bilgiyi kullanır. Deneyim, yetenek veya rakam uydurulmaz.

## 8. Kilometre Taşları

| Hedef | A (backend) | B (frontend) |
|---|---|---|
| M1: Birbirinden bağımsız çalışma | İskelet + profil API | İskelet + mock + profil sayfası |
| M2: İlk uçtan uca akış | Link ile ilan → paket → PDF | İlan detay + paket ekranı, gerçek API'ye bağlanma |
| M3: Otomatik bulma | Kaynaklar + puanlama + scheduler | İlan listesi, filtreler, tarama butonu, ayarlar |
| M4: Cila | Maliyet/hata yönetimi | Durum takibi, UX iyileştirmeleri |

## 9. Açık Sorular

- Hedef roller, konum (TR / yurt dışı / remote) ve seviye?
- CV dili: TR, EN veya ilanın diline göre otomatik?
- Adzuna/SerpAPI gibi ücretli ya da anahtarlı kaynaklar kullanılacak mı?
- Tek kullanıcılı mı (lokal), ileride çok kullanıcılı mı? (Şimdilik: tek kullanıcı, auth yok)
