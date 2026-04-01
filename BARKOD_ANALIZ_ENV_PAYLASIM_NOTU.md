Barkod Analiz Env Paylasim Notu

Amac
- Barkod Analiz ekibinin Market Gelsin API, Supabase ve Firebase entegrasyonunu hizli kurabilmesi icin paylasilabilir bir env iskeleti sunmak.

Repoda paylasilan dosyalar
- `.env.market_gelsin_api.example`
- `.env.supabase.example`
- `.env.firebase.example`
- `.env.barkod_analiz_team.example`

Git'e yazilmasi guvenli alanlar
- `SUPABASE_URL`
- `SUPABASE_DB_HOST`
- `SUPABASE_DB_PORT`
- `SUPABASE_DB_NAME`
- `SUPABASE_DB_USER`
- `MARKET_GELSIN_FIREBASE_PROJECT_ID`
- `MARKET_GELSIN_FIREBASE_COLLECTION`
- `MARKET_GELSIN_API_BASE_URL`

Git'e yazilmamasi gereken alanlar
- `SUPABASE_DB_URL` gercek parola ile
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `MARKET_GELSIN_INGEST_TOKEN`
- `MARKET_GELSIN_FIREBASE_CREDENTIALS` dosya icerigi
- herhangi bir gercek `.local` env dosyasi

Onerilen kullanim
1. Barkod Analiz ekibi `.env.barkod_analiz_team.example` dosyasini kendi lokal env dosyasina kopyalar.
2. Gercek secret degerler 1Password, Bitwarden, GitHub Secrets veya Supabase/Firebase panelinden guvenli kanalla doldurulur.
3. Lokal calisma icin Market Gelsin tarafinda `.env.market_gelsin_api.local`, `.env.supabase.local` ve `.env.firebase.local` kullanilir.

Not
- Secret degerleri git history'ye yazmiyoruz. Gerekiyorsa gecici paylasim linki veya ekip ici secret manager kullanilmali.
