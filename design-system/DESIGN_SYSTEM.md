# 🔥 FireCal Design System

> **NASA Space Apps Challenge · Cyber Techno & Deep Space Theme**  
> Sumber Figma: [FIRECAL - NASA Space Apps Challenge (Node #12:10396 & #12:10198)](https://www.figma.com/design/puzwPDVZ43BBZvvwTty5cC/FIRECAL---NASA-Space-Apps-Challenge?node-id=12-10396)

---

## 📋 Daftar Isi
1. [Filosofi & Konsep Desain](#1-filosofi--konsep-desain)
2. [Brand Assets & Logo (SVG di Repository)](#2-brand-assets--logo-svg-di-repository)
3. [Palet Warna Lengkap (Color Tokens)](#3-palet-warna-lengkap-color-tokens)
   - [High-Contrast Accents (Solar Flare / Fire)](#solar-flare--fire-accents)
   - [Dominant Dark Palette (Indigo Void & Deep Space)](#indigo-void--deep-space)
   - [Cyber Techno Borders & Contours](#cyber-techno-borders)
   - [Calendar Heatmap Intensity Scale](#heatmap-intensity-scale)
   - [Biosphere & NASA Earth Observation (Flora)](#biosphere--flora)
   - [Neutrals & Typography Colors](#neutrals--typography-colors)
4. [Sistem Gradien (Gradients)](#4-sistem-gradien-gradients)
5. [Sistem Tipografi (Typography)](#5-sistem-tipografi-typography)
   - [Hierarki Space Grotesk](#hierarki-space-grotesk)
   - [Hierarki Antarmuka (Figtree / Sans)](#hierarki-antarmuka-figtree--sans)
   - [Monospace Data](#monospace-data-jetbrains-mono)
6. [Spesimen Komponen UI](#6-spesimen-komponen-ui)
7. [Panduan Penggunaan (Figma & Kode)](#7-panduan-penggunaan-figma--kode)

---

## 1. Filosofi & Konsep Desain

FireCal memadukan nuansa **Deep Space Indigo Void** (astronomi, citra satelit NASA orbit bumi) dengan **Solar Thermal Flare** (panas api, hotspot, kalibrasi termal).

- **Dominasi Gelap**: Memaksimalkan visualisasi peta satelit, kalender data 24+ tahun, dan meminimalkan ketegangan mata pengguna.
- **Aksen Kontras Tinggi**: Membedakan anomali termal, tingkat keparahan kebakaran hutan, dan status kalibrasi sensor MODIS/VIIRS.
- **Tipografi Presisi**: Menggabungkan karakter display geometris modern (*Space Grotesk*) untuk judul dan angka besar, dengan sans-serif berdaya baca tinggi (*Figtree*) untuk teks antarmuka.

---

## 2. Brand Assets & Logo (SVG di Repository)

Logo resmi FireCal telah dimasukkan langsung ke dalam repositori dalam format vektor SVG murni sehingga siap digunakan pada komponen web, favicon, header, dan aset ekspor tanpa kehilangan resolusi.

### Berkas SVG Resmi di Repositori:
1. **Full Logo (Logomark + Logotype "FireCal")**  
   - 📁 **File Path**: [`design-system/FIRECAL LOGO.svg`](file:///Users/lanaginting/Documents/FireCal_NASA_SpaceApps_Challenge/design-system/FIRECAL%20LOGO.svg)
   - **Dimensi Asli**: `1209 × 354 px` (`viewBox="0 0 1209 354"`)
   - **Komposisi**: Simbol logomark di sisi kiri berpadu dengan tipografi merek *"FireCal"* berwarna putih (`#FFFFFF`) menggunakan tipe glyph Space Grotesk.
   - **Penggunaan Utama**: Navbar utama aplikasi, landing page hero header, cover presentasi, dan dokumen resmi.

2. **Logomark Only (Simbol Ikon)**  
   - 📁 **File Path**: [`design-system/FIRECAL LOGOMARK.svg`](file:///Users/lanaginting/Documents/FireCal_NASA_SpaceApps_Challenge/design-system/FIRECAL%20LOGOMARK.svg)
   - **Dimensi Asli**: `267 × 330 px` (`viewBox="0 0 267 330"`)
   - **Komposisi Vektor**:
     - *Flame Tongue (Lidah Api)*: Gradien termal `#FF9F1C` ➔ `#FF6B1A` ➔ `#E04006`
     - *Biosphere Foliage (Daun/Hutan)*: Gradien bio `#5FD678` ➔ `#2CBC84`
     - *Earth & Ocean Base*: Gradien spektrum satelit `#1649A8` ➔ `#0BA1C4`
     - *Dynamic Cut / Orbit Stroke*: Garis orbit putih kontras tebal 20px (`stroke="white"`).
   - **Penggunaan Utama**: Favicon browser, avatar profil, ikon sidebar saat collapsed, loading indicator, dan app watermark.

> [!NOTE]
> Semua implementasi kode frontend atau aset grafis baru **wajib mengacu ke file SVG di atas** yang berada di dalam folder [`design-system/`](file:///Users/lanaginting/Documents/FireCal_NASA_SpaceApps_Challenge/design-system) agar tampilan visual tetap sinkron dan presisi 1:1 dengan master Figma.

---

## 3. Palet Warna Lengkap (Color Tokens)

### Solar Flare / Fire Accents
Warna primer untuk tombol interaksi (CTA), status kebakaran aktif, dan sinyal anomali termal:

| Token Name | Hex Code | RGB | Fungsi & Penggunaan |
| :--- | :--- | :--- | :--- |
| `flare.ember` | `#E04006` | `rgb(224, 64, 6)` | Extreme Fire, status bahaya puncak, bagian bawah gradasi tombol |
| `flare.orange` | `#FF6B1A` | `rgb(255, 107, 26)` | **Primary CTA**, status hotspot aktif, warna inti FireCal |
| `flare.amber` | `#FF9F1C` | `rgb(255, 159, 28)` | Hover status, peringatan termal sedang, bagian atas gradasi tombol |
| `flare.yellow` | `#FFD23F` | `rgb(255, 210, 63)` | Hotspot ekstrim, solar flare glow, highlight metrik puncak |

### Indigo Void & Deep Space
Fondasi gelap untuk latar belakang, panel elevasi, dan hierarki kedalaman antarmuka:

| Token Name | Hex Code | RGB | Fungsi & Penggunaan |
| :--- | :--- | :--- | :--- |
| `space.void` | `#05050C` | `rgb(5, 5, 12)` | **Surface Void**: Latar belakang terdalam antarmuka orbital |
| `space.base` | `#090A15` | `rgb(9, 10, 21)` | **Surface Base**: Background kanvas utama aplikasi |
| `space.panel` | `#0E1022` | `rgb(14, 16, 34)` | **Surface Panel**: Kontainer kartu metrik, sidebar navigasi |
| `space.elevated` | `#151833` | `rgb(21, 24, 51)` | **Elevated Panel**: Dropdown, popover, item yang dihover |
| `space.overlay` | `#1C2044` | `rgb(28, 32, 68)` | **Overlay**: Modal dialog, floating tooltip container |
| `space.navyDark` | `#031044` | `rgb(3, 16, 68)` | Deep Cosmic Navy dari base swatch Figma (#12:10377) |
| `space.sapphire` | `#051D87` | `rgb(5, 29, 135)` | Deep Sapphire Blue aksen dari base swatch (#12:10378) |
| `space.atmosphere`| `#71B3F7` | `rgb(113, 179, 247)`| Aksen biru atmosferik dari base swatch (#12:10381) |

### Cyber Techno Borders
Garis kontur penegas batas komponen dalam mode gelap:

| Token Name | Hex Code | Deskripsi |
| :--- | :--- | :--- |
| `border.subtle` | `#232752` | Border kontras halus untuk panel kartu dan pemisah baris |
| `border.techno` | `#3A4186` | Border techno kontras sedang untuk input dan kontur tombol |
| `border.glow` | `#5B66D6` | Cyber glow neon untuk status seleksi dan keyboard focus |
| `border.canvasSubtle` | `rgba(255, 255, 255, 0.1)` | Garis tipis 10% putih untuk pemisah kartu pada canvas |

### Heatmap Intensity Scale
Gradasi skala aktivitas kebakaran bulanan pada matriks kalender:

| Tingkat Keparahan | Rentang Deteksi | Hex Latar | Hex Teks | Catatan Visual |
| :--- | :--- | :--- | :--- | :--- |
| **Zero (0)** | 0 hotspots | `#12162B` | `#9AA6C8` | Latar biru indigo redup, tanpa anomali |
| **Low** | 1 - 50 hotspots | `#4A2612` | `#FFA56E` | Cokelat api lembut, aktivitas awal |
| **Mid** | 50 - 200 hotspots | `#8A380A` | `#FFD0B3` | Cokelat jingga hangat, aktivitas sedang |
| **High** | 200 - 500 hotspots | `#FF6B1A` | `#05050C` | Flare orange menyala, intensitas tinggi |
| **Peak** | 500+ hotspots | `#FFD23F` | `#05050C` | Solar flare yellow berkilau, darurat puncak |

### Biosphere & Flora
Elemen bio/hutan yang merepresentasikan kanopi vegetasi dan pengamatan satelit bumi:

| Token Name | Hex Code | RGB | Fungsi & Penggunaan |
| :--- | :--- | :--- | :--- |
| `flora.light` | `#5FD678` | `rgb(95, 214, 120)` | Titik awal gradien daun logomark FireCal / Vegetasi sehat |
| `flora.emerald`| `#2CBC84` | `rgb(44, 188, 132)`| Titik akhir gradien daun logomark / Kanopi hutan hujan |
| `earth.blue` | `#0180E7` | `rgb(1, 128, 231)` | Telemetri orbit satelit dan lapisan perairan NASA |

### Neutrals & Typography Colors
| Token Name | Hex Code | RGB | Fungsi |
| :--- | :--- | :--- | :--- |
| `text.primary` | `#FFFFFF` | `rgb(255, 255, 255)` | Judul utama, teks kontras tinggi, stroke ikon |
| `text.secondary`| `#F8F8F8` | `rgb(248, 248, 248)`| Off-white sekunder dari base swatch (#12:10383) |
| `text.muted` | `#9AA6C8` | `rgb(154, 166, 200)`| Deskripsi, label koordinat, legenda |
| `text.onFlare` | `#05050C` | `rgb(5, 5, 12)` | Teks kontras gelap di atas tombol orange/kuning |
| `canvas.neutral`| `#444444` | `rgb(68, 68, 68)` | Latar belakang Section Figma Base Design System |

---

## 4. Sistem Gradien (Gradients)

1. **Button Thermal Gradient** (`gradients.button`):
   ```css
   background: linear-gradient(180deg, #FF9F1C 0%, #FF6B1A 50%, #E04006 100%);
   ```
   Digunakan untuk tombol utama *Run Calibration*, *Generate Report*, dan aksi primer.

2. **Logomark Flame Gradient** (`gradients.flameMark`):
   ```css
   background: linear-gradient(163deg, #FF9F1C 34%, #FF6B1A 89%, #E04006 100%);
   ```
   Bentuk lidah api pada logo FireCal.

3. **Logomark Foliage Gradient** (`gradients.foliageMark`):
   ```css
   background: linear-gradient(180deg, #5FD678 12%, #2CBC84 77%);
   ```
   Bentuk daun / biosfer pada logo FireCal.

4. **Surface Cyber Panel Gradient** (`gradients.spaceSurface`):
   ```css
   background: linear-gradient(180deg, #12152E 0%, #0A0C18 100%);
   ```

---

## 5. Sistem Tipografi (Typography)

### Hierarki Space Grotesk
Keluarga font display untuk identitas brand dan judul data visualisasi:

| Token Name | Font Family | Size | Weight | Line Height | Tracking | Digunakan Untuk |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `displayLogo` | Space Grotesk | **277px** | Medium (500) | 1.0 | 0 | Skala Brand Logotype (Node #12:9557) |
| `headingXL` | Space Grotesk | **75px** | Medium (500) | 96px | -0.02em | Base Heading (Node #12:10390) |
| `display2XL` | Space Grotesk | **36px** | Bold (700) | 44px | -0.02em | Hero Title & Page Landmark (Node #12:10269) |
| `subheading` | Space Grotesk | **35px** | Medium (500) | 45px | -0.01em | Base Subheading (Node #12:10388) |
| `buttonMedium`| Space Grotesk | **25px** | Medium (500) | 32px | 0 | Base Button Medium (Node #12:10394) |
| `bodyBase` | Space Grotesk | **22px** | Regular (400) | 28px | 0 | Base Body Text (Node #12:10392) |
| `headingL` | Space Grotesk | **24px** | SemiBold (600)| 32px | -0.01em | Panel Header & Modal Titles (#12:10271) |
| `headingM` | Space Grotesk | **18px** | SemiBold (600)| 24px | 0 | Section Header & Accordion (#12:10273) |

### Hierarki Antarmuka (Figtree / Sans)
Font antarmuka pendukung untuk teks panjang, form, dan kontrol UI mikro:

| Token Name | Font Family | Size | Weight | Line Height | Digunakan Untuk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `bodyLarge` | Figtree | **15px** | Medium (500) | 24px | Paragraf penjelasan & deskripsi (Node #12:10277) |
| `uiSemiBold` | Figtree | **13px** | SemiBold (600)| 18px | Label tombol navigasi, filter chip (Node #12:10279) |
| `caption` | Figtree | **12px** | Regular (400) | 16px | Metadata satelit, timestamp koordinat (Node #12:10280) |
| `badge` | Figtree | **11px** | Bold (700) | 14px | Pill badge sensor: `VIIRS 375m`, `MODIS 1km` |

### Monospace Data (JetBrains Mono)
- Digunakan khusus untuk kolom angka tabel, koordinat lintang/bujur (`[-0.25° Lat, 112.5° Lon]`), dan tick label waktu:
  ```css
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
  ```

---

## 6. Spesimen Komponen UI

### 1. Cyber Primary Action Button
```html
<button class="fc-btn-primary">
  RUN CALIBRATION
</button>
```
```css
.fc-btn-primary {
  background: linear-gradient(180deg, #FF9F1C 0%, #FF6B1A 50%, #E04006 100%);
  color: #05050C;
  font-family: 'Figtree', sans-serif;
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.05em;
  padding: 12px 24px;
  border-radius: 8px;
  border: none;
  box-shadow: 0px 0px 20px rgba(255, 107, 26, 0.4);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.fc-btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0px 0px 28px rgba(255, 107, 26, 0.6);
}
```

### 2. Secondary Cyber Outline Button
```css
.fc-btn-secondary {
  background: #090A15;
  color: #FFFFFF;
  border: 1.5px solid #3A4186;
  font-family: 'Figtree', sans-serif;
  font-weight: 600;
  font-size: 13px;
  padding: 12px 20px;
  border-radius: 8px;
}
.fc-btn-secondary:hover {
  border-color: #5B66D6;
  box-shadow: 0 0 12px rgba(91, 102, 214, 0.3);
}
```

### 3. Metric KPI Card
```css
.fc-kpi-card {
  background: #0E1022;
  border: 1px solid #232752;
  border-radius: 12px;
  padding: 24px;
  border-top: 3px solid #FF6B1A;
}
```

---

## 7. Panduan Penggunaan (Figma & Kode)

### A. Cara Memasukkan ke Figma (Variables & Styles)
Kami telah menyediakan script otomatis di file [figma-setup.js](file:///Users/lanaginting/Documents/FireCal_NASA_SpaceApps_Challenge/design-system/figma-setup.js):

1. Buka aplikasi **Figma Desktop** dengan file dokumen proyek Anda.
2. Buka Developer Console Figma:
   - macOS: Tekan <kbd>Cmd</kbd> + <kbd>Option</kbd> + <kbd>I</kbd>
   - Windows: Tekan <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>I</kbd>
   *(Atau buka menu Figma > Plugins > Development > Open Console)*
3. Pilih tab **Console**.
4. Salin seluruh isi kode dari file [figma-setup.js](file:///Users/lanaginting/Documents/FireCal_NASA_SpaceApps_Challenge/design-system/figma-setup.js), paste ke dalam Console, lalu tekan <kbd>Enter</kbd>.
5. **Selesai!** Figma akan otomatis membuat:
   - Koleksi **Local Variables** bernama `FireCal Design System` dengan seluruh warna.
   - Seluruh **Local Text Styles** yang sudah dikelompokkan dengan rapi (`Space Grotesk/...` dan `Interface/...`).

*(Alternatif: Anda juga bisa menggunakan plugin **Scripter** di Figma Community, paste kode, lalu klik Run).*

---

### B. Penggunaan di Frontend / Web App
Semua token telah diekspor ke dalam JavaScript dan JSON:

```javascript
// Import color tokens & gradients
import { colors, gradients, semanticColors } from './design-system/variables.js';

// Import typography configurations
import { fontFamilies, textStyles } from './design-system/styles.js';

// Contoh penggunaan:
console.log(colors.flare.orange); // "#FF6B1A"
console.log(colors.space.void);   // "#05050C"
console.log(textStyles.headingXL.fontSize); // "75px"
```

Atau menggunakan [tokens.json](file:///Users/lanaginting/Documents/FireCal_NASA_SpaceApps_Challenge/design-system/tokens.json) untuk tool seperti Style Dictionary, Tailwind config, atau CSS-in-JS.
