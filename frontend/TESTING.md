# UI entegrasyonu doğrulama raporu

Tarih: 22 Eylül 2026. Windows / PowerShell, ayrı `data-demo/app.db`.
Geliştirme: `http://127.0.0.1:5174` (5173 kullanımdaydı).
Derlenmiş arayüz: `http://127.0.0.1:8000`.

## Otomatik kontroller

- `npm test`: 20 test geçti. API istek/hata sözleşmeleri, 200/201 ayrımı,
  çerezli auth uçları, mock uyumu, boş maddeler/tarihler, clipboard yedeği,
  QueryCache/MutationCache 401/403/ağ kapısı ve özel verinin cache temizliği.
- `npm run build`: TypeScript kontrolü, Vite ve PWA service worker üretimi geçti.
- Backend'in mevcut `python -m pytest -q` paketi: 66 test geçti, 2 bağımlılık
  deprecation uyarısı. Gerçek LLM çağrısı yapmaz.
- `git diff --check`: geçti. Ayrı lint komutu mevcut değil.
- Backend ve contracts dosyalarında entegrasyon değişikliği yok. Bu branch'e
  alınan güncel main, backend dosyalarını merge commit'iyle getirdi.

## Tarayıcı kontrolleri

| Akış | Geliştirme proxy'si | Backend'den derlenmiş arayüz |
|---|---|---|
| Özet metrikleri, öne çıkan ilan, takiptekiler, son tarama/uyarı | Geçti | Geçti |
| 7 ilan, Türkçe `örnek` araması, durum/kaynak/puan filtreleri | Geçti | Geçti |
| Hazır paketin 5 sekmesi, ön yazı/cevap kopyalama | Geçti | Geçti |
| PDF indirme ve çerezli PDF erişimi | Geçti | Geçti (200, application/pdf) |
| Masaüstü PDF iframe önizlemesi | Backend engeli (#8 ile düzeltildi) | Backend engeli (#8 ile düzeltildi) |
| Başvuruldu durumu, not kaydı ve sayfa yenileme | Geçti | Geçti |
| Paket yeniden oluşturma, 202 sonrası failed/sebep | Geçti | Geçti |
| job_failed sebebi, metin yapıştırma, PATCH ardından POST | Geçti | Geçti |
| Profil kaydı/yenileme, boş deneyim maddelerini temizleme | Geçti | Geçti |
| TXT CV yükleme: 503 mesajı modal içinde | Geçti | Geçti |
| Proje ekleme/düzenleme/silme | Geçti | Geçti |
| E-posta alarmları ayarının kalıcılığı | Geçti | Geçti |
| Link ekleme: 422/503 mesajı, metin alanı, 200 mevcut ilan | Geçti | Geçti |
| Yanlış ASCII anahtar / doğru anahtar / cihazdan çıkış | Geçti | Geçti |
| Backend kapalı: bağlantı ekranı ve tekrar deneme | Geçti | Geçti |
| PWA kabuğunun backend kapalıyken yeniden açılması | Uygulanmaz | Geçti |
| 375 px özet/ilanlar/detay, yatay taşma ve mobil PDF düğmesi | Geçti | Geçti |
| Açık ve koyu görünüm | Geçti | Geçti |
| /jobs/job_ready doğrudan URL | Geçti | Geçti |

Ek doğrulamalar:

- Boş profilde paket ve tarama 409 mesajları ile Profil bağlantıları görünür.
- Mevcut `running` taramaya POST 200 ile katılma, 2,5 saniyelik polling,
  `done` sonrası başarı + info uyarısı ve son tarama güncellemesi kontrollü
  demo veritabanı fixture'ıyla doğrulandı. Bu gerçek kaynak taraması değildir.
- Yeni POST 202 taraması, tüm kaynaklar geçici olarak kapatılarak `done` / sıfır
  sonuçla tamamlandı. Demo ayarları ardından geri yüklendi.
- Mock, `.env.development.local` içinde `VITE_USE_MOCK=true` ile açıldı;
  anahtar istemedi, paket üretimi generating -> ready oldu ve ön yazı yüklendi.
  Yerel override test sonrası kaldırıldı; varsayılan gerçek API modu.
- Ağ hatası ile backend LLM 503 farklı ele alınır. Vite'ın bağlantı hatasını
  HTTP 500'e çevirmesi, sadece proxy'nin ürettiği özel başlıkla ayrıştırılır.

## Backend bulguları (değiştirilmedi)

1. `backend/app/api/jobs.py:171`: PDF `FileResponse` çağrısında `filename`
   verilmesi varsayılan `Content-Disposition: attachment` üretir.
   Beklenen: masaüstü iframe'in PDF'i inline göstermesi. Gerçek: PDF 200 ile
   iner, iframe boş kalır. Yanıtta `attachment; filename*=utf-8''...` görüldü.
   Mobilde yeni sekme bağlantısı vardır; cihaz PDF'i açabilir veya indirebilir.
2. `backend/app/auth.py:76`: `hmac.compare_digest(body.token.strip(), token)`
   Unicode string kabul etmez. `API_TOKEN=deneme-anahtar` iken `hatalı` göndermek
   beklenen 401 / `Erişim anahtarı yanlış.` yerine 500 üretir.
   ASCII yanlış anahtar ve doğru anahtar çalışır. Arayüz 500'ü hata olarak gösterir;
   backend sorununu gizleyecek karakter filtresi eklenmedi.

## Gerçek ortamda kalan doğrulamalar

Hiçbir gerçek LLM çağrısı yapılmadı. Test backend'inde LLM sağlayıcısı Claude,
CLI yolu mevcut olmayan bir dosya olarak ayarlandı; zamanlayıcı kapalıydı.
CV'den başarılı profil çıkarma, yeni linkten başarılı ilan ayrıştırma (201),
gerçek paket üretme ve gerçek kaynaklardan ilan tarama LLM kurulumuyla denenmeli.
502, 413, 415 ve 422 doğrulama dizisi istemci hata testleri/ortak hata yolu ile
kapsanır; tarayıcıda sunucu kaynaklı hata örnekleri 401, 409, 422 ve 503'tür.

Fiziksel Android cihazda Tailscale HTTPS üzerinden Ana ekrana ekle ve işletim
sisteminin PDF görüntüleyicisi bu masaüstü ortamında denenmedi. Manifest, PNG
ikonlar, responsive ekranlar ve yalnızca kabuğu önbelleğe alan service worker
üretildi ve yerel derlemede kontrol edildi.

## Teknik kararlar

- Oturum bilgisi React Query'de; anahtar yalnızca giriş formunda geçici tutulur.
  Oturum değişiminde özel sorgu/mutation önbelleği temizlenir.
- `addManualJob`, HTTP durumunu kaybetmemek için `{ job, created }` döndürür;
  sunucunun JSON sözleşmesi değişmez. Mock aynı istemci arayüzünü uygular.
- İlan detay içeriği ilan id'si ile yeniden oluşturulur; bir ilandaki taslak veya
  bekleyen mutation başka ilana taşınmaz. Yeniden paket üretiminde eski paket
  cache'i temizlenir.
- Form normalizasyonu kayıttan hemen önce yapılır; düzenleme sırasında boş
  satır yazılabilir. Kaydedilen payload boş bullet veya boş tarih içermez.
- PWA `autoUpdate`, `/api/` ve tam `/api` navigation dışlaması, boş runtime cache.
  PDF ve API verileri service worker önbelleğine girmez.
