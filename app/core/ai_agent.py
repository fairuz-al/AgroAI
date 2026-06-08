import os
import json
import logging
from sqlalchemy.orm import Session
from app.models import RecommendationRequest, RecommendationResponse, Crop, Fertilizer
import google.generativeai as genai

logger = logging.getLogger("uvicorn.error")

def get_recommendation(req: RecommendationRequest, db: Session) -> dict:
    """
    Generate agricultural recommendation.
    Uses Google Gemini if GEMINI_API_KEY is configured,
    otherwise falls back to a rules-based programmatic engine.
    """
    # 1. Fetch available crops and fertilizers from local database
    db_crops = db.query(Crop).all()
    db_fertilizers = db.query(Fertilizer).all()

    # Format DB context for LLM or local calculations
    crops_data = [
        {
            "name": c.name,
            "soil_type": c.soil_type,
            "elevation_min": c.elevation_min,
            "elevation_max": c.elevation_max,
            "price": c.estimated_price_per_kg,
            "base_reasoning": c.base_reasoning
        } for c in db_crops
    ]

    fertilizers_data = [
        {
            "name": f.name,
            "type": f.fertilizer_type,
            "n": f.n_content,
            "p": f.p_content,
            "k": f.k_content,
            "price": f.price_per_kg
        } for f in db_fertilizers
    ]

    # Try Gemini integration if API key is provided
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            logger.info("Generating recommendation using Gemini API...")
            genai.configure(api_key=api_key)
            
            # Use gemini-1.5-flash as the standard reasoning model
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            prompt = f"""
            Anda adalah AgroAI, asisten cerdas pertanian (Reasoning AI). Tugas Anda adalah memberikan rekomendasi komoditas tanaman terbaik dan rencana pemupukan yang paling ekonomis.

            DATA MASUKAN PENGGUNA:
            - Jenis Tanah: {req.soil_type}
            - Ketinggian Lahan: {req.elevation_mdpl} mdpl
            - Luas Lahan: {req.land_area_ha} ha
            - Lokasi Wilayah: {req.location}

            DATA BASELINE DARI DATABASE LOKAL:
            Crops (Komoditas):
            {json.dumps(crops_data, indent=2)}

            Fertilizers (Pupuk & Harga per kg):
            {json.dumps(fertilizers_data, indent=2)}

            ATURAN PENALARAN (REASONING RULES):
            1. Rekomendasi Tanaman: Cari tanaman dari database yang jenis tanahnya cocok (atau mirip secara biologis) dan ketinggian lahannya berada di antara 'elevation_min' dan 'elevation_max'. Urutkan berdasarkan tingkat kecocokan ('suitability_score' antara 0.0 - 1.0). Tulis alasan singkat bahasa Indonesia ('reasoning') mengapa tanaman ini cocok.
            2. Fase Pemupukan: 
               - Fase Vegetatif membutuhkan takaran N tinggi (misal 90 kg/ha N, 45 kg/ha P, 30 kg/ha K).
               - Fase Generatif membutuhkan takaran K tinggi (misal 45 kg/ha N, 20 kg/ha P, 60 kg/ha K).
               - Sesuaikan takaran ini dengan luas lahan ({req.land_area_ha} ha). Laporkan nilai takaran dalam kg/ha (misal: "90 kg/ha").
            3. Kalkulator Perbandingan Biaya Pupuk:
               - Bandingkan total biaya pemupukan jika menggunakan Pupuk Majemuk (NPK saja) vs Pupuk Tunggal (Campuran Urea + SP-36 + KCl).
               - Hitung kebutuhan pupuk berdasarkan kandungan N-P-K dari database.
               - Contoh: Kandungan Urea = 46% N, SP-36 = 36% P, KCl = 60% K. Kandungan NPK Majemuk = 15% N, 15% P, 15% K.
               - Kalikan total berat kebutuhan pupuk masing-masing opsi dengan harga per kg dari database untuk mendapatkan 'total_cost'.
               - Berikan saran konkret ('recommendation') dalam bahasa Indonesia tentang opsi mana yang lebih menghemat pengeluaran petani dan jelaskan persentase penghematannya.

            FORMAT RESPONSE:
            Kembalikan HASIL HANYA dalam format JSON valid tanpa markdown block ```json. Struktur JSON harus persis seperti berikut:
            {{
              "recommended_crops": [
                {{
                  "name": "Nama Tanaman",
                  "suitability_score": 0.95,
                  "estimated_price_per_kg": 5000,
                  "reasoning": "Alasan detail mengapa cocok..."
                }}
              ],
              "fertilization_plan": {{
                "vegetative_phase": {{
                  "N": "90 kg/ha",
                  "P": "45 kg/ha",
                  "K": "30 kg/ha"
                }},
                "generative_phase": {{
                  "N": "45 kg/ha",
                  "P": "20 kg/ha",
                  "K": "60 kg/ha"
                }},
                "cost_comparison": {{
                  "npk_compound": {{
                    "total_cost": 1250000,
                    "label": "NPK Majemuk"
                  }},
                  "single_fertilizer_mix": {{
                    "total_cost": 980000,
                    "label": "Urea + SP36 + KCl"
                  }},
                  "recommendation": "Meracik pupuk tunggal lebih hemat 21.6% untuk luas lahan ini"
                }}
              }}
            }}
            """
            
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            
            # Remove markdown syntax blocks if returned by the LLM
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"Gemini API Error: {str(e)}. Falling back to local reasoning...")
            # If API fails, go to fallback

    # 2. Local/Programmatic Fallback Reasoning Engine
    logger.info("Executing local programmatic reasoning...")
    
    # 2.1 Calculate Crop Recommendations
    recommendations = []
    for crop in db_crops:
        # Check soil match
        soil_match = crop.soil_type.lower() == req.soil_type.lower()
        # Check elevation match
        elev_match = crop.elevation_min <= req.elevation_mdpl <= crop.elevation_max
        
        if soil_match or elev_match:
            score = 0.5
            if soil_match:
                score += 0.3
            if elev_match:
                score += 0.2
            
            # Simple details
            reasoning = f"{crop.base_reasoning} Jenis tanah {req.soil_type} dengan ketinggian {req.elevation_mdpl} mdpl di {req.location} dinilai sangat cocok untuk mengoptimalkan hasil panen."
            
            recommendations.append({
                "name": crop.name,
                "suitability_score": round(score, 2),
                "estimated_price_per_kg": crop.estimated_price_per_kg,
                "reasoning": reasoning
            })
    
    # Sort by score descending
    recommendations = sorted(recommendations, key=lambda x: x["suitability_score"], reverse=True)
    if not recommendations:
        # Generic fallback if no crops match at all
        recommendations.append({
            "name": "Padi IR64",
            "suitability_score": 0.75,
            "estimated_price_per_kg": 5500.0,
            "reasoning": "Meskipun kecocokan tanah spesifik rendah, Padi IR64 umumnya adaptif di lahan dataran rendah dengan sistem pengairan memadai."
        })

    # 2.2 Calculate Fertilization and Cost Comparison
    # Nutrient requirements (kg/ha)
    # Vegetative Phase
    veg_n_ha, veg_p_ha, veg_k_ha = 90.0, 45.0, 30.0
    # Generative Phase
    gen_n_ha, gen_p_ha, gen_k_ha = 45.0, 20.0, 60.0

    # Total nutrient required for the land area (kg)
    tot_veg_n = veg_n_ha * req.land_area_ha
    tot_veg_p = veg_p_ha * req.land_area_ha
    tot_veg_k = veg_k_ha * req.land_area_ha

    tot_gen_n = gen_n_ha * req.land_area_ha
    tot_gen_p = gen_p_ha * req.land_area_ha
    tot_gen_k = gen_k_ha * req.land_area_ha

    # Find fertilizers from database or use defaults
    urea = next((f for f in db_fertilizers if f.name.lower() == "urea"), None)
    sp36 = next((f for f in db_fertilizers if f.name.lower() == "sp-36"), None)
    kcl = next((f for f in db_fertilizers if f.name.lower() == "kcl"), None)
    npk = next((f for f in db_fertilizers if "npk" in f.name.lower()), None)

    # Defaults if db queries are empty (should not happen due to seeding)
    p_urea = urea.price_per_kg if urea else 4500.0
    p_sp36 = sp36.price_per_kg if sp36 else 5200.0
    p_kcl = kcl.price_per_kg if kcl else 8500.0
    p_npk = npk.price_per_kg if npk else 10000.0

    # Option A: Single Fertilizer Mix (Urea + SP36 + KCl)
    # We calculate based on the nutrient content:
    # Urea (46% N), SP-36 (36% P), KCl (60% K)
    # Vegetative mixes
    veg_urea = tot_veg_n / 0.46
    veg_sp36 = tot_veg_p / 0.36
    veg_kcl = tot_veg_k / 0.60
    # Generative mixes
    gen_urea = tot_gen_n / 0.46
    gen_sp36 = tot_gen_p / 0.36
    gen_kcl = tot_gen_k / 0.60

    total_urea = veg_urea + gen_urea
    total_sp36 = veg_sp36 + gen_sp36
    total_kcl = veg_kcl + gen_kcl

    cost_single = (total_urea * p_urea) + (total_sp36 * p_sp36) + (total_kcl * p_kcl)

    # Option B: NPK Compound (e.g. NPK 15-15-15)
    # To satisfy the nutrient requirements with 15-15-15 NPK:
    # NPK contains 15% N, 15% P, 15% K
    # For simplicity, we calculate based on the highest requirement or standard dosage:
    # Let's say standard practice for NPK compound is 350 kg/ha (veg) and 250 kg/ha (gen)
    npk_qty_veg = 350.0 * req.land_area_ha
    npk_qty_gen = 250.0 * req.land_area_ha
    cost_npk = (npk_qty_veg + npk_qty_gen) * p_npk

    # Savings calculation
    diff = cost_npk - cost_single
    savings_pct = (diff / cost_npk) * 100 if cost_npk > 0 else 0

    if diff > 0:
        recommendation_text = f"Meracik pupuk tunggal (Urea + SP-36 + KCl) lebih hemat {savings_pct:.1f}% (selisih Rp {int(diff):,}) untuk luas lahan {req.land_area_ha} ha dibandingkan membeli pupuk majemuk NPK."
    else:
        savings_pct_npk = (abs(diff) / cost_single) * 100
        recommendation_text = f"Membeli pupuk majemuk NPK lebih hemat {savings_pct_npk:.1f}% (selisih Rp {int(abs(diff)):,}) untuk luas lahan {req.land_area_ha} ha karena harga pupuk tunggal sedang tinggi."

    result = {
        "recommended_crops": recommendations,
        "fertilization_plan": {
            "vegetative_phase": {
                "N": f"{veg_n_ha} kg/ha",
                "P": f"{veg_p_ha} kg/ha",
                "K": f"{veg_k_ha} kg/ha"
            },
            "generative_phase": {
                "N": f"{gen_n_ha} kg/ha",
                "P": f"{gen_p_ha} kg/ha",
                "K": f"{gen_k_ha} kg/ha"
            },
            "cost_comparison": {
                "npk_compound": {
                    "total_cost": round(cost_npk, 2),
                    "label": "NPK Majemuk 15-15-15"
                },
                "single_fertilizer_mix": {
                    "total_cost": round(cost_single, 2),
                    "label": "Campuran Urea + SP-36 + KCl"
                },
                "recommendation": recommendation_text
            }
        }
    }
    return result
