# Progres FireCal — 14 November 2026

Tahap saat ini: persiapan dan harmonisasi data nyata Indonesia selesai untuk
snapshot yang tersedia. Audit penyebab bias 2026 menjadi pekerjaan berikutnya.
Dataset masih berstatus **eksperimental**.

## Status pekerjaan

| Pekerjaan | Status | Bukti / hasil |
| --- | --- | --- |
| Arsip Indonesia 2000–2025 | Selesai | 48 berkas NASA; [laporan pilot](indonesia-pilot.md) |
| Audit regional awal | Selesai | 16 kandidat; perbaikan CV terbaik 1,94% di bawah ambang 5%; baseline dipertahankan; [laporan audit](regional-audit-findings.md) |
| Akuisisi 2026 dan NOAA-21 | Selesai sesuai rencana snapshot | 463 respons dari 8 sumber SP/NRT; 3.015.711 deteksi bbox; checksum dan receipt tersimpan |
| Country filtering dan harmonisasi | Selesai | 313 bulan; 7.716.551 deteksi setelah filtering; versi `593ae2d95fdf` |
| Pemeriksaan hasil | Lolos secara teknis | Rekonsiliasi point weights, API/CSV, 126 Python tests, Ruff lint/format |
| Paket kolaborasi data | Selesai lokal | Processed ZIP 106,7 MB dan sources ZIP 187,3 MB; manifest/checksum, pemindaian key, dan verifikasi dari ekstraksi kosong lolos; [onboarding](DATA-ONBOARDING.md) |
| Distribusi data ke rekan | Belum diunggah | Kedua ZIP dan checksum siap dibagikan dari `data/interim/share/`; akses repository privat perlu tersedia |
| Akurasi regional / transfer 2026 | Belum memenuhi target | Bias nasional Januari–Oktober 2026 −12,20%; 8/27 provinsi memenuhi kedua target |
| Audit SP/NRT, satelit, dan exposure | Belum dimulai | Urutan kerja tersedia di [handover audit bias](handover-bias-audit.md) |
| Protokol evaluasi model berikutnya | Belum disusun | Periode yang hasilnya sudah dibaca perlu diperlakukan sebagai regression check |
| Integrasi snapshot baru ke serving | Belum dilakukan | Baseline `a9443c4efd84` tetap terpisah dari snapshot baru |
| CI remote | Belum terselesaikan pada pemeriksaan sebelumnya | `startup_failure` tanpa job; status run terbaru belum diperiksa pada handover ini |

Jumlah respons lengkap membuktikan kelengkapan rencana permintaan. Coverage
observasi sensor, outage, dan valid observation masih perlu diperiksa terpisah.

## Hasil kuantitatif snapshot terbaru

| Periode pembanding | r nasional | Bias nasional | Provinsi memenuhi target |
| --- | ---: | ---: | ---: |
| 2016 dan 2019 | 0,9992 | −6,20% | 12/27 |
| 2022–2025 | 0,9949 | −2,88% | 9/27 |
| Januari–Oktober 2026, provisional | 0,9944 | −12,20% | 8/27 |

Target: r ≥ 0,9 dan absolute aggregate bias ≤ 10% terhadap MODIS. Provinsi yang
dinilai memiliki minimal 1.000 deteksi MODIS selama training, dengan bobot
overlap wilayah. MODIS digunakan sebagai referensi sensor; validasi terhadap
kejadian kebakaran di lapangan belum tersedia. November 2026 parsial dan tidak
masuk tabel evaluasi di atas.

## Status repository dan verifikasi

- Branch implementasi: `feat/firms-api-acquisition`.
- Commit implementasi terakhir: `54a2ed9`, sudah di-push ke `origin`.
- Commit sebelumnya: `a07311d` untuk pilot dan `a39a785` untuk audit regional.
- Pemeriksaan sebelum penyusunan dokumen ini: working tree bersih; HEAD dan
  upstream tidak memiliki selisih commit menurut referensi lokal.
- Log pengujian implementasi: `data/interim/extended-tests.log`, 126 passed,
  1 dependency deprecation warning. Pengujian ini mendahului perubahan dokumentasi.
- Data hasil download, output olahan, dan `.env` tidak disertakan dalam Git.
  Checkout baru memerlukan penyiapan atau pemindahan data lokal secara terpisah.

Lihat [laporan snapshot](indonesia-extended.md) untuk jumlah data dan bukti
verifikasi, serta [handover](handover-bias-audit.md) untuk melanjutkan pekerjaan.
