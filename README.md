# Application Agent

İş ilanlarını bulan, profile göre puanlayan ve her ilan için uyarlanmış CV, ön yazı ve
hazır cevaplardan oluşan bir başvuru paketi hazırlayan sistem. Başvuruyu kullanıcı manuel yapar.

**Kurulum, ilk gerçek test ve telefona yükleme:** [KURULUM.md](KURULUM.md)

Plan, görev dağılımı ve API sözleşmesi için [plan.md](plan.md) dosyasına bakın.

| Klasör | İçerik |
|---|---|
| `backend/` | FastAPI + LLM + ilan kaynakları |
| `frontend/` | React arayüzü |
| `contracts/examples/` | API sözleşmesi örnek JSON'ları (mock ve test verisi) |
| `profile.example/` | Örnek profil formatı |
