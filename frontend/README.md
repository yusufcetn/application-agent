# Apply Agent arayüzü

React, TypeScript, Vite ve TanStack Query. Tasarım: [DESIGN.md](DESIGN.md).

## Yerel geliştirme (PowerShell)

Backend'i ayrı terminalde başlatın:

```powershell
cd backend
uv sync
uv run playwright install chromium
$env:DATA_DIR="../data-demo"
$env:DATABASE_URL="sqlite:///../data-demo/app.db"
$env:SCHEDULER_ENABLED="false"
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Demo seed LLM kullanmadan 7 ilan, bir hazır paket, gerçek PDF, profil, projeler,
ayarlar ve uyarı içeren bir tarama oluşturur. Gerçek verilerden ayrı `data-demo/`
klasöründedir. Seed'i `--force` ile tekrar çalıştırmak demo kayıtlarını başlangıç haline getirir.

İkinci terminal:

```powershell
cd frontend
npm ci
npm run dev
```

`http://localhost:5173` adresini açın. Varsayılan `.env.development` ayarı
`VITE_USE_MOCK=false`; `/api` istekleri `http://127.0.0.1:8000` adresine gider.
Windows IPv6 çözümlemesi nedeniyle proxy hedefinde `localhost` kullanılmaz.
Proxy'ye `xfwd` eklemeyin: backend iletilen IP başlığını uzaktan erişim sayar.
Geliştirme proxy'si backend'e erişemediğinde özel bir hata başlığıyla bağlantı
ekranını tetikler; backend'in LLM 503 yanıtları ilgili formda kalır.

## Mock modu

`frontend/.env.development.local` dosyasına `VITE_USE_MOCK=true` yazıp Vite'ı
yeniden başlatın. Demo veriler `apply-agent-demo:*` anahtarlarıyla tarayıcıda
saklanır. Mock kimlik doğrulama istemez; gerçek profil verisi kullanmaz.
Gerçek moda dönmek için yerel dosyayı kaldırın veya değeri `false` yapın.
Üretim derlemesinde mock varsayılan olarak kapalıdır.

## Doğrulama ve üretim

```powershell
npm test
npm run build
```

Testler API hata/durum sözleşmelerini, mock akışlarını, form normalizasyonunu,
panoya kopyalama yedeğini ve oturum/bağlantı kapısını kapsar. Build TypeScript
kontrolünü de çalıştırır. Ayrı lint komutu bulunmuyor.

Çıktı `frontend/dist/` altındadır. Build sonrasında backend'i yeniden başlatın;
`http://127.0.0.1:8000/` arayüzü ve `/jobs/job_ready` gibi doğrudan detay
bağlantılarını sunar. API, PDF ve arayüz aynı adrestedir; oturum HttpOnly çerezle
yürür. Anahtar tarayıcı depolamasına veya Authorization başlığına yazılmaz.

CV yükleme (10–30 sn), yeni ilan ayrıştırma (15–30 sn), paket hazırlama
(yaklaşık 1 dk) ve tarama (1–3 dk) için backend'deki LLM CLI kurulumu gerekir.
CV yükleme bir önizlemedir; Taslağa aktar ve Kaydet ile kalıcı olur.
LLM olmadan hata kontrolü yapmak için yalnızca test terminalinde
`$env:CLAUDE_BIN="C:\olmayan-test-cli.exe"` ve `$env:LLM_PROVIDER="claude"`
ayarlayın. Bu ortamla başarılı üretim doğrulanamaz.

## Telefonda kurulum

Backend [telefon kurulumunu](../backend/README.md#telefondan-kullanım-tailscale)
uygulayın: API_TOKEN, Tailscale Serve ve HTTPS adresi. Telefonda erişim anahtarıyla
bağlanın, Chrome menüsünden **Ana ekrana ekle** seçin. Ayarlar'dan bu cihazın
oturumunu kapatabilirsiniz. Bilgisayar ve backend açık olmalıdır.

PWA yalnızca uygulama kabuğunu önbelleğe alır; `/api` ve kişisel veriler için
runtime cache yoktur. Bağlantı kesilirse uygulama yeniden deneme ekranı gösterir.
Mobilde CV yeni sekmede açılır; masaüstünde PDF iframe önizlemesi vardır.
PWA güncellemeleri otomatik uygulanır.

İkon kaynağı `public/icon.svg`, mevcut çanta marka işaretinin vektör çizimidir.
İkonları yeniden üretmek için:

```powershell
npm run generate-icons
```

PNG'ler repoda tutulur. Yapılandırma, [Vite PWA generateSW](https://vite-pwa-org.netlify.app/workbox/generate-sw)
ve [assets generator](https://vite-pwa-org.netlify.app/assets-generator/cli)
belgelerini izler.
