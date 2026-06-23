import os
import json
import logging
import mimetypes
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException, Form, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Paksa registrasi MIME type CSS untuk mencegah pemblokiran stylesheet di WSL/Windows
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')

# Load environmental variables
load_dotenv()

from app.database import engine, Base, get_db, SessionLocal
from app.models import (
    RecommendationRequest, 
    RecommendationResponse, 
    Crop, 
    Fertilizer,
    AnalysisHistory
)
from app.core.ai_agent import get_recommendation

# Setup Logging Standard Industri
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgroAI")


# ==========================================
# Database Seeding Helper
# ==========================================
def seed_database(db: Session):
    """
    Seeds default crop and fertilizer data into the database if empty.
    """
    if db.query(Crop).count() == 0:
        crops_seed = [
            Crop(
                name="Padi IR64", soil_type="Aluvial", elevation_min=0, elevation_max=600, estimated_price_per_kg=5200.0,
                seed_cost_per_ha=375000.0, yield_per_ha=6000.0,
                base_reasoning="Padi IR64 sangat ideal ditanam pada tanah aluvial di dataran rendah."
            ),
            Crop(
                name="Jagung Hibrida Bisi 2", soil_type="Andosol", elevation_min=0, elevation_max=1000, estimated_price_per_kg=4500.0,
                seed_cost_per_ha=1200000.0, yield_per_ha=8000.0,
                base_reasoning="Jagung hibrida tumbuh optimal di tanah andosol yang subur dan gembur."
            ),
            Crop(
                name="Kentang Granola", soil_type="Andosol", elevation_min=1000, elevation_max=3000, estimated_price_per_kg=12000.0,
                seed_cost_per_ha=37500000.0, yield_per_ha=20000.0,
                base_reasoning="Kentang Granola membutuhkan suhu dingin dataran tinggi dan tanah andosol vulkanik."
            ),
            Crop(
                name="Bawang Merah Bima", soil_type="Liat", elevation_min=0, elevation_max=250, estimated_price_per_kg=28000.0,
                seed_cost_per_ha=35000000.0, yield_per_ha=10000.0,
                base_reasoning="Bawang merah membutuhkan tanah berstruktur lempung liat dengan drainase baik."
            ),
            Crop(
                name="Semangka Tanpa Biji", soil_type="Pasir", elevation_min=0, elevation_max=300, estimated_price_per_kg=8000.0,
                seed_cost_per_ha=2500000.0, yield_per_ha=20000.0,
                base_reasoning="Semangka tumbuh sangat baik di tanah berpasir dengan drainase yang lancar dan intensitas cahaya matahari penuh."
            ),
            Crop(
                name="Cabai Rawit", soil_type="Aluvial", elevation_min=0, elevation_max=1500, estimated_price_per_kg=35000.0,
                seed_cost_per_ha=2000000.0, yield_per_ha=8000.0,
                base_reasoning="Cabai rawit cocok ditanam di tanah aluvial gembur dengan ketersediaan air cukup."
            ),
            Crop(
                name="Tomat", soil_type="Andosol", elevation_min=500, elevation_max=1500, estimated_price_per_kg=12000.0,
                seed_cost_per_ha=1500000.0, yield_per_ha=15000.0,
                base_reasoning="Tomat tumbuh sangat baik di tanah andosol vulkanik di dataran sedang hingga tinggi."
            ),
            Crop(
                name="Singkong Mukibat", soil_type="Liat", elevation_min=0, elevation_max=800, estimated_price_per_kg=2000.0,
                seed_cost_per_ha=500000.0, yield_per_ha=30000.0,
                base_reasoning="Singkong mukibat sangat adaptif pada kondisi tanah liat gembur dengan sinar matahari penuh."
            ),
            Crop(
                name="Kedelai Wilis", soil_type="Aluvial", elevation_min=0, elevation_max=500, estimated_price_per_kg=10000.0,
                seed_cost_per_ha=800000.0, yield_per_ha=2000.0,
                base_reasoning="Kedelai cocok ditanam di tanah aluvial berdrainase baik sebagai tanaman rotasi setelah padi."
            )
        ]
        db.add_all(crops_seed)
        db.commit()
        logger.info("Successfully seeded Crops database.")

    if db.query(Fertilizer).count() == 0:
        fertilizers_seed = [
            Fertilizer(name="Urea", fertilizer_type="Single", n_content=46.0, p_content=0.0, k_content=0.0, price_per_kg=1800.0),
            Fertilizer(name="SP-36", fertilizer_type="Single", n_content=0.0, p_content=36.0, k_content=0.0, price_per_kg=2000.0),
            Fertilizer(name="KCl", fertilizer_type="Single", n_content=0.0, p_content=0.0, k_content=60.0, price_per_kg=9500.0),
            Fertilizer(name="NPK Phonska 15-15-15", fertilizer_type="Compound", n_content=15.0, p_content=15.0, k_content=15.0, price_per_kg=2300.0),
            Fertilizer(name="ZA", fertilizer_type="Single", n_content=21.0, p_content=0.0, k_content=0.0, price_per_kg=1400.0),
            Fertilizer(name="Organik", fertilizer_type="Organic", n_content=0.0, p_content=0.0, k_content=0.0, price_per_kg=500.0),
        ]
        db.add_all(fertilizers_seed)
        db.commit()
        logger.info("Successfully seeded Fertilizers database.")


# ==========================================
# Lifespan Manager (Fixed Context Loop)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Mengatur proses startup dan shutdown aplikasi secara aman.
    """
    logger.info("Initializing database and seeding data...")
    # Buat skema database jika belum ada
    Base.metadata.create_all(bind=engine)
    
    # Eksekusi Database Seeding
    with SessionLocal() as db:
        try:
            seed_database(db)
        except Exception as e:
            db.rollback()
            logger.error(f"Error seeding database in lifespan: {e}")
            
    # Yield tunggal menyerahkan kendali operasi ke FastAPI instans
    yield
    
    # Kode di bawah ini berjalan saat proses shutdown aplikasi dipicu
    logger.info("Shutting down AgroAI Application...")


# ==========================================
# Inisialisasi Aplikasi Utama
# ==========================================
app = FastAPI(
    title="AgroAI API",
    description="Intelligent Seed & Fertilizer Recommendation System",
    version="1.0.0",
    lifespan=lifespan
)

# Konfigurasi Jalur Pintar (Mencegah kegagalan pencarian direktori aset statis)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Cek apakah statis/templates ada di dalam modul 'app/' atau di root direktori
TEMPLATE_DIR = os.path.join(CURRENT_DIR, "templates")
if not os.path.exists(TEMPLATE_DIR):
    TEMPLATE_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "templates")

STATIC_DIR = os.path.join(CURRENT_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "static")

# Mount Static Files & Templates secara aman
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Global State for XAI Demo
LATEST_XAI_DATA = None


# ==========================================
# 🌐 ROUTER 1: Web UI (Monolith Blueprint)
# ==========================================
ui_router = APIRouter(tags=["Web User Interface"])

@ui_router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request, 
        "dashboard.html", 
        {
            "result": None,
            "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY", "")
        }
    )

@ui_router.get("/history", response_class=HTMLResponse)
async def read_history(request: Request):
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY", "")
        }
    )

@ui_router.get("/xai", response_class=HTMLResponse)
async def read_xai(request: Request):
    return templates.TemplateResponse(
        request,
        "xai.html",
        {
            "xai_data": LATEST_XAI_DATA
        }
    )

@ui_router.post("/", response_class=HTMLResponse)
async def handle_form_recommendation(
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    land_area_ha: float = Form(...),
    force_local: bool = Form(False),
    db: Session = Depends(get_db)
):
    try:
        req_data = RecommendationRequest(
            latitude=latitude,
            longitude=longitude,
            land_area_ha=land_area_ha,
            force_local=force_local
        )
        
        # Panggil core AI Agent
        recommendations = await get_recommendation(req_data, db)
        
        # Save XAI data globally
        if recommendations.get("xai_logs") or recommendations.get("xai_structured"):
            global LATEST_XAI_DATA
            LATEST_XAI_DATA = {
                "logs": recommendations.get("xai_logs", []),
                "structured": recommendations.get("xai_structured", {})
            }
        
        return templates.TemplateResponse(
            request,
            "dashboard.html", 
            {
                "result": recommendations,
                "ai_mode": recommendations.get("ai_mode", "local"),
                "reasoning_chain": recommendations.get("reasoning_chain", []),
                "analysis_summary": recommendations.get("analysis_summary", ""),
                "recommended_crops": recommendations.get("recommended_crops", []),
                "fertilization_plan": recommendations.get("fertilization_plan"),
                "xai_logs": recommendations.get("xai_logs", []),
                "input_values": req_data,
                "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY", "")
            }
        )
    except Exception as e:
        logger.error(f"UI Recommendation Error: {str(e)}")
        return templates.TemplateResponse(
            request,
            "dashboard.html", 
            {
                "error_message": f"Gagal memproses rekomendasi: {str(e)}",
                "result": None,
                "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY", "")
            }
        )


# ==========================================
# 🤖 ROUTER 2: REST API (Mobile/B2B Integrations)
# ==========================================
api_router = APIRouter(prefix="/api/v1", tags=["REST API Endpoints"])

@api_router.post("/recommend", response_model=RecommendationResponse)
async def get_agro_recommendation_api(req: RecommendationRequest, db: Session = Depends(get_db)):
    try:
        recommendations = await get_recommendation(req, db)
        return recommendations
    except Exception as e:
        logger.error(f"API Recommendation Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error occurred.")


# Registrasi Semua Router ke Aplikasi Utama
app.include_router(ui_router)
app.include_router(api_router)