import os
import json
import logging
import asyncio
from sqlalchemy.orm import Session
from app.models import RecommendationRequest, Crop, Fertilizer
from google import genai
from google.genai import types
from groq import Groq as GroqClient
from app.services.market_api import get_realtime_market_prices, get_realtime_fertilizer_prices
from app.services.gps_resolver import (
    get_elevation_from_gps,
    get_location_name_from_gps,
    get_soil_type_from_gps
)

logger = logging.getLogger("uvicorn.error")


# ==============================================================
# FUZZY LOGIC ENGINE
# Fuzzy Membership Functions & Inference System for Agricultural
# Suitability Scoring
# ==============================================================

class FuzzyMembership:
    """
    Fuzzy membership functions for agricultural input variables.
    Implements triangular and trapezoidal membership functions.
    """

    @staticmethod
    def trimf(x, a, b, c):
        """Triangular membership function: peak at b, zero at a and c."""
        if x <= a or x >= c:
            return 0.0
        elif a < x <= b:
            return (x - a) / (b - a) if (b - a) != 0 else 0.0
        elif b < x < c:
            return (c - x) / (c - b) if (c - b) != 0 else 0.0
        else:
            return 1.0

    @staticmethod
    def trapmf(x, a, b, c, d):
        """Trapezoidal membership function: full membership between b and c."""
        if x <= a or x >= d:
            return 0.0
        elif a < x <= b:
            return (x - a) / (b - a) if (b - a) != 0 else 0.0
        elif b < x <= c:
            return 1.0
        elif c < x < d:
            return (d - x) / (d - c) if (d - c) != 0 else 0.0
        else:
            return 1.0

    # --- Soil Type Fuzzy Memberships ---
    @classmethod
    def soil_suitability(cls, input_soil, crop_soil):
        """
        Fuzzy soil compatibility: exact match = 1.0, partial overlap = 0.5,
        completely incompatible = 0.1.
        """
        if input_soil.lower() == crop_soil.lower():
            return 1.0

        compatibility = {
            ("aluvial", "liat"): 0.6,
            ("liat", "aluvial"): 0.6,
            ("andosol", "aluvial"): 0.5,
            ("aluvial", "andosol"): 0.5,
            ("pasir", "aluvial"): 0.3,
            ("aluvial", "pasir"): 0.3,
            ("andosol", "laterit"): 0.5,
            ("laterit", "andosol"): 0.5,
            ("gambut", "liat"): 0.3,
            ("liat", "gambut"): 0.3,
            ("pasir", "laterit"): 0.2,
            ("laterit", "pasir"): 0.2,
        }

        key = (input_soil.lower(), crop_soil.lower())
        return compatibility.get(key, 0.1)

    # --- Elevation Fuzzy Memberships ---
    @classmethod
    def elevation_suitability(cls, input_elev, elev_min, elev_max):
        """Fuzzy elevation compatibility using trapezoidal membership."""
        if elev_min <= input_elev <= elev_max:
            center = (elev_min + elev_max) / 2.0
            half_range = (elev_max - elev_min) / 2.0

            if half_range == 0:
                return 1.0 if input_elev == elev_min else 0.0

            dist_from_center = abs(input_elev - center) / half_range
            return cls.trimf(dist_from_center, 0, 0, 1.0)
        else:
            margin = 200
            if input_elev < elev_min:
                dist = elev_min - input_elev
                return max(0, 1.0 - dist / margin) * 0.4
            else:
                dist = input_elev - elev_max
                return max(0, 1.0 - dist / margin) * 0.4

    # --- Price/Market Fuzzy Memberships ---
    @classmethod
    def price_attractiveness(cls, price, max_price):
        """Fuzzy price attractiveness: higher price = more attractive for farmers."""
        if max_price <= 0:
            return 0.5
        normalized = price / max_price
        return cls.trimf(normalized, 0.0, 0.7, 1.0)


class FuzzyInferenceEngine:
    """
    Fuzzy inference engine using Mamdani-style rules.
    """
    OUTPUT_LEVELS = {
        'very_low': 0.15, 'low': 0.35, 'medium': 0.55, 'high': 0.75, 'very_high': 0.95
    }

    @classmethod
    def classify_fuzzy_value(cls, value):
        if value >= 0.8: return 'high'
        elif value >= 0.5: return 'medium'
        else: return 'low'

    @classmethod
    def evaluate_rules(cls, soil_fuzzy, elev_fuzzy, price_fuzzy):
        soil_level = cls.classify_fuzzy_value(soil_fuzzy)
        elev_level = cls.classify_fuzzy_value(elev_fuzzy)

        rules = []
        if soil_level == 'high' and elev_level == 'high':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'very_high'))
        if soil_level == 'high' and elev_level == 'medium':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'high'))
        if soil_level == 'medium' and elev_level == 'high':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'high'))
        if soil_level == 'medium' and elev_level == 'medium':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'medium'))
        if soil_level == 'low' and elev_level == 'high':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'medium'))
        if soil_level == 'high' and elev_level == 'low':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'medium'))
        if soil_level == 'low' and elev_level == 'low':
            rules.append((min(soil_fuzzy, elev_fuzzy), 'low'))
        if soil_fuzzy < 0.2:
            rules.append((soil_fuzzy, 'very_low'))

        if not rules:
            rules.append((0.5, 'medium'))

        total_weight, weighted_sum = 0.0, 0.0
        for strength, output_level in rules:
            total_weight += strength
            weighted_sum += strength * cls.OUTPUT_LEVELS[output_level]

        base_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        price_modifier = price_fuzzy * 0.15
        return max(0.05, min(round(base_score + price_modifier, 2), 1.0))


# ==============================================================
# FORWARD CHAINING INFERENCE ENGINE
# ==============================================================

class Fact:
    def __init__(self, name, value, confidence=1.0):
        self.name = name
        self.value = value
        self.confidence = confidence

class Rule:
    def __init__(self, name, condition, action, description=""):
        self.name = name
        self.condition = condition  
        self.action = action        
        self.description = description
        self.fired = False

    def evaluate(self, facts):
        try: return self.condition(facts)
        except: return False

    def execute(self, facts):
        self.fired = True
        return self.action(facts)

class ForwardChainingEngine:
    def __init__(self):
        self.facts = []
        self.rules = []

    def add_fact(self, fact): self.facts.append(fact)
    def add_rule(self, rule): self.rules.append(rule)
    def get_fact_value(self, name):
        for f in self.facts:
            if f.name == name: return f.value
        return None
    def has_fact(self, name): return any(f.name == name for f in self.facts)

    def run(self, max_iterations=50):
        reasoning_chain = []
        iteration = 0
        while iteration < max_iterations:
            rule_fired = False
            for rule in self.rules:
                if not rule.fired and rule.evaluate(self.facts):
                    new_facts = rule.execute(self.facts)
                    reasoning_chain.append({
                        "step": len(reasoning_chain) + 1,
                        "icon": "⚙️",
                        "title": f"Rule: {rule.name}",
                        "description": rule.description
                    })
                    for fact in new_facts:
                        if not self.has_fact(fact.name):
                            self.facts.append(fact)
                            rule_fired = True
                        else:
                            for existing in self.facts:
                                if existing.name == fact.name and fact.confidence > existing.confidence:
                                    existing.value = fact.value
                                    existing.confidence = fact.confidence
                                    rule_fired = True
            if not rule_fired: break
            iteration += 1
        return reasoning_chain


def build_agro_rules(crops_data, req, fertilizers_data):
    rules = []
    rules.append(Rule(
        name="R01_Soil_Classification",
        condition=lambda facts: any(f.name == "input_soil_type" for f in facts),
        action=lambda facts: [Fact("soil_category", _classify_soil(next(f.value for f in facts if f.name == "input_soil_type")))],
        description=f"Mengklasifikasikan jenis tanah '{req.soil_type}' ke dalam kategori kesuburan untuk evaluasi lebih lanjut."
    ))

    rules.append(Rule(
        name="R02_Elevation_Zone",
        condition=lambda facts: any(f.name == "input_elevation" for f in facts),
        action=lambda facts: [Fact("elevation_zone", _classify_elevation(next(f.value for f in facts if f.name == "input_elevation")))],
        description=f"Zona elevasi {req.elevation_mdpl} mdpl diklasifikasikan untuk menentukan jenis tanaman yang cocok."
    ))

    for crop in crops_data:
        crop_name_safe = crop["name"].replace(" ", "_").lower()
        rules.append(Rule(
            name=f"R03_Eligibility_{crop_name_safe}",
            condition=lambda facts, c=crop: (any(f.name == "soil_category" for f in facts) and any(f.name == "elevation_zone" for f in facts)),
            action=lambda facts, c=crop, cn=crop_name_safe: [
                Fact(f"crop_eligible_{cn}", True,
                     confidence=FuzzyInferenceEngine.evaluate_rules(
                         FuzzyMembership.soil_suitability(req.soil_type, c["soil_type"]),
                         FuzzyMembership.elevation_suitability(req.elevation_mdpl, c["elevation_min"], c["elevation_max"]),
                         FuzzyMembership.price_attractiveness(c["price"], max(cr["price"] for cr in crops_data) if crops_data else 1)
                     ))
            ],
            description=f"Evaluasi kelayakan {crop['name']} berdasarkan kecocokan tanah, elevasi, dan daya tarik harga pasar."
        ))

    rules.append(Rule(
        name="R04_Top_Recommendation",
        condition=lambda facts: any(f.name.startswith("crop_eligible_") for f in facts),
        action=lambda facts: _select_top_crops(facts, crops_data, req),
        description="Memilih dan mengurutkan tanaman dengan skor kelayakan tertinggi berdasarkan hasil inferensi fuzzy."
    ))

    rules.append(Rule(
        name="R05_Nutrient_Requirements",
        condition=lambda facts: any(f.name.startswith("crop_eligible_") for f in facts),
        action=lambda facts: [
            Fact("veg_nutrients", {"N": 90.0, "P": 45.0, "K": 30.0}),
            Fact("gen_nutrients", {"N": 45.0, "P": 20.0, "K": 60.0})
        ],
        description="Menetapkan kebutuhan nutrisi N-P-K standar untuk fase vegetatif (N-tinggi) dan generatif (K-tinggi)."
    ))

    rules.append(Rule(
        name="R06_Cost_Calculation",
        condition=lambda facts: any(f.name == "veg_nutrients" for f in facts),
        action=lambda facts: _calculate_costs(facts, fertilizers_data, req),
        description=f"Menghitung dan membandingkan total biaya pemupukan untuk lahan seluas {req.land_area_ha} ha menggunakan harga riil."
    ))
    return rules

def _classify_soil(soil_type):
    if soil_type.lower() in ["aluvial", "andosol"]: return "high_fertility"
    elif soil_type.lower() in ["liat", "laterit"]: return "medium_fertility"
    return "low_fertility"

def _classify_elevation(elevation):
    if elevation < 200: return "lowland"
    elif elevation < 600: return "mid_elevation"
    elif elevation < 1000: return "highland"
    return "mountainous"

def _select_top_crops(facts, crops_data, req):
    eligible = []
    for f in facts:
        if f.name.startswith("crop_eligible_") and f.value:
            crop_key = f.name.replace("crop_eligible_", "")
            for crop in crops_data:
                if crop["name"].replace(" ", "_").lower() == crop_key:
                    eligible.append((crop, f.confidence))
    eligible.sort(key=lambda x: x[1], reverse=True)
    if not eligible: eligible = [(c, 0.5) for c in crops_data]
    return [Fact("top_crops", eligible)]

def _calculate_costs(facts, fertilizers_data, req):
    f_prices = {f["name"].lower(): f["price"] for f in fertilizers_data}
    p_urea = f_prices.get("urea", 1800.0)
    p_sp36 = f_prices.get("sp-36", 2000.0)
    p_kcl = f_prices.get("kcl", 9500.0)
    p_npk = next((v for k, v in f_prices.items() if "npk" in k), 2300.0)

    veg_n = next((f.value.get("N", 90.0) for f in facts if f.name == "veg_nutrients"), 90.0)
    veg_p = next((f.value.get("P", 45.0) for f in facts if f.name == "veg_nutrients"), 45.0)
    veg_k = next((f.value.get("K", 30.0) for f in facts if f.name == "veg_nutrients"), 30.0)
    gen_n = next((f.value.get("N", 45.0) for f in facts if f.name == "gen_nutrients"), 45.0)
    gen_p = next((f.value.get("P", 20.0) for f in facts if f.name == "gen_nutrients"), 20.0)
    gen_k = next((f.value.get("K", 60.0) for f in facts if f.name == "gen_nutrients"), 60.0)

    tot_nutrients = {
        "urea": (veg_n + gen_n) * req.land_area_ha / 0.46,
        "sp36": (veg_p + gen_p) * req.land_area_ha / 0.36,
        "kcl": (veg_k + gen_k) * req.land_area_ha / 0.60
    }
    cost_single = (tot_nutrients["urea"] * p_urea) + (tot_nutrients["sp36"] * p_sp36) + (tot_nutrients["kcl"] * p_kcl)
    npk_qty_total = (350.0 + 250.0) * req.land_area_ha
    cost_npk = npk_qty_total * p_npk

    return [Fact("cost_analysis", {"cost_single": round(cost_single, 2), "cost_npk": round(cost_npk, 2), "tot_nutrients": tot_nutrients})]


def fmt_rp(val: float) -> str:
    return f"Rp {int(round(val)):,}".replace(",", ".")

def fmt_kg(val: float) -> str:
    return f"{int(round(val)):,}".replace(",", ".")

async def get_recommendation(req: RecommendationRequest, db: Session) -> dict:
    # Resolusi GPS otomatis jika koordinat dikirimkan dan parameter kosong
    if req.elevation_mdpl is None or req.elevation_mdpl <= 0:
        req.elevation_mdpl = await get_elevation_from_gps(req.latitude, req.longitude)
    if req.location is None or req.location == "":
        req.location = await get_location_name_from_gps(req.latitude, req.longitude)
    if req.soil_type is None or req.soil_type == "":
        req.soil_type = get_soil_type_from_gps(req.latitude, req.longitude, req.elevation_mdpl)

    db_crops = db.query(Crop).all()
    db_fertilizers = db.query(Fertilizer).all()

    live_prices, live_fertilizers = await asyncio.gather(
        get_realtime_market_prices(),
        get_realtime_fertilizer_prices()
    )

    crops_data = []
    for c in db_crops:
        matched_price = c.estimated_price_per_kg
        if live_prices:
            for live_name, live_price in live_prices.items():
                if live_name in c.name.lower() or c.name.lower() in live_name:
                    matched_price = live_price
                    break
        crops_data.append({
            "name": c.name, "soil_type": c.soil_type, "elevation_min": c.elevation_min,
            "elevation_max": c.elevation_max, "price": matched_price, "base_reasoning": c.base_reasoning,
            "seed_cost_per_ha": c.seed_cost_per_ha or 0.0,
            "yield_per_ha": c.yield_per_ha or 0.0
        })

    fertilizers_data = []
    for f in db_fertilizers:
        matched_f_price = f.price_per_kg
        if live_fertilizers:
            for live_f_name, live_f_price in live_fertilizers.items():
                if live_f_name in f.name.lower():
                    matched_f_price = live_f_price
                    break
        fertilizers_data.append({
            "name": f.name, "type": f.fertilizer_type, "n": f.n_content,
            "p": f.p_content, "k": f.k_content, "price": matched_f_price
        })

    filtered_crops = [crop for crop in crops_data if crop["soil_type"].lower() == req.soil_type.lower() or crop["elevation_min"] <= req.elevation_mdpl <= crop["elevation_max"]]
    if not filtered_crops: filtered_crops = crops_data

    # Shared prompt for all AI providers
    schema_inst = """
    Wajib mengembalikan format JSON murni dengan arsitektur key berikut:
    {
      "recommended_crops": [
        {"name": "Nama Tanaman", "suitability_score": 0.95, "estimated_price_per_kg": 5000, "reasoning": "Penjelasan detail analitis..."}
      ],
      "fertilization_plan": {
        "vegetative_phase": {"N": "90 kg/ha", "P": "45 kg/ha", "K": "30 kg/ha"},
        "generative_phase": {"N": "45 kg/ha", "P": "20 kg/ha", "K": "60 kg/ha"},
        "cost_comparison": {
          "npk_compound": {"total_cost": 120000, "label": "NPK Majemuk"},
          "single_fertilizer_mix": {"total_cost": 95000, "label": "Campuran Urea + SP-36 + KCl"},
          "recommendation": "Rekomendasi taktis penghematan biaya pemupukan..."
        }
      }
    }
    """

    prompt = f"""
    Anda adalah AgroAI, sistem pakar agronomis cerdas. Analisis data di bawah ini dan berikan keputusan taktis terstruktur.
    {schema_inst}

    MASUKAN LAHAN PETANI:
    - Jenis Tanah: {req.soil_type}
    - Ketinggian: {req.elevation_mdpl} mdpl
    - Luas Lahan: {req.land_area_ha} ha
    - Lokasi: {req.location}

    DATA REFERENSI REAL-TIME:
    Komoditas & Harga: {json.dumps(filtered_crops)}
    Harga Pupuk Terkini: {json.dumps(fertilizers_data)}
    """

    # Helper: process AI result into final response dict
    def process_ai_result(ai_result: dict, ai_mode: str, model_name: str) -> dict:
        cost_npk = float(ai_result.get("fertilization_plan", {}).get("cost_comparison", {}).get("npk_compound", {}).get("total_cost", 0.0))
        cost_single = float(ai_result.get("fertilization_plan", {}).get("cost_comparison", {}).get("single_fertilizer_mix", {}).get("total_cost", 0.0))

        qty_npk = 600.0 * req.land_area_ha
        qty_urea = 135.0 * req.land_area_ha / 0.46
        qty_sp36 = 65.0 * req.land_area_ha / 0.36
        qty_kcl = 90.0 * req.land_area_ha / 0.60
        qty_single = qty_urea + qty_sp36 + qty_kcl

        for crop_rec in ai_result.get("recommended_crops", []):
            db_crop = next((c for c in db_crops if c.name.lower() in crop_rec.get("name", "").lower() or crop_rec.get("name", "").lower() in c.name.lower()), None)
            y_ha = db_crop.yield_per_ha if db_crop else 6000.0
            s_ha = db_crop.seed_cost_per_ha if db_crop else 375000.0
            price_kg = float(crop_rec.get("estimated_price_per_kg", db_crop.estimated_price_per_kg if db_crop else 5200.0))

            harvest_revenue = y_ha * req.land_area_ha * price_kg
            seed_cost = s_ha * req.land_area_ha

            crop_rec["yield_per_ha"] = y_ha
            crop_rec["seed_cost_per_ha"] = s_ha
            crop_rec["harvest_revenue"] = harvest_revenue
            crop_rec["fertilizer_cost_npk"] = cost_npk
            crop_rec["fertilizer_cost_single"] = cost_single
            crop_rec["profit_npk"] = harvest_revenue - (seed_cost + cost_npk)
            crop_rec["profit_single"] = harvest_revenue - (seed_cost + cost_single)
            crop_rec["fertilizer_qty_npk"] = qty_npk
            crop_rec["fertilizer_qty_single"] = qty_single
            crop_rec["fertilizer_urea_kg"] = qty_urea
            crop_rec["fertilizer_sp36_kg"] = qty_sp36
            crop_rec["fertilizer_kcl_kg"] = qty_kcl

            crop_rec["estimated_price_per_kg_str"] = fmt_rp(price_kg)
            crop_rec["seed_cost_per_ha_str"] = fmt_rp(s_ha)
            crop_rec["seed_cost_total_str"] = fmt_rp(seed_cost)
            crop_rec["harvest_revenue_str"] = fmt_rp(harvest_revenue)
            crop_rec["fertilizer_cost_npk_str"] = fmt_rp(cost_npk)
            crop_rec["fertilizer_cost_single_str"] = fmt_rp(cost_single)
            crop_rec["profit_npk_str"] = fmt_rp(crop_rec["profit_npk"])
            crop_rec["profit_single_str"] = fmt_rp(crop_rec["profit_single"])
            crop_rec["fertilizer_qty_npk_str"] = fmt_kg(qty_npk)
            crop_rec["fertilizer_qty_single_str"] = fmt_kg(qty_single)
            crop_rec["fertilizer_urea_kg_str"] = fmt_kg(qty_urea)
            crop_rec["fertilizer_sp36_kg_str"] = fmt_kg(qty_sp36)
            crop_rec["fertilizer_kcl_kg_str"] = fmt_kg(qty_kcl)

        ai_result["ai_mode"] = ai_mode

        cost_comp = ai_result.get("fertilization_plan", {}).get("cost_comparison", {})
        if cost_comp:
            if "npk_compound" in cost_comp:
                cost_comp["npk_compound"]["total_cost_str"] = fmt_rp(cost_npk)
                cost_comp["npk_compound"]["pct"] = (cost_npk / max(cost_npk, cost_single, 1.0)) * 100
            if "single_fertilizer_mix" in cost_comp:
                cost_comp["single_fertilizer_mix"]["total_cost_str"] = fmt_rp(cost_single)
                cost_comp["single_fertilizer_mix"]["pct"] = (cost_single / max(cost_npk, cost_single, 1.0)) * 100
            diff = abs(cost_npk - cost_single)
            cost_comp["savings_str"] = fmt_rp(diff)
            cost_comp["savings_pct"] = (diff / max(cost_npk, cost_single, 1)) * 100
            cost_comp["is_single_cheaper"] = cost_single < cost_npk

        ai_result["reasoning_chain"] = [
            {"step": 1, "icon": "🔍", "title": "Data Retrieval", "description": "Mengambil data baseline komoditas dari DB lokal serta menyinkronkan live market prices BAPPEBTI."},
            {"step": 2, "icon": "🧠", "title": f"Neural AI Inference ({model_name})", "description": f"Memproses kondisi spesifik lahan terintegrasi dengan model {model_name}."},
            {"step": 3, "icon": "📊", "title": "Optimasi Finansial", "description": f"Menganalisis perbandingan efisiensi biaya pemupukan campuran tunggal vs majemuk untuk luas {req.land_area_ha} ha."}
        ]
        ai_result["analysis_summary"] = (
            f"Analisis berbasis {model_name} berhasil dilakukan untuk wilayah {req.location}. "
            f"Sistem mengevaluasi kecocokan tanah {req.soil_type} di ketinggian {req.elevation_mdpl} mdpl "
            f"untuk menghasilkan kalkulasi agronomis yang optimal bagi petani."
        )
        return ai_result

    # ==========================================
    # AI PROVIDER 1: GROQ (Fast, Free Tier)
    # ==========================================
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            logger.info("Mengeksekusi rekomendasi via Groq API (Llama 3.3 70B)...")
            groq_client = GroqClient(api_key=groq_key)

            def call_groq():
                return groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Anda adalah AgroAI, sistem pakar agronomis. Selalu balas dalam format JSON murni sesuai skema yang diminta."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=4096,
                )

            groq_response = await asyncio.wait_for(asyncio.to_thread(call_groq), timeout=30.0)
            groq_result = json.loads(groq_response.choices[0].message.content.strip())
            return process_ai_result(groq_result, "groq", "Groq Llama 3.3 70B")

        except asyncio.TimeoutError:
            logger.error("Groq API Error: Request timed out after 30 seconds.")
        except Exception as e:
            logger.error(f"Groq API Error: {type(e).__name__}: {str(e)[:200]}")

    # ==========================================
    # AI PROVIDER 2: GOOGLE GEMINI
    # ==========================================
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            logger.info("Mengeksekusi rekomendasi via Gemini API...")
            ai_client = genai.Client(api_key=gemini_key)

            # 2. Pemanggilan Endpoint dengan model fallback jika model utama overload
            def call_gemini(model_name="gemini-2.5-flash"):
                return ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )

            # Try primary model, fallback to gemini-2.0-flash if overloaded
            try:
                response = await asyncio.wait_for(asyncio.to_thread(call_gemini, "gemini-2.5-flash"), timeout=30.0)
            except Exception as primary_err:
                err_msg = str(primary_err)
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "high demand" in err_msg.lower() or "429" in err_msg:
                    logger.warning("Gemini 2.5 Flash overloaded, falling back to gemini-2.0-flash...")
                    response = await asyncio.wait_for(asyncio.to_thread(call_gemini, "gemini-2.0-flash"), timeout=30.0)
                else:
                    raise primary_err

            gemini_result = json.loads(response.text.strip())
            return process_ai_result(gemini_result, "gemini", "Google Gemini 2.5 Flash")

        except asyncio.TimeoutError:
            logger.error("Gemini API Error: Request timed out after 30 seconds. Mengaktifkan sistem pakar lokal otomatis (Fallback)...")

        except Exception as e:
            logger.error(f"Gemini API Error: {type(e).__name__}: {str(e)}. Mengaktifkan sistem pakar lokal otomatis (Fallback)...")

    # --- JALUR CADANGAN (FALLBACK): LOCAL EXPERT SYSTEM ---
    logger.info("Executing local Fuzzy Logic + Forward Chaining reasoning engine...")
    engine = ForwardChainingEngine()
    engine.add_fact(Fact("input_soil_type", req.soil_type))
    engine.add_fact(Fact("input_elevation", req.elevation_mdpl))
    engine.add_fact(Fact("input_land_area", req.land_area_ha))
    engine.add_fact(Fact("input_location", req.location))

    for rule in build_agro_rules(filtered_crops, req, fertilizers_data):
        engine.add_rule(rule)

    rules_chain = engine.run()
    reasoning_chain = [
        {"step": 1, "icon": "📥", "title": "Input Collection", "description": f"Menerima input parameter lahan: {req.soil_type}, {req.elevation_mdpl} mdpl."},
        {"step": 2, "icon": "🔍", "title": "Data Pruning", "description": f"Menyaring kandidat komoditas berdasarkan kecocokan wilayah terdekat."}
    ] + rules_chain

    top_crops_fact = engine.get_fact_value("top_crops")
    cost_analysis = engine.get_fact_value("cost_analysis")

    recommendations = []
    if top_crops_fact:
        for crop, fuzzy_score in top_crops_fact:
            price_str = fmt_rp(crop['price'])
            reasoning = f"{crop['base_reasoning']} Evaluasi logika fuzzy menunjukkan kecocokan tanah {req.soil_type} sebesar {int(fuzzy_score * 100)}% pada elevasi {req.elevation_mdpl} mdpl. Harga pasar saat ini berkisar {price_str}/kg."
            recommendations.append({"name": crop["name"], "suitability_score": fuzzy_score, "estimated_price_per_kg": crop["price"], "reasoning": reasoning})
    
    recommendations = sorted(recommendations, key=lambda x: x["suitability_score"], reverse=True)
    if not recommendations:
        recommendations.append({"name": "Padi IR64", "suitability_score": 0.70, "estimated_price_per_kg": 5200.0, "reasoning": "Fallback data aktif dikarenakan ketidakcocokan ekstrem parameter tanah."})
    
    cost_single = cost_analysis["cost_single"] if cost_analysis else 0.0
    cost_npk = cost_analysis["cost_npk"] if cost_analysis else 0.0

    qty_npk = 600.0 * req.land_area_ha
    qty_urea = 135.0 * req.land_area_ha / 0.46
    qty_sp36 = 65.0 * req.land_area_ha / 0.36
    qty_kcl = 90.0 * req.land_area_ha / 0.60
    qty_single = qty_urea + qty_sp36 + qty_kcl

    # Hitung profit untuk rekomendasi mesin inferensi lokal
    for crop_rec in recommendations:
        db_crop = next((c for c in db_crops if c.name.lower() in crop_rec["name"].lower() or crop_rec["name"].lower() in c.name.lower()), None)
        y_ha = db_crop.yield_per_ha if db_crop else 6000.0
        s_ha = db_crop.seed_cost_per_ha if db_crop else 375000.0
        price_kg = float(crop_rec["estimated_price_per_kg"])
        
        harvest_revenue = y_ha * req.land_area_ha * price_kg
        seed_cost = s_ha * req.land_area_ha
        
        crop_rec["yield_per_ha"] = y_ha
        crop_rec["seed_cost_per_ha"] = s_ha
        crop_rec["harvest_revenue"] = harvest_revenue
        crop_rec["fertilizer_cost_npk"] = cost_npk
        crop_rec["fertilizer_cost_single"] = cost_single
        crop_rec["profit_npk"] = harvest_revenue - (seed_cost + cost_npk)
        crop_rec["profit_single"] = harvest_revenue - (seed_cost + cost_single)

        # Set numeric fertilizer quantities
        crop_rec["fertilizer_qty_npk"] = qty_npk
        crop_rec["fertilizer_qty_single"] = qty_single
        crop_rec["fertilizer_urea_kg"] = qty_urea
        crop_rec["fertilizer_sp36_kg"] = qty_sp36
        crop_rec["fertilizer_kcl_kg"] = qty_kcl

        # Set string formatted versions
        crop_rec["estimated_price_per_kg_str"] = fmt_rp(price_kg)
        crop_rec["seed_cost_per_ha_str"] = fmt_rp(s_ha)
        crop_rec["seed_cost_total_str"] = fmt_rp(seed_cost)
        crop_rec["harvest_revenue_str"] = fmt_rp(harvest_revenue)
        crop_rec["fertilizer_cost_npk_str"] = fmt_rp(cost_npk)
        crop_rec["fertilizer_cost_single_str"] = fmt_rp(cost_single)
        crop_rec["profit_npk_str"] = fmt_rp(crop_rec["profit_npk"])
        crop_rec["profit_single_str"] = fmt_rp(crop_rec["profit_single"])
        crop_rec["fertilizer_qty_npk_str"] = fmt_kg(qty_npk)
        crop_rec["fertilizer_qty_single_str"] = fmt_kg(qty_single)
        crop_rec["fertilizer_urea_kg_str"] = fmt_kg(qty_urea)
        crop_rec["fertilizer_sp36_kg_str"] = fmt_kg(qty_sp36)
        crop_rec["fertilizer_kcl_kg_str"] = fmt_kg(qty_kcl)

    diff = cost_npk - cost_single

    if diff > 0:
        savings_pct = (diff / cost_npk) * 100 if cost_npk > 0 else 0
        diff_str = fmt_rp(diff)
        rec_text = f"Meracik campuran pupuk tunggal secara mandiri menghemat pengeluaran biaya Anda sebesar {savings_pct:.1f}% (Hemat {diff_str}) untuk lahan seluas {req.land_area_ha} ha."
    else:
        savings_pct = (abs(diff) / cost_single) * 100 if cost_single > 0 else 0
        diff_str = fmt_rp(abs(diff))
        rec_text = f"Penggunaan kombinasi formula pupuk majemuk NPK Phonska bersubsidi jauh lebih ekonomis sekitar {savings_pct:.1f}% (Hemat {diff_str}) di pasaran."

    analysis_summary = f"Berdasarkan analisis Fuzzy Logic & Forward Chaining lokal, lahan dengan jenis tanah {req.soil_type} di elevasi {req.elevation_mdpl} mdpl paling direkomendasikan untuk menanam {recommendations[0]['name']}. Dari segi pembiayaan, skema {('pupuk tunggal' if diff > 0 else 'pupuk majemuk')} memberikan efisiensi tertinggi."

    return {
        "recommended_crops": recommendations,
        "ai_mode": "local",
        "reasoning_chain": reasoning_chain,
        "analysis_summary": analysis_summary,
        "fertilization_plan": {
            "vegetative_phase": {"N": "90 kg/ha", "P": "45 kg/ha", "K": "30 kg/ha"},
            "generative_phase": {"N": "45 kg/ha", "P": "20 kg/ha", "K": "60 kg/ha"},
            "cost_comparison": {
                "npk_compound": {
                    "total_cost": round(cost_npk, 2),
                    "label": "NPK Majemuk",
                    "total_cost_str": fmt_rp(cost_npk),
                    "pct": (cost_npk / max(cost_npk, cost_single, 1.0)) * 100
                },
                "single_fertilizer_mix": {
                    "total_cost": round(cost_single, 2),
                    "label": "Campuran Urea + SP-36 + KCl",
                    "total_cost_str": fmt_rp(cost_single),
                    "pct": (cost_single / max(cost_npk, cost_single, 1.0)) * 100
                },
                "recommendation": rec_text,
                "savings_str": fmt_rp(abs(cost_npk - cost_single)),
                "savings_pct": (abs(cost_npk - cost_single) / max(cost_npk, cost_single, 1)) * 100,
                "is_single_cheaper": cost_single < cost_npk
            }
        }
    }