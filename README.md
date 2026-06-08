# 🌾 AgroAI: Intelligent Seed & Fertilizer Recommendation System

> **AgroAI** adalah platform asisten cerdas berbasis *Reasoning AI* yang dirancang untuk membantu petani mengoptimalkan hasil panen sekaligus menekan biaya produksi.

Sistem ini bekerja dengan menganalisis karakteristik geografis lahan untuk merekomendasikan komoditas terbaik, lalu menyusun strategi pemupukan yang presisi dan ekonomis berdasarkan fase pertumbuhan tanaman serta fluktuasi harga pasar secara *real-time*.

Berbeda dengan AI konvensional yang sering mengalami halusinasi data, AgroAI menggunakan pendekatan **Neuro-Symbolic** — menggabungkan kecerdasan LLM dengan validasi aturan database lokal — menggunakan arsitektur **ReAct (Reason + Act)**.

---

## 🚀 Fitur Utama

### 1. Smart Land & Crop Matching (Pemilihan Komoditas)

- **Analisis Multi-Variabel** — Mengombinasikan Jenis Tanah (misal: Aluvial, Pasir, Andosol) dan Tingkat Dataran (Rendah/Tinggi via mdpl) untuk menentukan kecocokan hayati tanaman.
- **Proyeksi Nilai Ekonomis** — AI tidak hanya menyarankan tanaman yang subur, tetapi juga menganalisis tren harga jual pasar terkini di wilayah tersebut untuk memaksimalkan profitabilitas petani.

### 2. Dynamic Fertilization & Cost Optimization (Nutrisi & Harga Relatif)

- **Sinkronisasi Fase Tumbuh** — Rekomendasi takaran unsur hara (N, P, K) yang dinamis, beradaptasi otomatis mengikuti fase tanaman (Vegetatif, Generatif, hingga Pematangan).
- **Kalkulator Harga Relatif** — AI secara cerdas membandingkan harga pasar berbagai opsi pupuk (misal: membandingkan efisiensi biaya antara membeli pupuk majemuk NPK langsung vs meracik sendiri dari pupuk tunggal seperti Urea + SP36 + KCl).

---

## 🛠️ Arsitektur Sistem & Alur Penalaran (Reasoning)

Sistem ini dibangun menggunakan arsitektur **Agentic AI** yang memisahkan logika bahasa (LLM) dengan validasi data riil (Database/API):

```
User Input
    │
    ▼
AI Reasoning (ReAct Framework)
    │  Menganalisis maksud pengguna & memutuskan tool yang dipanggil
    ▼
Database Retrieval
    │  Backend mengeksekusi query SQL/ORM ke database lokal
    │  → Data kecocokan tanaman
    │  → Tabel harga pupuk terbaru
    ▼
Contextual Output
    │  AI melakukan penalaran biaya & membungkus hasil menjadi
    └→ Rekomendasi strategis yang mudah dipahami petani
```

| Tahap | Komponen | Keterangan |
|-------|----------|------------|
| **1. User Input** | Frontend / API | Petani memasukkan kondisi lahan (contoh: Tanah Liat, Dataran Rendah) |
| **2. AI Reasoning** | ReAct Framework | AI memutuskan untuk memanggil fungsi internal (Tools), bukan menebak |
| **3. DB Retrieval** | SQLAlchemy + PostgreSQL | Query data kecocokan tanaman & harga pupuk terkini |
| **4. Output** | LLM Response | Rekomendasi strategis yang kontekstual dan akurat |

---

## 💻 Tech Stack

| Layer | Teknologi | Alasan Pemilihan |
|-------|-----------|-----------------|
| **Backend Framework** | FastAPI (Python) | Performa asinkronus (`async`/`await`), validasi otomatis via Pydantic, Swagger UI built-in |
| **AI Orchestration** | LangChain / Pydantic AI | Framework agen penalaran yang modular dan extensible |
| **Database** | PostgreSQL / SQLite | Pengelolaan data spasial pertanian dan harga komoditas |
| **ORM** | SQLAlchemy | Abstraksi database yang robust dan mendukung query kompleks |

---

## 📁 Struktur Proyek

```
agroai/
├── app/
│   ├── api/            # Route & endpoint FastAPI
│   ├── agents/         # Logika ReAct Agent & Tools
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   └── database/       # Koneksi & seed data
├── data/
│   ├── crops.json      # Data kecocokan tanaman per jenis tanah
│   └── fertilizers.json # Tabel harga & kandungan pupuk
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## ⚙️ Instalasi & Menjalankan Proyek

### Prasyarat

- Python 3.10+
- PostgreSQL (atau SQLite untuk development)

### Langkah Instalasi

```bash
# 1. Clone repository
git clone https://github.com/username/agroai.git
cd agroai

# 2. Buat virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Salin dan konfigurasi environment variable
cp .env.example .env
# Edit .env sesuai konfigurasi database dan API key

# 5. Jalankan migrasi database
alembic upgrade head

# 6. Jalankan server
uvicorn app.main:app --reload
```

Server akan berjalan di `http://localhost:8000`. Dokumentasi API tersedia di `http://localhost:8000/docs`.

---

## 📖 Contoh Penggunaan

**Request:**
```json
POST /api/v1/recommend
{
  "soil_type": "Aluvial",
  "elevation_mdpl": 150,
  "land_area_ha": 2.5,
  "location": "Jawa Tengah"
}
```

**Response:**
```json
{
  "recommended_crops": [
    {
      "name": "Padi IR64",
      "suitability_score": 0.92,
      "estimated_price_per_kg": 5200,
      "reasoning": "Tanah aluvial dengan ketinggian rendah sangat ideal untuk padi sawah..."
    }
  ],
  "fertilization_plan": {
    "vegetative_phase": { "N": "90 kg/ha", "P": "45 kg/ha", "K": "30 kg/ha" },
    "generative_phase": { "N": "45 kg/ha", "P": "20 kg/ha", "K": "60 kg/ha" },
    "cost_comparison": {
      "npk_compound": { "total_cost": 1250000, "label": "NPK Majemuk" },
      "single_fertilizer_mix": { "total_cost": 980000, "label": "Urea + SP36 + KCl" },
      "recommendation": "Meracik pupuk tunggal lebih hemat 21.6% untuk luas lahan ini"
    }
  }
}
```

---

## 🤝 Kontribusi

Kontribusi sangat disambut! Silakan buka *issue* terlebih dahulu untuk mendiskusikan perubahan besar yang ingin Anda buat.

1. Fork repositori ini
2. Buat branch fitur (`git checkout -b feature/nama-fitur`)
3. Commit perubahan (`git commit -m 'feat: tambah fitur X'`)
4. Push ke branch (`git push origin feature/nama-fitur`)
5. Buka Pull Request

---

## 📄 Lisensi

Didistribusikan di bawah lisensi MIT. Lihat [`LICENSE`](LICENSE) untuk informasi lebih lanjut.

---

<p align="center">Dibuat dengan ❤️ untuk para petani Indonesia</p>
