# Melanjutkan FireCal dengan snapshot bersama

Snapshot Indonesia `593ae2d95fdf` berisi **7.716.551 deteksi setelah filtering**,
November 2000–14 November 2026. Data berstatus eksperimental; bias nasional
Januari–Oktober 2026 −12,20%. Batasan dan tugas berikutnya tersedia di
[handover audit](handover-bias-audit.md) dan [tracker progres](PROGRESS.md).

## Stack yang digunakan

| Bagian | Stack repository |
| --- | --- |
| Pipeline | Python ≥3.12, uv workspace, pandas, DuckDB, PyArrow, GeoPandas/Shapely, statsmodels, scikit-learn; Typer CLI |
| Penyimpanan analitis | Berkas Parquet, point partitions per tahun, metadata/laporan JSON; tidak membutuhkan server database lokal |
| API | FastAPI, Uvicorn, Pydantic; DuckDB membaca Parquet dari `DATA_URI` |
| Frontend | React 19, TypeScript 5.8, Vite 6, MapLibre, Terra Draw, ECharts/D3, TanStack Query, Zustand |
| Tooling frontend | Node ≥22.19.0, pnpm 10.33.2 sesuai `web/package.json`; Vitest, ESLint, Prettier, Playwright |
| Deployment yang dikonfigurasi | Docker Compose; frontend Cloudflare Pages, API Fly.io/Cloud Run, data S3/R2; status deployment tidak diverifikasi pada penyiapan paket ini |

Gunakan `uv.lock` dan `web/pnpm-lock.yaml` untuk versi dependency yang sama.

## Berkas yang harus dibagikan

Paket dibuat lokal di `data/interim/share/`, di luar Git:

| Paket | Isi | Penggunaan |
| --- | --- | --- |
| `firecal-indonesia-593ae2d95fdf-processed.zip` | Seluruh processed snapshot, termasuk 7,7 juta points, koefisien, grid, regions, metadata, dan laporan | Menjalankan API/frontend serta mengaudit hasil tanpa download ulang |
| `firecal-indonesia-593ae2d95fdf-sources.zip` | 48 CSV tahunan asli, respons API beserta receipt, availability/rencana, batas negara, archive manifest, regions baseline, serta prior selection lock | Menelusuri provenance, gap, audit runner, dan reproduksi snapshot |
| Berkas `.zip.sha256` masing-masing | SHA-256 seluruh arsip | Memastikan transfer utuh |

Setiap ZIP memiliki `SNAPSHOT-MANIFEST-*.json` dengan checksum setiap berkas,
versi dataset, jumlah points, dan commit implementasi saat pengemasan. Manifest
paket menggunakan path relatif repository. Receipt asli tetap dipertahankan.
Paket tidak membawa `.env`, MAP_KEY, environment Python, atau `node_modules`.

Untuk rekan yang melanjutkan audit bias, bagikan **kedua ZIP dan kedua checksum**
bersama URL repository serta branch `feat/firms-api-acquisition`. Paket belum
diunggah otomatis. Unggah ke folder Drive bersama atau object storage yang
bisa diunduh tim; tempelkan URL aksesnya di pesan handover. Akun rekan juga
memerlukan akses repository privat. Commit/push kode tidak mengirim data ZIP.

## Setup pada komputer rekan

Contoh PowerShell, dari folder induk tempat repository akan disimpan:

```powershell
git clone --branch feat/firms-api-acquisition https://github.com/suryasuharna23/FireCal_NASA_SpaceApps_Challenge.git
Set-Location FireCal_NASA_SpaceApps_Challenge
uv sync --all-packages --locked
corepack enable
corepack prepare pnpm@10.33.2 --activate
pnpm --dir web install --frozen-lockfile
```

Pastikan kode onboarding/packager terbaru sudah ikut dikirim atau di-push;
commit implementasi snapshot adalah `54a2ed9`. Periksa `git log -1 --oneline`.

Simpan kedua ZIP yang diterima di folder Downloads. Bandingkan hash hasil
perintah berikut dengan `.sha256` yang dikirim melalui kanal tepercaya:

```powershell
Get-FileHash "$HOME/Downloads/firecal-indonesia-593ae2d95fdf-processed.zip" -Algorithm SHA256
Get-FileHash "$HOME/Downloads/firecal-indonesia-593ae2d95fdf-sources.zip" -Algorithm SHA256

# Jika packager sudah tersedia di checkout:
uv run --no-sync python scripts/package_snapshot.py --verify "$HOME/Downloads/firecal-indonesia-593ae2d95fdf-processed.zip"
uv run --no-sync python scripts/package_snapshot.py --verify "$HOME/Downloads/firecal-indonesia-593ae2d95fdf-sources.zip"
```

Ekstrak dari root repository pada checkout baru. Path `data/...` sudah ada di
dalam ZIP. Hindari ekstraksi di atas data kerja yang sudah dimodifikasi.

```powershell
Expand-Archive "$HOME/Downloads/firecal-indonesia-593ae2d95fdf-processed.zip" -DestinationPath .
Expand-Archive "$HOME/Downloads/firecal-indonesia-593ae2d95fdf-sources.zip" -DestinationPath .
```

Manifest di root setelah ekstraksi merupakan artefak lokal yang diabaikan Git
melalui `.gitignore` terbaru.

## Menjalankan aplikasi dari snapshot

Tidak diperlukan MAP_KEY untuk membaca paket yang sudah diunduh. Di terminal API:

```powershell
$env:DATA_URI = (Resolve-Path 'data/interim/indonesia-extended-20261114/processed').Path
$env:CORS_ORIGINS = 'http://localhost:5173'
uv run --no-sync uvicorn app.main:app --app-dir api --host 127.0.0.1 --port 8000
```

Di terminal kedua, dari root repository:

```powershell
$env:VITE_API_BASE_URL = 'http://localhost:8000'
pnpm --dir web dev
```

Buka `http://localhost:5173`, lalu cek metadata di `http://localhost:8000/meta`.
Pastikan `data_version` adalah `593ae2d95fdf` dan cakupan berakhir November 2026.
Endpoint `/health` saja tidak membuktikan dataset berhasil dimuat.

Compose yang ada menetapkan `DATA_URI=/app/data/processed`, yaitu lokasi baseline.
Gunakan perintah lokal di atas untuk snapshot ini; menjalankan Compose tanpa
override tidak otomatis memilih snapshot tambahan.

## Memverifikasi data dan melanjutkan audit

Setelah kedua paket diekstrak, jalankan dari root repository:

```powershell
$env:COVERAGE_BBOX = '94,-12,142,7'
uv run --no-sync python scripts/verify_indonesia_extended.py
```

Untuk audit runner yang ditambahkan rekan pada commit `90da7d7`:

```powershell
uv run --no-sync python scripts/audit_indonesia_bias.py --check-inputs
# Jalankan analisis setelah preflight siap; direktori output harus baru:
uv run --no-sync python scripts/audit_indonesia_bias.py
```

Sources ZIP terbaru menyertakan `data/interim/regional-audit/selection_lock.json`
yang diperlukan preflight. Periksa `audit.json` sebelum menganggap eksekusi audit
selesai; keberadaan direktori output saja belum membuktikan keberhasilan.

Verifier memeriksa jumlah/coverage platform, rekonsiliasi point weights, API/CSV,
dan regression check regional. Verifier menulis ulang laporan pada snapshot
lokal; simpan manifest/checksum paket sebagai acuan transfer yang tidak berubah.

Untuk reproduksi penuh, setelah input dan checksum terverifikasi:

```powershell
$env:COVERAGE_BBOX = '94,-12,142,7'
uv run --no-sync python scripts/prepare_indonesia_extended.py
uv run --no-sync python scripts/verify_indonesia_extended.py
```

Perintah preparation membangun ulang output turunan snapshot. Paket sources
hanya menyertakan regions dan archive manifest dari baseline sebagai input
reproduksi, bukan seluruh dataset baseline serving. Jika membutuhkan baseline
lama lengkap untuk eksperimen lain, minta paket terpisah.

Lanjutkan langkah di [handover audit bias](handover-bias-audit.md), simpan hasil
eksperimen terpisah, dan catat versi dataset serta commit pada setiap laporan.

## Membuat paket ulang pada komputer pemilik data

```powershell
uv run --no-sync python scripts/package_snapshot.py --build processed
uv run --no-sync python scripts/package_snapshot.py --build sources
```

Packager memeriksa versi dan jumlah points, membuat manifest, memverifikasi
seluruh isi ZIP, lalu menulis checksum arsip. Paket yang sudah ada tidak ditimpa.

## Hasil penyiapan lokal, 14 November 2026

- Processed ZIP: 106.674.802 byte, 52 berkas data/laporan ditambah manifest.
- Sources ZIP terbaru: 187.265.986 byte, 991 berkas sumber/provenance ditambah manifest.
- Checksum per berkas di kedua ZIP telah diverifikasi dan pemindaian seluruh
  isi paket tidak menemukan MAP_KEY lokal.
- Kedua ZIP diekstrak ke folder qualification kosong. Verifier snapshot,
  rekonsiliasi points, dan API/CSV tiga provinsi lolos dari folder tersebut.
- Setelah integrasi runner rekan, preflight dari paket hasil ekstraksi juga
  lolos: `ready=true`, 27 point partitions, 463 respons API terverifikasi.
- Sebanyak 16 tests audit runner lolos pada ASUS setelah integrasi kode remote;
  audit numerik penuh belum dijalankan pada tahap commit/push ini.
- Qualification memakai environment Python yang sudah tersedia pada komputer
  ini. Instalasi dependency pada komputer rekan dan upload bersama belum diuji.
