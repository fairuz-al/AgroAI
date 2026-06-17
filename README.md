# 🌾 AgroAI: Sistem Rekomendasi Cerdas Komoditas Pertanian Berbasis Sistem Pakar & AI

> **AgroAI** adalah platform asisten cerdas agronomis yang dirancang untuk membantu petani mengoptimalkan produktivitas lahan sekaligus menekan biaya produksi secara strategis. 

Sistem ini bekerja dengan menganalisis karakteristik geografis lahan secara *real-time*, merekomendasikan jenis komoditas yang paling sesuai dan menguntungkan, serta merancang rencana pemupukan dinamis (N, P, K) berdasarkan fase pertumbuhan tanaman dan fluktuasi harga pasar.

---

## 🚀 Fitur Utama

### 1. Smart Land & Crop Matching (Pemilihan Komoditas)
- **Fuzzy Suitability Scoring** — Mengukur tingkat kecocokan komoditas menggunakan logika fuzzy Mamdani berdasarkan parameter jenis tanah (Aluvial, Andosol, Liat, Pasir, dll.), elevasi lahan (meter di atas permukaan laut / mdpl), serta daya tarik harga pasar.
- **GPS Auto-Resolver** — Secara otomatis mendeteksi ketinggian (elevasi), nama wilayah geografis, dan memprediksi jenis tanah default berdasarkan koordinat GPS latitude & longitude.
- **Sinkronisasi Harga Pasar Terkini** — Mengambil tren harga jual komoditas regional (terintegrasi dengan BAPPEBTI) untuk memberikan proyeksi profitabilitas riil.

### 2. Dynamic Fertilization Plan (Rencana Pemupukan Dinamis)
- **Kebutuhan Nutrisi Spesifik Tanaman** — Menyediakan formulasi hara N, P, K yang dinamis untuk fase vegetatif (pertumbuhan) dan generatif (pembuahan) yang disesuaikan secara ilmiah untuk 9 komoditas utama (Padi, Jagung, Kentang, Bawang Merah, Semangka, Cabai Rawit, Tomat, Singkong, dan Kedelai).
- **Kalkulator Efisiensi Pupuk** — Membandingkan pengeluaran riil antara penggunaan **Pupuk Majemuk (NPK Phonska)** dengan **Campuran Pupuk Tunggal (Urea + SP-36 + KCl)** berdasarkan luas lahan (hektar) untuk menemukan biaya operasional terendah.

### 3. Tampilan Antarmuka Modern & Bersih (Premium UI)
- **Emerald Theme** — Palet warna hijau zamrud modern yang serasi, bersih, dan memanjakan mata, dirancang khusus untuk nuansa agroteknologi.
- **Minimalist Panel Headers** — Menghilangkan tajuk panel solid kontras lama, digantikan dengan garis batas tipis yang elegan dan aksen warna tematik untuk nuansa SaaS premium.
- **Animated Suitability Ring** — Indikator persentase kecocokan lingkaran interaktif berbasis animasi SVG path stroke-dashoffset.
- **Sleek Micro-interactions** — Dilengkapi efek hover translasi yang halus, perluasan rincian profitabilitas yang responsif, serta animasi pemuatan yang mulus.
- **Bebas dari Simbol AI Berlebihan** — Menghilangkan emoji dekoratif yang ramai serta jargon AI bombastis agar sistem terlihat bersih dan berkelas industri.

### 4. Halaman Riwayat Pengembangan (History Ongoing)
- Terintegrasi menu `/history` khusus yang merinci status pengembangan riwayat analisis secara transparan (*ongoing* karena menunggu migrasi skema tabel database `analysis_history`), dilengkapi visual kartu log pratinjau semi-transparan yang estetik.

---

## 🛠️ Arsitektur Sistem & Alur Penalaran (Reasoning Flow)

AgroAI mengadopsi pendekatan **Neuro-Symbolic** (Hybrid AI) yang memisahkan logika interpretasi bahasa dengan kalkulasi aturan agronomis kaku:

```
          [ Masukan Lahan Petani ]
         (GPS Koordinat & Luas Lahan)
                     │
                     ▼
         [ Resolusi GPS Otomatis ]
   (Elevasi MDPL, Wilayah, & Jenis Tanah)
                     │
                     ▼
      ┌──────────────┴──────────────┐
      ▼                             ▼
[ AI Mode API ]             [ Expert System Fallback ]
(Gemini / Groq)             (Fuzzy Logic + Forward Chaining)
      │                             │
      └──────────────┬──────────────┘
                     ▼
        [ Penyelarasan Nutrisi ]
    (CROP_NUTRIENT_REQUIREMENTS Mapping)
                     │
                     ▼
      [ Kalkulator Efisiensi Biaya ]
   (Campuran Tunggal vs Majemuk NPK)
                     │
                     ▼
      [ Hasil Rekomendasi & Profit ]
```

### Jalur Keputusan (Inference Engines)
1. **Model Bahasa Besar (Gemini & Groq)**: Memproses data agronomis menggunakan model `Google Gemini 2.5 Flash` (atau Groq `Llama 3.3 70B`) untuk interpretasi kontekstual terstruktur.
2. **Sistem Pakar Lokal (Fuzzy + Forward Chaining)**: Apabila kunci API tidak terkonfigurasi atau terjadi gangguan jaringan (timeout), sistem secara otomatis mengaktifkan mesin logika lokal untuk menghitung klasifikasi tanah, zona elevasi, kelayakan komoditas, dan pembiayaan pupuk.

---

## 💻 Tech Stack

- **Backend**: FastAPI (Python 3.11) — asinkronus (`async`/`await`), performa tinggi, dan validasi data Pydantic.
- **Database**: PostgreSQL (SQLAlchemy ORM) — mendukung penyimpanan relasional relasi komoditas (`crops`), pupuk (`fertilizers`), dan log riwayat.
- **Frontend**: Vanilla HTML5, CSS3 Variables, dan Leaflet.js/Google Maps API untuk pemetaan interaktif.
- **Containerization**: Docker & Docker Compose untuk orkestrasi web server dan database database terisolasi.

---

## ⚙️ Instalasi & Menjalankan Proyek

### Menggunakan Docker Compose (Direkomendasikan)
Pastikan Anda telah memasang **Docker** dan **Docker Compose** di sistem Anda.

1. **Salin Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   *Edit file `.env` dan masukkan API Key Anda (misal `GEMINI_API_KEY` atau `GROQ_API_KEY`) jika ingin menggunakan mode AI cloud.*

2. **Jalankan Container**:
   ```bash
   docker compose up -d
   ```

3. **Inisialisasi Database (Seeding)**:
   Saat pertama kali dijalankan, sistem secara otomatis akan membuat tabel database dan mengisi data komoditas default serta harga pupuk standar di dalam lifecyle startup aplikasi.

4. **Akses Aplikasi**:
   Buka browser dan akses `http://localhost:8000`.

### Perintah Docker Bermanfaat
- **Melihat Status Kontainer**:
  ```bash
  docker compose ps
  ```
- **Melihat Log Server**:
  ```bash
  docker compose logs -f web
  ```
- **Memuat Ulang Kode setelah Edit**:
  Jika Anda mengedit kode backend di lokal, restart kontainer web agar uvicorn memuat kode terbaru:
  ```bash
  docker compose restart web
  ```
- **Menghentikan Kontainer**:
  ```bash
  docker compose down
  ```

---

## 📖 Struktur Database Seed Default

### Komoditas Terdaftar (`crops`)
- **Padi IR64** (Tanah Aluvial, 0-600 mdpl)
- **Jagung Hibrida Bisi 2** (Tanah Andosol, 0-1000 mdpl)
- **Kentang Granola** (Tanah Andosol, 1000-3000 mdpl)
- **Bawang Merah Bima** (Tanah Liat, 0-250 mdpl)
- **Semangka Tanpa Biji** (Tanah Pasir, 0-300 mdpl)
- **Cabai Rawit** (Tanah Aluvial, 0-1500 mdpl)
- **Tomat** (Tanah Andosol, 500-1500 mdpl)
- **Singkong Mukibat** (Tanah Liat, 0-800 mdpl)
- **Kedelai Wilis** (Tanah Aluvial, 0-500 mdpl)

### Referensi Pupuk Terdaftar (`fertilizers`)
- **Urea** (Pupuk Tunggal - N: 46%)
- **SP-36** (Pupuk Tunggal - P: 36%)
- **KCl** (Pupuk Tunggal - K: 60%)
- **NPK Phonska 15-15-15** (Pupuk Majemuk - N: 15%, P: 15%, K: 15%)
- **ZA** (Pupuk Tunggal - N: 21%)
- **Organik** (Pupuk Organik)
