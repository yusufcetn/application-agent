# Kurulum ve ilk gerçek test

Bu rehber, uygulamayı kendi bilgisayarında kendi verinle kurmak, uçtan uca test etmek ve telefona
uygulama olarak yüklemek için. Herkes kendi kopyasını çalıştırır: veriler, LLM aboneliği ve e-posta
bilgileri kişiye özeldir, hiçbiri paylaşılmaz.

Geliştirme ve demo veriyle test için [frontend/README.md](frontend/README.md) ve
[backend/README.md](backend/README.md) dosyalarına bak.

## 1. Gerekenler

| Araç | Neden | Kontrol |
|---|---|---|
| Git | Repoyu çekmek | `git --version` |
| [uv](https://docs.astral.sh/uv/) | Backend (Python) | `uv --version` |
| Node.js 22 | Arayüzü derlemek | `node --version` |
| Antigravity CLI (varsayılan), Claude Code **veya** Codex CLI, oturum açık | LLM çağrıları (hesabın, API anahtarı yok) | `agy models`, `claude -p "merhaba"` veya `codex exec "merhaba"` |
| Tailscale (bilgisayar + telefon) | Telefondan erişim | `tailscale status` |

Antigravity CLI'ı Windows'ta PowerShell'de `irm https://antigravity.google/cli/install.ps1 | iex` ile kur
(macOS için antigravity.google'daki komut), sonra yeni bir terminal açıp `agy` ile Google hesabınla giriş yap.
Windows'ta Claude Code, Git for Windows (Git Bash) da ister.

## 2. Bir kerelik kurulum

macOS ve Windows'ta komutlar aynı. Windows'ta PowerShell kullan.

```bash
git clone git@github.com:yusufcetn/apply-agent.git
cd apply-agent

cd backend
uv sync
uv run playwright install chromium
cd ../frontend
npm ci
npm run build
cd ..
```

Kök dizindeki `.env.example` dosyasını `.env` adıyla kopyala ve şunları doldur:

```ini
# antigravity, claude veya codex: hangi CLI'da oturumun açıksa
LLM_PROVIDER=antigravity
# Boş bırakırsan antigravity'de gemini-3.8-flash-medium, diğerlerinde CLI'ın varsayılanı kullanılır
LLM_MODEL=
# Telefondan erişim için uzun, rastgele bir değer (aşağıdaki komutla üret)
API_TOKEN=
```

`API_TOKEN` üretmek için:

```bash
cd backend
uv run python -c "import secrets; print(secrets.token_urlsafe(24))"
```

## 3. Çalıştırma

```bash
cd backend
uv run uvicorn app.main:app --port 8000
```

Tarayıcıda `http://127.0.0.1:8000` adresini aç. Arayüz ve API aynı adreste. Bu terminal açık kaldığı
sürece uygulama çalışır, her sabah 08:00'deki otomatik tarama da sadece o sırada yapılır.

**Windows'ta otomatik başlatma:** terminal açık tutmak yerine backend'i oturum açılınca başlatan ve
her sabah 07:55'te bilgisayarı uykudan uyandıran bir Görev Zamanlayıcı görevi kurabilirsin:

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\windows_autostart.ps1
```

Çıktı `data\backend.log` dosyasına yazılır. Uyandırma için güç seçeneklerinde "Uyandırma zamanlayıcılarına
izin ver" açık olmalı; tamamen kapalı bilgisayar açılmaz. Kaldırmak için sona `-Remove` ekle. Görev
çalışırken backend'i ayrıca terminalden başlatma, port çakışır.

Repoyu güncelledikten sonra (`git pull`):

```bash
cd backend && uv sync
cd ../frontend && npm ci && npm run build
```

Ardından backend'i yeniden başlat.

**Veriler:** gerçek verin `data/app.db` ve `data/packages/` altında. Bu klasör git'e girmez, ara sıra yedeğini al.

## 4. İlk gerçek test (sırayla)

Her adımda "Bak" kısmındakileri kontrol et, beklenmedik bir şey olursa not al (bkz. bölüm 6).

### 4.1 Profil: CV yükle

Profil sayfasında **CV yükle** butonuna bas ve PDF, DOCX, TXT ya da MD dosyanı seç. Okuma 10–30 sn sürer.
Çıkan taslağı kontrol et, **Taslağa aktar**, ardından **Kaydet**.

- **Bak:** deneyim, tarih ve yetenekler doğru çıkarılmış mı? CV'de olmayan bir şey eklenmiş mi?
  Türkçe karakterler bozuk mu? Sayfayı yenile, bilgiler kalıyor mu?

### 4.2 Projeler

Projeler sayfasında en az 2–3 projeni ekle: somut maddeler ve kullandığın teknolojilerle.
Sistem ilana en uygun olanları CV'ye koyar.

Projelerin JSON dosyası olarak hazırsa **JSON içe aktar** ile hepsini birden seç. Format
[contracts/examples/project.json](contracts/examples/project.json) ile aynı; bir dosyada tek proje ya da bir
liste olabilir. Aynı `id` ya da aynı ada sahip proje varsa kopyalanmaz, güncellenir. Yani dosyaları
düzenleyip tekrar içe aktarmak güvenli. Kişisel dosyalarını `profile/` klasöründe tutarsan git'e girmez.

### 4.3 Link ile tek ilan

**İlanlar → Link ile ekle** ile gerçek bir ilan linki ver. Greenhouse, Lever veya bir şirketin kariyer
sayfası en kolayı. İlan 15–30 sn'de okunur, paket yaklaşık 1 dk'da hazırlanır.

- **Bak (en önemli test):**
  - CV PDF'inde **senin yapmadığın bir şey** var mı? Uydurma deneyim, rakam, teknoloji, "ekiplerle
    çalıştım" gibi süsleme olmamalı.
  - CV dili ilanın diline uyuyor mu? Pozisyon ve bölüm adları çevrilmiş mi?
  - Ön yazı ve hazır cevaplar bu şirkete ve role özel mi?
  - Maaş gibi bilinmeyen sorular doldurulacak şablon olarak mı bırakılmış?
  - Puan ve gerekçe mantıklı mı?
- LinkedIn linki okunamazsa: ilan metnini kopyala ve modalda **İlan metnini yapıştır** alanına yapıştır.

### 4.4 Ayarlar ve ilk tarama

Ayarlar sayfasında şunları gir:

- Hedef pozisyonlar (ör. "Backend Developer")
- Konumlar (ör. "İstanbul", "Remote")
- Seviye
- Minimum puan (70 iyi bir başlangıç)
- **Şirket kısa adları.** İstanbul için en çok ilanı bu getirir. Greenhouse, Lever veya Ashby kullanan
  şirketlerin kariyer sayfası adresinden alınır: `job-boards.greenhouse.io/firma` → `firma`,
  `jobs.lever.co/firma` → `firma`, `jobs.ashbyhq.com/firma` → `firma`.

Kaydet, sonra **Şimdi tara**. İlanlar 10'arlı gruplar halinde puanlanır ve her grup bitince listeye
düşer; kenar çubuğunda kaç ilanın puanlandığı görünür. Hızlı kaynaklar 1–3 dk sürer, web araması açıksa
arkada birkaç dakika daha devam eder. Eşik üstündeki ilanların paketleri tarama sürerken sırayla
hazırlanır, her biri 1–3 dk.

- **Bak:** bulunan ilanlar gerçekten hedefine uygun mu? Puan gerekçeleri mantıklı mı?
  "Hiçbir kaynak okunamadı" gibi bir uyarı çıktı mı? Aynı taramayı tekrar çalıştırınca eski ilanlar
  tekrar puanlanmamalı, bu yüzden ikinci tarama hızlı biter.

### 4.5 (İsteğe bağlı) LinkedIn ve Kariyer.net alarm e-postaları

Gmail'de 2 adımlı doğrulamayı aç ve https://myaccount.google.com/apppasswords adresinden bir uygulama
şifresi oluştur. `.env` dosyasına şunları ekle:

```ini
IMAP_USER=adresin@gmail.com
IMAP_PASSWORD=uygulama-şifresi
```

Backend'i yeniden başlat, Ayarlar'da **E-posta alarmları** seçeneğini aç ve tara. Posta kutusu salt
okunur açılır: hiçbir e-posta okundu olarak işaretlenmez ya da silinmez.

Son `EMAIL_LOOKBACK_DAYS` günün (varsayılan 14) alarm e-postalarındaki ilanlar her taramada o günkü
ayarlarınla yeniden filtrelenir. Sonradan bir pozisyon eklersen daha önce okunmuş e-postalardaki uygun
ilanlar da gelir. Her e-posta yapay zekâya yalnızca bir kez okutulur; daha önce kaydedilmiş ya da
puanlanıp elenmiş ilanlar tekrar puanlanmaz.

- **Bak:** alarm e-postalarındaki ilanlar "E-posta alarmı" kaynağıyla listeye düştü mü?

### 4.6 (İsteğe bağlı) Web araması

Ayarlar > İlan kaynakları'nda **Web araması**'nı aç. Yapay zekâ ajanı ayarlarındaki roller ve konumlarla
hedefli aramalar yapar (şirket kariyer sayfaları, Youthall, Kariyer.net, LinkedIn linkleri). Bulduğu bir
şirket Greenhouse, Lever, Ashby, Workable ya da SmartRecruiters kullanıyorsa o şirketin bütün açık ilanları
bu sitelerin herkese açık API'sinden çekilir ve senin rol/konum filtrenden geçer. Diğer linklerden tek bir
ilana gitmeyenler (logo, liste ya da kariyer ana sayfası) atılır. Bot engelleyen sitelerin (ör. Kariyer.net)
ilanları doğrulanamadığı için web aramasından alınmaz; bunlar için e-posta alarmlarını kullan.
Sadece başvuruya açık olduğu görülen ilanlar listeye girer. LinkedIn'e giriş yapılmaz, sadece link bulmak
için kullanılır. Web araması diğer kaynaklarla aynı anda çalışır, onları bekletmez.

Antigravity kullanıyorsan ajanın sayfa açabilmesi için bir kerelik izin gerekir. Şu içerikle
`~/.gemini/antigravity-cli/settings.json` dosyasını oluştur (Windows'ta `C:\Users\ad\.gemini\...`):

```json
{ "permissions": { "allow": ["read_url(*)", "search_web(*)"] } }
```

Kayıtlı ilanlar her taramada tekrar kontrol edilir: kapananlar "Kapandı" olarak işaretlenir ve listede
gizlenir, yeniden açılanlar geri gelir. LinkedIn ve bot engelleyen sitelerdeki (ör. Kariyer.net) ilanlar
otomatik kontrol edilemez.

### 4.7 (İsteğe bağlı) Sabah raporu

4.5'teki Gmail uygulama şifresi e-posta göndermek için de kullanılır. Ayarlar > Zamanlama'da **Sabah
raporu**'nu aç. Her günlük taramadan sonra yeni ilanlar, başvurmadığın açık ilanlar, son başvurusu
yaklaşanlar ve kapananlar sana e-postayla gelir. **Son taramanın raporunu şimdi gönder** ile hemen dene.

## 5. Telefona uygulama olarak yükleme (Android)

1. `.env` dosyasında `API_TOKEN` dolu olmalı. Değiştirdiysen backend'i yeniden başlat.
2. Backend çalışırken, ayrı bir terminalde:
   ```bash
   tailscale serve --bg 8000
   ```
   Komut `https://<bilgisayar-adın>.<tailnet>.ts.net` gibi bir adres yazar. Durumu görmek için
   `tailscale serve status`. **`tailscale funnel` kullanma**, o adresi herkese açar.
3. Telefonda Tailscale açıkken Chrome'da bu adresi aç ve erişim anahtarını (`API_TOKEN`) bir kez gir.
4. Chrome menüsünden (⋮) **Uygulamayı yükle** seçeneğine dokun. Menüde bu yoksa **Ana ekrana ekle**'yi seç.
   Chrome bu adımda gerçek bir Android uygulaması (WebAPK) oluşturup kurar. Uygulama çekmecesinde
   "Apply" olarak görünür, tam ekran açılır, ayrıca bir APK dosyası indirmen gerekmez.
5. **Test et:**
   - İlan listesi ve ilan detayı açılıyor mu?
   - Ön yazıyı ve cevapları kopyalayabiliyor musun?
   - **PDF'i aç** CV'yi gösteriyor mu?
   - Bilgisayarda backend'i durdur: uygulama "Bilgisayarına ulaşılamıyor" demeli. Backend'i açınca
     **Tekrar dene** çalışmalı.

Telefon, bilgisayar açıkken ve backend çalışırken bağlanır. Laptop uykudaysa uygulama açılmaz.

> **Neden ayrı bir .apk dosyası yok?** Chrome'un kurduğu uygulama zaten bir APK. Elle derlenmiş bir
> APK için Android SDK gerekir ve herkesin Tailscale adresi farklı olduğu için kişiye özel derlemek
> gerekir. Bildirim gibi tarayıcının veremediği bir özellik gerekirse Capacitor ile ayrı APK'ya geçilir.

## 6. Sorun olursa

| Belirti | Sebep ve çözüm |
|---|---|
| "LLM API anahtarı…" ya da "komutu bulunamadı" (503) | CLI kurulu değil ya da backend onu PATH'te bulamıyor. `.env` içinde `ANTIGRAVITY_BIN` / `CLAUDE_BIN` / `CODEX_BIN` ile tam yolunu ver |
| "Claude CLI hatası: Failed to authenticate" (502) | CLI oturumu kapanmış. Terminalde `claude` çalıştırıp `/login` yap |
| Telefonda "Uzaktan erişim için API_TOKEN ayarlanmalı" | `.env` içinde `API_TOKEN` boş ya da backend yeniden başlatılmamış |
| Telefonda anahtar ekranı sürekli geri geliyor | `API_TOKEN` değişmiş; yeni anahtarı gir |
| Telefonda "İstek başarısız oldu (HTTP 502)" | Backend kapalı, Tailscale hâlâ açık. Backend'i başlat |
| Paket "hazırlanamadı" | Sebep altında yazar. İlan metni okunamadıysa metni yapıştır ve **Kaydet ve yeniden oluştur** |
| Port 8000 kullanımda | Otomatik başlatma görevi açık olabilir (`Get-ScheduledTask "Apply Agent"`). Değilse `--port 8001` ile başlat, `tailscale serve --bg 8001` |
| "Antigravity web araçları için izin gerekli" | 4.6'daki `settings.json` dosyasını oluştur |
| Rapor e-postası gelmiyor | `.env` içinde `IMAP_USER` / `IMAP_PASSWORD` dolu mu? Ayarlar'daki **şimdi gönder** düğmesi hatayı gösterir |

Hata bildirirken şunları yaz: ne yaptın, ne bekledin, ne oldu. Varsa backend terminalindeki son satırları
ve ilgili ilanın linkini de ekle.
