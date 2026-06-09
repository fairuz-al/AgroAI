import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException, Form, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

from app.database import engine, Base, get_db, SessionLocal
from app.models import (
    RecommendationRequest, 
    RecommendationResponse, 
    Crop, 
    Fertilizer
)
from app.core.ai_agent import get_recommendation

# Setup Logging Standard Industri
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgroAI")

# ==========================================
# Lifespan Manager (Modern FastAPI Lifecycle)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Mengatur proses startup dan shutdown aplikasi secara aman.
    Menggantikan @app.on_event("startup") yang sudah deprecated.
    """
    logger.info("Initializing database and seeding data...")
    # 1. Automigrasi Skema Database
    Base.metadata.create_all(bind=engine)
    
    # 2. Database Seeding dengan Context Manager (Auto-Close Connection)
    with SessionLocal() as db:
        try:
            if db.query(Crop).count() == 0:
                crops_seed = [
                    Crop(name="Padi IR64", soil_type="Aluvial", elevation_min=0, elevation_max=600, estimated_price_per_kg=5200.0, base_reasoning="Padi IR64 sangat ideal ditanam pada tanah aluvial di dataran rendah."),
                    Crop(name="Jagung Hibrida Bisi 2", soil_type="Andosol", elevation_min=0, elevation_max=1000, estimated_price_per_kg=4500.0, base_reasoning="Jagung hibrida tumbuh optimal di tanah andosol yang subur dan gembur."),
                    Crop(name="Kentang Granola", soil_type="Andosol", elevation_min=1000, elevation_max=3000, estimated_price_per_kg=12000.0, base_reasoning="Kentang Granola membutuhkan suhu dingin dataran tinggi dan tanah andosol vulkanik."),
                    Crop(name="Bawang Merah Bima", soil_type="Liat", elevation_min=0, elevation_max=250, estimated_price_per_kg=28000.0, base_reasoning="Bawang merah membutuhkan tanah berstruktur lempung liat dengan drainase baik."),
                    Crop(name="Semangka Tanpa Biji", soil_type="Pasir", elevation_min=0, elevation_max=300, estimated_price_per_kg=8000.0, base_reasoning="Semangka tumbuh sangat baik di tanah berpasir dengan drainase yang lancar dan intensitas cahaya matahari penuh.")
                ]
                db.add_all(crops_seed)
                db.commit()
                logger.info("Successfully seeded Crops database.")

            if db.query(Fertilizer).count() == 0:
                # -------------------------------------------------------
                # Harga seed mengikuti HET Pupuk Bersubsidi
                # Permentan No. 47/SR.310/12/2017 Pasal 11 ayat (2)
                # -------------------------------------------------------
                fertilizers_seed = [
                    Fertilizer(
                        name="Urea",
                        fertilizer_type="Single",
                        n_content=46.0, p_content=0.0, k_content=0.0,
                        price_per_kg=1800.0          # HET: Rp 1.800/kg
                    ),
                    Fertilizer(
                        name="SP-36",
                        fertilizer_type="Single",
                        n_content=0.0, p_content=36.0, k_content=0.0,
                        price_per_kg=2000.0          # HET: Rp 2.000/kg
                    ),
                    Fertilizer(
                        name="KCl",
                        fertilizer_type="Single",
                        n_content=0.0, p_content=0.0, k_content=60.0,
                        price_per_kg=9500.0          # Non-subsidi, estimasi harga pasar
                    ),
                    Fertilizer(
                        name="NPK Phonska 15-15-15",
                        fertilizer_type="Compound",
                        n_content=15.0, p_content=15.0, k_content=15.0,
                        price_per_kg=2300.0          # HET: Rp 2.300/kg
                    ),
                    Fertilizer(
                        name="ZA",
                        fertilizer_type="Single",
                        n_content=21.0, p_content=0.0, k_content=0.0,
                        price_per_kg=1400.0          # HET: Rp 1.400/kg
                    ),
                    Fertilizer(
                        name="Organik",
                        fertilizer_type="Organic",
                        n_content=0.0, p_content=0.0, k_content=0.0,
                        price_per_kg=500.0           # HET: Rp 500/kg
                    ),
                ]
                db.add_all(fertilizers_seed)
                db.commit()
                logger.info("Successfully seeded Fertilizers database.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error seeding database: {e}")
            
    yield
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

# Konfigurasi Jalur Absolut
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(CURRENT_DIR, "templates")
STATIC_DIR = os.path.join(CURRENT_DIR, "static")

# Mount Static Files & Templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


# ==========================================
# 🌐 ROUTER 1: Web UI (Monolith Blueprint)
# ==========================================
ui_router = APIRouter(tags=["Web User Interface"])

@ui_router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"result": None})

@ui_router.post("/", response_class=HTMLResponse)
async def handle_form_recommendation(
    request: Request,
    soil_type: str = Form(...),
    elevation_mdpl: int = Form(...),
    land_area_ha: float = Form(...),
    location: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        req_data = RecommendationRequest(
            soil_type=soil_type,
            elevation_mdpl=elevation_mdpl,
            land_area_ha=land_area_ha,
            location=location
        )
        
        # Panggil core AI Agent
        recommendations = await get_recommendation(req_data, db)
        
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
                "input_values": req_data
            }
        )
    except Exception as e:
        logger.error(f"UI Recommendation Error: {str(e)}")
        return templates.TemplateResponse(
            request,
            "dashboard.html", 
            {
                "error_message": f"Gagal memproses rekomendasi: {str(e)}",
                "result": None
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