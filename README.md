# FireCal

**Kalender Aktivitas Kebakaran Terharmonisasi (MODIS–VIIRS)** — NASA Space Apps Challenge.

FireCal adalah aplikasi web yang menampilkan kalender aktivitas titik panas bulanan dari
November 2000 hingga hari ini untuk area yang dipilih pengguna. Data MODIS (C6.1) dan VIIRS
375 m dari [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov) diharmonisasi ke skala
setara-MODIS sehingga peralihan sensor tidak menimbulkan lonjakan tren palsu.

Spesifikasi lengkap, user story, dan tiket ada di
[`docs/FRD-Tickets-FireCal.pdf`](docs/FRD-Tickets-FireCal.pdf).

## Arsitektur

```
NASA FIRMS ──► pipeline (ingest → clean → grid → harmonize → validate) ──► Parquet
                                                                              │ DuckDB
                         web (React + MapLibre + D3) ◄── JSON ── api (FastAPI)
```

Pipeline berjalan harian dan menulis Parquet; API dan web hanya membaca hasilnya, sehingga
query cepat dan tetap jalan walau FIRMS sedang tidak dapat diakses.

## Struktur repositori

| Path                 | Isi                                                                 |
| -------------------- | ------------------------------------------------------------------- |
| `data/`              | `raw/`, `interim/`, `processed/` — tidak di-commit                  |
| `pipeline/firecal/`  | Paket Python + CLI Typer `firecal` (ingest, clean, grid, harmonize) |
| `pipeline/notebooks` | Notebook analisis (T-10, T-13)                                      |
| `api/app/`           | FastAPI: `/calendar`, `/stats`, `/points`, `/export`, `/globe`, `/meta` |
| `web/src/`           | React + TypeScript + Vite: globe, peta AOI, kalender, grafik        |
| `.github/workflows/` | CI (lint + test + build di setiap PR)                               |
| `docs/`              | FRD dan tiket                                                       |

## Prasyarat

- Git, [Python 3.12](https://www.python.org/), [uv](https://docs.astral.sh/uv/) ≥ 0.5
- [Node.js 22 LTS](https://nodejs.org/) dan [pnpm](https://pnpm.io/) ≥ 9 (`corepack enable`)
- Docker + Docker Compose v2 (opsional)
- `MAP_KEY` FIRMS gratis dari [halaman API FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/)

## Menjalankan secara lokal

```bash
git clone https://github.com/suryasuharna23/FireCal_NASA_SpaceApps_Challenge.git firecal
cd firecal

# 1. Konfigurasi — isi FIRMS_MAP_KEY di .env (jangan di-commit)
cp .env.example .env
cp web/.env.example web/.env

# 2. Dependensi + hook pre-commit
make setup

# 3. Data — simpan CSV arsip FIRMS (per tahun & sensor) di data/raw/, lalu:
make data                       # persempit COVERAGE_BBOX ke satu negara untuk uji cepat
uv run firecal nrt --days 7     # data near-real-time terbaru

# 4. Jalankan
make api                        # http://localhost:8000/docs
make web                        # http://localhost:5173
# atau keduanya lewat Docker:
make dev
```

Tanpa `make` (mis. Windows), jalankan perintah di [`Makefile`](Makefile) secara langsung.

## Perintah

| Perintah      | Fungsi                                                       |
| ------------- | ------------------------------------------------------------ |
| `make setup`  | Instal dependensi Python dan JavaScript, pasang pre-commit   |
| `make data`   | Jalankan seluruh pipeline dari `data/raw/` ke `data/processed/` |
| `make dev`    | Jalankan API dan frontend sekaligus lewat Docker Compose     |
| `make test`   | Ruff, pytest, ESLint, Prettier, typecheck, dan Vitest        |
| `make e2e`    | Uji Playwright pada alur utama                               |
| `make format` | Format otomatis kode Python dan TypeScript                   |

Jalankan `make test` sebelum membuka PR.

## Variabel lingkungan

Backend dan pipeline membaca `.env` di root; frontend membaca `web/.env`. Hanya variabel
berawalan `VITE_` yang sampai ke browser, sehingga `FIRMS_MAP_KEY` tetap di server (NFR-08).
Lihat [`.env.example`](.env.example) dan [`web/.env.example`](web/.env.example).

Setelah mengisi `FIRMS_MAP_KEY`, uji dengan `uv run firecal check-key`. Untuk CI, simpan key yang sama
sebagai GitHub secret `FIRMS_MAP_KEY` lalu jalankan workflow **Check FIRMS MAP_KEY**.

## Kontribusi

- Branch dari `main` dengan nama `<tipe>/<tiket>-<ringkas>`, mis. `feat/T-15-calendar-endpoint`.
- Pesan commit mengikuti [Conventional Commits](https://www.conventionalcommits.org/),
  mis. `feat(api): add /calendar endpoint`.
- CI wajib hijau sebelum merge.

## Lisensi dan atribusi

Kode dirilis di bawah [lisensi MIT](LICENSE). Data titik panas berasal dari
**NASA FIRMS** (Fire Information for Resource Management System), MODIS Collection 6.1
dan VIIRS 375 m (S-NPP, NOAA-20, NOAA-21).
