# Apply Agent: Arayüz Tasarım Brifi

Bu doküman, uygulamanın arayüzünü tasarlamak için gereken her şeyi anlatır: ürünün ne yaptığı,
hangi ekranların olduğu, her ekranda ne gösterildiği ve görsel yön.
Arayüz dili **Türkçe**.

---

## 1. Ürün ne yapıyor?

Apply Agent, iş arayan **tek bir kişinin** kişisel iş başvuru asistanıdır.

1. Kullanıcı CV bilgilerini ve projelerini bir kez sisteme girer.
2. Sistem her sabah internetteki iş ilanlarını tarar ve kullanıcıya uygun olanları bulur.
3. Her ilana kullanıcıyla ne kadar uyumlu olduğunu gösteren **0–100 arası bir uyum puanı** verir.
4. Uygun ilanların her biri için bir **başvuru paketi** hazırlar:
   - O ilana göre özelleştirilmiş CV (PDF)
   - O ilana özel ön yazı
   - Başvuru formunda çıkabilecek sorulara hazır cevaplar
   - Analiz: eşleşen ve eksik yetenekler, öne çıkarılan projeler, tavsiyeler
5. Kullanıcı paketi açar, CV'yi indirir, metinleri kopyalar ve ilanın sitesine giderek **başvuruyu kendisi yapar**.
   Sonra ilanı "Başvurdum" olarak işaretler.

**Özet:** bu bir iş arama gelen kutusu. Her sabah yeni ilanlar geliyor, her biri başvurmaya hazır bir paketle.

## 2. Kullanıcı ve ana akış

- **Kullanıcı:** iş arayan yazılımcı veya genç profesyonel. Günde 5–20 ilana bakar.
- **Temel ihtiyaç:** "Bugün hangi ilanlara başvurmalıyım?" sorusuna hızlı cevap, sonra en az tıklamayla başvuru.
- **En sık yapılan akış (tasarımın odağı):**
  `Özet sayfası → yüksek puanlı yeni ilan → ilan detayı → CV indir + ön yazı kopyala → "İlana git" → dön, "Başvurdum" işaretle → sıradaki ilan`

Profil ve Ayarlar ekranları nadiren kullanılır, ama ilk kurulumda önemlidir.

## 3. Görsel yön

- **His:** sakin, profesyonel, verimli. Linear, Notion ve Raycast arası bir his. İş arama stresli bir süreç; arayüz düzenli ve güven veren bir yer olmalı.
- **Yoğunluk:** orta. Liste ekranları bilgi yoğun (tablo gibi), detay ekranları ferah ve okunabilir.
- **Renk (güncel yön):** sıcak kâğıt (`#f8f5ef`), kırık beyaz yüzey (`#fffcf7`), koyu mürekkep (`#302c2b`), mürdüm (`#4c343c`) ve ana aksiyon için toprak kırmızısı (`#864b3e`). Puan ve durum renkleri aşağıdaki anlamlarını korur.
- **Tipografi (güncel yön):** arayüz ve uzun metinlerde DM Sans; önemli başlıklar ve sayısal vurgu için Fraunces. Ön yazı ve cevap metinleri rahat satır aralığıyla okunur.
- **Tema:** açık tema ana tasarım. Koyu tema da desteklenecek.
- **Köşeler ve gölgeler:** hafif yuvarlatılmış (8–16px), minimal gölge; bilgi yoğun listelerde ayırıcı çizgiler, odak gerektiren panellerde ince kenarlık kullanılır.
- **İkonlar:** Lucide ikon seti.

### Anlamlı renkler

**Uyum puanı rozeti** (uygulamanın en önemli görsel öğesi):

| Puan | Renk | Anlam |
|---|---|---|
| 80–100 | Yeşil | Çok uygun |
| 60–79 | Sarı/amber | Uygun |
| 0–59 | Gri | Zayıf eşleşme |

**Başvuru durumu etiketi:**

| Durum (API) | Etiket | Renk |
|---|---|---|
| `new` | Yeni | Mavi |
| `applied` | Başvuruldu | Mor |
| `interview` | Mülakat | Turuncu |
| `offer` | Teklif | Yeşil |
| `rejected` | Red | Kırmızı (soluk) |
| `skipped` | Geçildi | Gri |

## 4. Uygulama iskeleti

Masaüstü öncelikli web uygulaması.

- **Sol kenar çubuğu (sabit, ~240px):**
  - Üstte logo + "Apply Agent"
  - Menü: **Özet**, **İlanlar** (yeni ilan sayısı rozetiyle), **Profil**, **Projeler**, **Ayarlar**
  - Altta: son tarama zamanı ("Son tarama: bugün 08:00") ve **"Şimdi tara"** butonu
- **Ana alan:** sayfa başlığı + sağ üstte sayfaya özel aksiyonlar.

## 5. Ekranlar

### 5.1 Özet (ana sayfa)

**Amaç:** "Bugün ne yapmalıyım?" sorusunu tek bakışta cevaplamak.

- **Üstte 4 istatistik kartı:**
  - Bugün bulunan yeni ilan: **12**
  - Paketi hazır, başvuru bekleyen: **5**
  - Bu hafta yapılan başvuru: **8**
  - Mülakat aşamasında: **2**
- **"Bugün öne çıkanlar" listesi:** en yüksek puanlı 5 yeni ilan, büyük ve tıklanabilir satırlar halinde.
  Her satırda puan rozeti, pozisyon, firma, konum, "Paket hazır" göstergesi, sağda "Aç" butonu.
- **"Takiptekiler" bölümü:** durumu Mülakat veya Başvuruldu olan son ilanlar, kompakt liste.
- **Son tarama özeti:** "Bu sabah 57 ilan tarandı, 12 yeni, 5 tanesi eşiğin üstünde."

### 5.2 İlanlar

**Amaç:** tüm ilanları görmek, filtrelemek, sıralamak.

- **Sağ üst aksiyonlar:** "Link ile ilan ekle" (ikincil buton), "Şimdi tara" (ana buton)
- **Filtre çubuğu:** arama kutusu (firma/pozisyon), durum seçimi (çoklu), minimum puan kaydırıcısı, kaynak seçimi
- **Durum sekmeleri:** Tümü · Yeni (12) · Başvuruldu (8) · Mülakat (2) · Geçildi
- **Liste/tablo sütunları:**

  | Puan | Pozisyon & Firma | Konum | Kaynak | Bulunma | Paket | Durum |
  |---|---|---|---|---|---|---|
  | **82** | Backend Engineer · Örnek Firma | Remote (EMEA) | Lever | 2 saat önce | ✓ Hazır | Yeni |
  | **76** | Python Developer · Trendyol | İstanbul | Greenhouse | 5 saat önce | ⟳ Hazırlanıyor | Yeni |
  | **64** | Software Engineer · Getir | İstanbul (Hibrit) | Manuel | Dün | — Yok | Başvuruldu |
  | **91** | Junior Backend Developer · Insider | Remote | Ashby | Dün | ✓ Hazır | Mülakat |

- Satıra tıklayınca İlan Detayı açılır.
- Satırın üzerine gelince hızlı aksiyonlar görünür: "Geç", "Başvurdum".
- Varsayılan sıralama puana göre (yüksekten düşüğe).

**"Link ile ilan ekle" modalı:** tek bir URL alanı + "Ekle ve paket hazırla" butonu.
- Gönderince buton yükleniyor durumuna geçer: "İlan okunuyor…" (sayfa okunup ayrıştırıldığı için **15–30 sn** sürer).
- Başarılı olunca modal kapanır, ilan listenin en üstünde "Hazırlanıyor" durumuyla görünür. Aynı link daha önce
  eklendiyse mevcut ilan açılır.
- Sayfa okunamazsa (ör. LinkedIn giriş ekranı) modal hata mesajını gösterir ve altında bir **"İlan metnini yapıştır"**
  alanı açılır; kullanıcı metni yapıştırıp tekrar gönderir.

### 5.3 İlan Detayı + Başvuru Paketi (en önemli ekran)

**Amaç:** başvuru için gereken her şeyi tek sayfada, en az tıklamayla sunmak.

**Üst başlık alanı:**
- Büyük puan rozeti (82), pozisyon adı (büyük), firma · konum · kaynak · "2 gün önce yayınlandı"
- Sağda: **"İlana git ↗"** (ana buton, yeni sekmede açılır), durum açılır menüsü (Yeni ▾), "Paketi yeniden oluştur" (ikon buton)

**Altında sekmeler:**

1. **Genel Bakış** (varsayılan)
   - Tek cümlelik puan gerekçesi: "Python/FastAPI deneyimi ve API projeleri güçlü eşleşiyor, Kubernetes eksik."
   - İki sütun: **Eşleşen yetenekler** (yeşil çipler: Python, FastAPI, PostgreSQL, Docker) · **Eksik yetenekler** (gri/kırmızı çipler: Kubernetes)
   - **CV'de öne çıkarılanlar:** seçilen proje ve deneyimlerin küçük kartları
   - **Tavsiyeler:** madde listesi ("Mülakatta Kubernetes eksikliğini Docker deneyiminle dengeleyebilirsin.")
   - **Hızlı başvuru kutusu:** 3 adımlık kontrol listesi
     ☐ CV'yi indir · ☐ Ön yazıyı kopyala · ☐ İlana git ve başvur, en altta "Başvurdum olarak işaretle"

2. **CV**
   - PDF önizleme (sayfa görünümünde, gömülü)
   - Üstte: "PDF İndir" butonu, dil etiketi (EN/TR)

3. **Ön Yazı**
   - Okunabilir metin bloğu, sağ üstte **"Kopyala"** butonu (tıklayınca "Kopyalandı ✓" olur)

4. **Hazır Cevaplar**
   - Soru-cevap kartları listesi. Soru kalın başlık, altında cevap, her kartta ayrı "Kopyala" butonu.
   - Örnek: "Why do you want to work at Örnek Firma?", "Describe a project relevant to this role."

5. **İlan Metni**
   - İlanın orijinal açıklaması, okunabilir formatta
   - Altında kullanıcının kendi notları için bir metin alanı

**Paket durumları (sekmelerin içeriği bunlara göre değişir):**
- **Hazırlanıyor:** iskelet (skeleton) yükleme ve "Başvuru paketi hazırlanıyor, yaklaşık 1 dakika…" mesajı
- **Yok:** boş durum illüstrasyonu + "Paket oluştur" butonu
- **Hata:** "Paket oluşturulamadı" başlığı, altında backend'in verdiği sebep (`package_error`, Türkçe) ve "Tekrar dene".
  Sebep ilan metninin okunamaması ise (e-posta alarmından gelen ilanlarda olabilir) bir **"İlan metnini yapıştır"**
  alanı ve "Kaydet ve yeniden oluştur" butonu gösterilir.

### 5.4 Profil

**Amaç:** CV'nin kaynağı olan bilgileri düzenlemek. Uzun bir form sayfası.

- **Üstte banner (profil boşken belirgin, doluyken küçük):** "Mevcut CV'ni yükle, bilgileri otomatik dolduralım" + "CV Yükle" butonu
- Sağ üstte "Kaydet" butonu, kaydedilmemiş değişiklik varsa belirgin hale gelir
- **Bölümler** (her biri kart, sol tarafta bölümler arası atlama menüsü):
  1. **Kişisel bilgiler:** ad soyad, başlık ("Backend Developer"), e-posta, telefon, konum, linkler (GitHub, LinkedIn… eklenebilir liste)
  2. **Özet:** çok satırlı metin
  3. **Deneyim:** eklenebilir/sıralanabilir kartlar. Her kartta firma, pozisyon, konum, başlangıç–bitiş ("Halen çalışıyorum" kutusu), madde listesi, yetenek etiketleri
  4. **Eğitim:** okul, derece, bölüm, tarih aralığı, not ortalaması
  5. **Yetenekler:** üç grup (Diller, Framework'ler, Araçlar), her biri etiket girişi
  6. **Yabancı diller:** dil + seviye
  7. **Sertifikalar:** ad, veren kurum, tarih

**CV Yükleme akışı (modal, 3 adım):**
1. Dosyayı sürükle-bırak alanı (PDF/DOCX)
2. "CV okunuyor…" yükleme durumu
3. Çıkarılan bilgilerin önizlemesi, bölüm bölüm. "Profilime aktar" / "İptal"

### 5.5 Projeler

**Amaç:** kişisel projeleri yönetmek. Sistem ilana göre bunlardan en alakalı olanları CV'ye koyar.

- Sağ üstte "Proje ekle"
- **Kart ızgarası (2–3 sütun):** her kartta proje adı, rol, kısa özet, teknoloji etiketleri, link ikonları, "Öne çıkan" yıldızı
- Karta tıklayınca **sağdan açılan panel (drawer)** ile düzenleme: ad, rol, özet, madde listesi, teknolojiler, linkler, tarih aralığı, "öne çıkan" anahtarı, silme butonu
- Boş durum: "Henüz proje yok. Projelerin, ilana özel CV'lerde öne çıkarılır." + "İlk projeni ekle"

### 5.6 Ayarlar

**Amaç:** sistemin hangi ilanları arayacağını belirlemek. Tek sütunlu form, gruplanmış kartlar.

1. **Ne arıyorum?**
   - Hedef pozisyonlar (etiket girişi: "Backend Developer", "Python Developer")
   - Seviye (çoklu seçim çipleri: Stajyer, Junior, Mid, Senior)
   - Hariç tutulacak kelimeler (etiket girişi: "Principal", "Staff")
2. **Nerede?**
   - Konumlar (etiket girişi: "İstanbul", "Remote")
   - "Sadece remote" anahtarı
3. **Eşleşme ve paket**
   - Minimum uyum puanı kaydırıcısı (varsayılan 70). Açıklama: "Bu puanın üstündeki ilanlar için paket otomatik hazırlanır."
   - "Paketleri otomatik hazırla" anahtarı
   - CV dili: Otomatik (ilanın diline göre) / Türkçe / İngilizce
4. **Kaynaklar**
   - Açma/kapama anahtarlı liste: RemoteOK, Remotive, Arbeitnow, Adzuna
   - Greenhouse / Lever / Ashby için takip edilen şirket listesi (etiket girişi)
5. **Zamanlama**
   - Günlük tarama saati (saat seçici, varsayılan 08:00)

## 6. Ortak bileşenler

- **Puan rozeti:** 3 boyut (küçük: listelerde, orta: kartlarda, büyük: detay başlığında). Renkler bölüm 3'teki tabloya göre.
- **Durum etiketi:** renkli, yumuşak arka planlı çip. Detay sayfasında açılır menü olarak da kullanılır.
- **Paket göstergesi:** ✓ Hazır / ⟳ Hazırlanıyor (dönen ikon) / — Yok / ! Hata
- **Kopyala butonu:** tıklayınca 2 saniye "Kopyalandı ✓" gösterir.
- **Yetenek çipi:** nötr, eşleşen (yeşil), eksik (soluk kırmızı) varyantları
- **Etiket girişi (tag input):** yaz, Enter'a bas, çip olarak eklensin, × ile silinsin
- **Boş durumlar:** her liste için sade bir ikon, bir cümle açıklama ve bir aksiyon butonu
- **Toast bildirimleri:** "Tarama başladı", "Paket hazır: Backend Engineer @ Örnek Firma", "Kaydedildi"
- **Tarama durumu:** "Şimdi tara"ya basınca kenar çubuğunda ilerleme göstergesi ("Taranıyor…"), bitince toast ("12 yeni ilan bulundu")

## 7. Durumlar

Her veri ekranı için şu durumlar tasarlanmalı:

- **Yükleniyor:** skeleton
- **Boş:** ilk kullanım. Profil boşsa Özet sayfası "Başlamak için profilini doldur" yönlendirmesi gösterir
- **Hata:** kısa mesaj + "Tekrar dene"
- **Dolu:** yukarıdaki örnek verilerle

## 8. Ekran boyutları

- **Ana hedef:** masaüstü (1280–1440px)
- **Telefon:** ikinci ana hedef. Kullanıcı uygulamayı telefonuna "Ana ekrana ekle" ile kurup gün içinde
  telefondan kullanacak (bkz. bölüm 11). Kenar çubuğu alt sekme çubuğuna veya hamburger menüye döner,
  ilan tablosu kart listesine dönüşür. İlan detayı ve kopyala butonları telefonda rahat kullanılmalı:
  en sık akış "bildirimi gör → ilanı aç → ön yazıyı kopyala → ilana git" telefondan yapılacak.

## 9. Kapsam dışı

- Kullanıcı hesabı, kayıt ekranı yok (herkes kendi bilgisayarında kendi kopyasını çalıştırır).
  Sadece telefondan erişim için tek alanlı bir **erişim anahtarı** ekranı var (bölüm 11).
- Uygulama başvuruyu kendisi göndermez; "Başvur" butonu sadece ilanın sayfasını açar
- Çoklu kullanıcı, ekip, bildirim ayarları yok

## 10. Tasarım teslim listesi

1. Uygulama iskeleti (kenar çubuğu + boş ana alan)
2. Özet sayfası (dolu + ilk kullanım/boş hali)
3. İlanlar listesi + "Link ile ilan ekle" modalı
4. İlan Detayı: 5 sekmenin her biri + "Hazırlanıyor" durumu
5. Profil sayfası + CV Yükleme modalı (3 adım)
6. Projeler ızgarası + düzenleme paneli
7. Ayarlar sayfası
8. Bileşen sayfası: puan rozeti, durum etiketi, çipler, butonlar, toast
9. Koyu tema versiyonu (en azından Özet ve İlan Detayı)
10. Mobil görünüm: Özet, İlan listesi ve İlan Detayı
11. Erişim anahtarı ekranı (telefon)
12. Uygulama ikonu (192 ve 512 px, maskable) ve açılış rengi

## 11. Telefonda kullanım (PWA)

Her kullanıcı backend'i kendi bilgisayarında çalıştırır. Telefon ona Tailscale üzerinden bir HTTPS
adresle bağlanır (ör. `https://yusuf-mac.tail1234.ts.net`). Arayüz aynı React uygulaması. Backend
derlenmiş hali (`frontend/dist`) aynı adresten sunar, ayrı bir mobil uygulama yok.

**Kurulabilir uygulama (PWA) gereksinimleri**
- `manifest.webmanifest`: `name: "Apply Agent"`, `short_name: "Apply"`, `display: "standalone"`,
  `start_url: "/"`, tema ve arka plan rengi, 192 ve 512 px ikonlar (512'nin maskable sürümü de).
- Minimal service worker: sadece uygulama kabuğunu (HTML/JS/CSS) önbelleğe alır. **`/api` isteklerini
  önbelleğe almaz**, veriler her zaman canlı gelir. Vite için `vite-plugin-pwa` yeterli.
- Telefonda çentik ve alt çubuk için güvenli alan boşlukları (`env(safe-area-inset-*)`).

**Erişim anahtarı ekranı**
- Uygulama açılışta `GET /api/auth/status` çağırır. `token_required` true ve `authenticated` false ise
  tam ekran, ortalanmış tek bir kart gösterilir:
  - Başlık: "Apply Agent'a bağlan"
  - Açıklama: "Bilgisayarındaki .env dosyasındaki API_TOKEN değerini gir. Bu cihaz hatırlanır."
  - Şifre tipi tek alan ("Erişim anahtarı") + "Bağlan" butonu
  - Hata: "Erişim anahtarı yanlış."
- `POST /api/auth/login` 204 dönerse uygulama normal açılır. Oturum çerezde tutulur (1 yıl).
- Herhangi bir API isteği 401 dönerse bu ekrana geri dönülür.
- Ayarlar sayfasının altında küçük bir "Bu cihazdan çıkış yap" linki (`POST /api/auth/logout`).

**Bağlantı yok durumu**
- Bilgisayar kapalıysa veya backend çalışmıyorsa istekler başarısız olur. Tam ekran sade bir durum:
  "Bilgisayarına ulaşılamıyor. Bilgisayarın açık, backend çalışıyor ve Tailscale bağlı olmalı."
  + "Tekrar dene" butonu.

