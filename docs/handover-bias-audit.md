# Handover audit bias FireCal

Disiapkan 14 November 2026. Tujuan tahap berikutnya adalah menelusuri kontribusi
SP/NRT, tiap satelit, dan exposure terhadap bias 2026 sebelum merancang koreksi.
Audit ini belum dijalankan. [Tracker progres](PROGRESS.md) mencatat pekerjaan
yang sudah selesai dan pekerjaan yang masih terbuka.

## Kondisi awal

- Repository: `suryasuharna23/FireCal_NASA_SpaceApps_Challenge`.
- Workspace lokal: `C:\Users\ASUS\.vscode\paper\NASA\FireCal_NASA_SpaceApps_Challenge`.
- Branch: `feat/firms-api-acquisition`; commit implementasi terakhir `54a2ed9`
  sudah di-push. Branch ini memuat pilot `a07311d` dan audit regional `a39a785`.
- Akuisisi, country filtering, harmonisasi, dan pemeriksaan teknis snapshot
  Indonesia selesai. Tidak perlu mengulang download untuk snapshot ini.
- Dataset baru eksperimental; konfigurasi serving belum dialihkan.
- Handover ini menambahkan dokumentasi. Tidak ada perubahan model atau audit
  bias baru yang dihasilkan pada tahap penulisan dokumen ini.

| Dataset | Lokasi relatif terhadap repository | Versi / cakupan |
| --- | --- | --- |
| Baseline serving | `data/processed/` | `a9443c4efd84`; November 2000–Desember 2025 |
| Snapshot tambahan | `data/interim/indonesia-extended-20261114/processed/` | `593ae2d95fdf`; November 2000–November 2026; deteksi terakhir 14 November |
| Respons NASA asli | `data/interim/api-acquisition/responses/` | 463 respons; receipt dan checksum per berkas |
| Rencana dan availability | `data/interim/api-acquisition/plan.json`, `availability.json`, `progress.json` | 8 sumber; snapshot selesai sesuai availability yang direkam |
| Audit model sebelumnya | `data/interim/regional-audit/` | Selection lock, kandidat, dan hasil audit terdahulu |

Semua lokasi `data/` di atas bersifat lokal dan diabaikan Git. Data mentah serta
receipt perlu ikut dipindahkan jika pekerjaan dilanjutkan di komputer lain.
`FIRMS_MAP_KEY` hanya dibaca dari `.env`; jangan memasukkan key atau URL yang
memuat key ke laporan, log, atau commit.

## Hasil yang sudah diketahui

Snapshot baru memuat 7.716.551 deteksi setelah filtering pada 313 bulan dari
Terra, Aqua, S-NPP, NOAA-20, dan NOAA-21. Rekonsiliasi point weights terhadap
cube memiliki galat maksimum 1,74e-11. Pemeriksaan API/CSV untuk Riau, Sumatera
Selatan, dan Kalimantan Tengah lolos; 126 Python tests dan Ruff juga lolos.

Bias nasional Januari–Oktober 2026 adalah −12,20%, dengan r = 0,9944. Hanya
8 dari 27 provinsi yang memenuhi r ≥ 0,9 dan absolute aggregate bias ≤ 10%.
Hasil per wilayah dan periode tersedia di
`processed/reports/regional_regression.csv` pada snapshot baru. Ringkasan
lengkap tersedia di [laporan snapshot](indonesia-extended.md).

Model memakai `GRID_RES_DEG=0.25` dan calibration window 2013–2021, dengan 2016
dan 2019 dikeluarkan dari fitting. Kandidat audit sebelumnya tidak melewati
ambang perbaikan CV 5%, sehingga baseline dipertahankan. Snapshot tambahan
menghitung ulang koefisien baseline setelah seluruh sumber memakai country mask
Natural Earth 10m yang sama. Angka historisnya dapat berbeda dari pilot lama.

## Titik masuk kode dan bukti

| Berkas | Kegunaan untuk audit |
| --- | --- |
| `pipeline/firecal/grid.py` | `aggregate_monthly`: `n_viirs_sats` dihitung dari satelit dengan deteksi pada bulan tersebut di seluruh dataset yang dimuat |
| `pipeline/firecal/harmonize.py` | `v_norm = n_viirs / n_viirs_sats`; prediksi `k * v_norm`; fitting dan transisi seri |
| `pipeline/firecal/ingest.py` | Normalisasi platform, tanggal, dan versi sumber SP/NRT |
| `pipeline/firecal/nrt.py` | Penggabungan dan deduplikasi SP/NRT |
| `scripts/prepare_indonesia_extended.py` | Verifikasi input, country filtering, dan pembangunan snapshot terpisah |
| `scripts/verify_indonesia_extended.py` | Rekonsiliasi point weights, API/CSV, serta regression check regional dengan bulan nol tetap disertakan |
| `scripts/audit_regional_harmonization.py` | Contoh selection lock dan audit kandidat terdahulu |
| `processed/points/**/*.parquet` | Titik bersih dengan platform dan sumber untuk agregasi ulang |
| `processed/reports/satellite_source_counts.csv` | Jumlah dan rentang deteksi yang benar-benar dipertahankan |
| `processed/reports/validation.json` | Metrik dan batasan snapshot |

Pada tiga baris terakhir, `processed/` merujuk pada snapshot tambahan.
Untuk regression check sebelum transisi akhir 2021, bandingkan MODIS dengan
prediksi `k * n_viirs / n_viirs_sats` dari grid dan koefisien. Seri gabungan
`n_harmonized` pada periode tersebut memakai MODIS sehingga tidak sesuai untuk
mengukur prediksi VIIRS terhadap MODIS.

## Urutan audit berikutnya

### 1. Bekukan input dan buat baseline audit

- [ ] Simpan versi dataset, SHA-256 input yang dipakai, konfigurasi, dan commit
  kode di manifest audit baru, misalnya `data/interim/bias-audit-20261114/`.
- [ ] Reproduksi metrik nasional dan 27 provinsi eligible pada Januari–Oktober
  2026 dengan koefisien snapshot tetap. Laporkan juga tiga provinsi pilot.
- [ ] Cocokkan jumlah deteksi per satelit/sumber dengan receipt dan laporan
  snapshot; pertahankan zero-detection months pada agregasi bulanan.

### 2. Pisahkan periode SP/NRT

| Periode snapshot 2026 | MODIS | VIIRS | Perlakuan |
| --- | --- | --- | --- |
| Januari–Juli | SP | SP | Baseline diagnostik dengan mode pemrosesan yang sama |
| Agustus | SP | NRT | Periode transisi dengan mode berbeda |
| September–Oktober | NRT | NRT | Diagnostik mode NRT pada bulan kalender lengkap; exposure masih perlu diverifikasi |
| 1–14 November | NRT | NRT; S-NPP berakhir 2 November | Laporkan terpisah sebagai periode parsial |

- [ ] Sajikan n_modis, jumlah VIIRS per satelit, denominator, prediksi, residual,
  bias, MAE, dan r bila jumlah bulan/variasi memadai; tandai metrik yang tidak
  dapat dihitung.
- [ ] Pisahkan hasil tiap tahun pada 2022–2025 sebagai konteks historis yang
  hasilnya sudah diketahui.
- [ ] Bedakan asosiasi waktu dan penyebab. SP/NRT pada snapshot ini tidak
  menyediakan pasangan observasi periode sama untuk semua platform; perbedaan
  musim dan sampling dapat ikut menjelaskan perbedaan antarperiode.

### 3. Periksa kontribusi satelit

- [ ] Agregasikan S-NPP, NOAA-20, dan NOAA-21 secara terpisah pada bulan yang
  sama. NOAA-21 SP tersedia mulai 1 Maret 2023.
- [ ] Lakukan sensitivity check dengan mengeluarkan satu satelit, termasuk
  NOAA-21; hitung ulang denominator dari subset satelit yang sama sambil
  mempertahankan koefisien `k`. Laporkan perubahan hasil sebagai diagnostik.
- [ ] Periksa Terra dan Aqua secara terpisah karena referensi MODIS juga dapat
  berubah. Catat source version, negara/wilayah, serta bulan pembanding.
- [ ] Jangan memilih subset satelit hanya karena membuat bias 2026 melewati
  target. Perbedaan ini belum mengisolasi efek sensor, pemrosesan, atau exposure.

### 4. Periksa exposure dan outage

- [ ] Inventarisasi gap/outage dari metadata NASA atau valid-observation swath,
  termasuk cakupan spasial, platform, tanggal, sumber, dan waktu pengambilan.
- [ ] Bedakan tiga keadaan: permintaan berhasil tanpa deteksi, outage yang
  terkonfirmasi, dan exposure yang belum diketahui.
- [ ] Bandingkan informasi tersebut dengan denominator bulanan yang sekarang
  hanya menghitung satelit dengan deteksi. Evaluasi dampak parsial S-NPP pada
  November tanpa menyamakannya dengan bulan penuh.
- [ ] Jika bukti exposure belum cukup, tulis batasannya dan kebutuhan data
  lanjutan. Jumlah hari yang memiliki deteksi tidak boleh dijadikan pengganti
  jumlah hari observasi valid.

[Protokol audit sebelumnya](regional-audit-protocol.md) memuat rujukan metadata
gap NASA. Pada pelaksanaan berikutnya, verifikasi kembali dokumentasi dan
availability resminya sebelum mengambil data tambahan.

### 5. Simpulkan diagnosis dan rancang evaluasi berikutnya

- [ ] Buat tabel kontribusi bias menurut satelit, mode SP/NRT, bulan, dan wilayah,
  disertai bukti serta faktor yang belum dapat dipisahkan.
- [ ] Usulkan kandidat koreksi berdasarkan diagnosis, lalu tetapkan training
  split, kriteria pemilihan, target, dan evaluation lock sebelum model dipilih.
- [ ] Perlakukan 2016/2019, 2022–2025, dan hasil agregat 2026 yang sudah dibaca
  sebagai hasil yang diketahui. Jangan menyebutnya fresh independent hold-out.
- [ ] Tentukan sumber evaluasi yang benar-benar belum digunakan atau nyatakan
  keterbatasan independensinya. Tetap pisahkan hasil nasional dan regional.

## Keluaran yang diharapkan dari tahap berikutnya

Artefak berikut masih direncanakan:

- Manifest input audit dan tabel bulanan per platform/sumber/wilayah.
- Tabel sensitivity check beserta denominator yang dipakai.
- Inventaris exposure/gap dengan status bukti dan batasan.
- Laporan temuan yang membedakan hasil observasi, hipotesis, dan rekomendasi.
- Usulan protokol evaluasi baru untuk kandidat koreksi.

Tahap audit selesai ketika baseline berhasil direproduksi, setiap cabang
diagnostik memiliki hasil atau alasan keterbatasan yang jelas, dan rekomendasi
dapat ditelusuri ke bukti. Akurasi yang belum memenuhi target tetap dilaporkan.
Audit tidak otomatis mengganti model, `.env`, dataset serving, atau deployment.

## Memulai sesi berikutnya

```powershell
Set-Location -LiteralPath "C:\Users\ASUS\.vscode\paper\NASA\FireCal_NASA_SpaceApps_Challenge"
git status --short
git branch --show-current
git log -1 --oneline

# Pemeriksaan snapshot yang sudah tersedia, tanpa download ulang:
uv run --no-sync python scripts/verify_indonesia_extended.py
```

Verifier memperbarui laporan verifikasi dan regression check di snapshot lokal.
Simpan salinan laporan/checksum yang dibutuhkan sebelum menjalankannya untuk
audit yang dibekukan. `prepare_indonesia_extended.py` membangun ulang output
turunan; gunakan hanya jika memang perlu reproduksi penuh.

Prompt lanjutan yang bisa digunakan:

> Lanjutkan FireCal dari docs/handover-bias-audit.md dan docs/PROGRESS.md.
> Reproduksi baseline snapshot 593ae2d95fdf, lalu audit bias per SP/NRT, satelit,
> bulan, dan provinsi dengan koefisien tetap. Tinjau bukti exposure/outage dan
> laporkan ketidakpastiannya. Simpan eksperimen terpisah, pertahankan serving,
> dan susun rekomendasi serta protokol evaluasi berikutnya dari temuan audit.
