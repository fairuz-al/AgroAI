import os
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load environmental variables from .env
load_dotenv()

from app.database import engine, Base, get_db
from app.models import (
    RecommendationRequest, 
    RecommendationResponse, 
    Crop, 
    Fertilizer
)
from app.core.ai_agent import get_recommendation

# Initialize FastAPI App
app = FastAPI(
    title="AgroAI API",
    description="Intelligent Seed & Fertilizer Recommendation System",
    version="1.0.0"
)

# Ensure static & templates directory exists
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)

# Mount Static Files & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Database Startup Seeding
@app.on_event("startup")
def startup_event():
    # 1. Create database tables
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed default data if empty
    db = next(get_db())
    try:
        if db.query(Crop).count() == 0:
            crops_seed = [
                Crop(
                    name="Padi IR64",
                    soil_type="Aluvial",
                    elevation_min=0,
                    elevation_max=600,
                    estimated_price_per_kg=5200.0,
                    base_reasoning="Padi IR64 sangat ideal ditanam pada tanah aluvial di dataran rendah."
                ),
                Crop(
                    name="Jagung Hibrida Bisi 2",
                    soil_type="Andosol",
                    elevation_min=0,
                    elevation_max=1000,
                    estimated_price_per_kg=4500.0,
                    base_reasoning="Jagung hibrida tumbuh optimal di tanah andosol yang subur dan gembur."
                ),
                Crop(
                    name="Kentang Granola",
                    soil_type="Andosol",
                    elevation_min=1000,
                    elevation_max=3000,
                    estimated_price_per_kg=12000.0,
                    base_reasoning="Kentang Granola membutuhkan suhu dingin dataran tinggi dan tanah andosol vulkanik."
                ),
                Crop(
                    name="Bawang Merah Bima",
                    soil_type="Liat",
                    elevation_min=0,
                    elevation_max=250,
                    estimated_price_per_kg=28000.0,
                    base_reasoning="Bawang merah membutuhkan tanah berstruktur lempung liat dengan drainase baik."
                ),
                Crop(
                    name="Semangka Tanpa Biji",
                    soil_type="Pasir",
                    elevation_min=0,
                    elevation_max=300,
                    estimated_price_per_kg=8000.0,
                    base_reasoning="Semangka tumbuh sangat baik di tanah berpasir dengan drainase yang lancar dan intensitas cahaya matahari penuh."
                )
            ]
            db.add_all(crops_seed)
            db.commit()
            print("Successfully seeded Crops database.")

        if db.query(Fertilizer).count() == 0:
            fertilizers_seed = [
                Fertilizer(name="Urea", fertilizer_type="Single", n_content=46.0, p_content=0.0, k_content=0.0, price_per_kg=4500.0),
                Fertilizer(name="SP-36", fertilizer_type="Single", n_content=0.0, p_content=36.0, k_content=0.0, price_per_kg=5200.0),
                Fertilizer(name="KCl", fertilizer_type="Single", n_content=0.0, p_content=0.0, k_content=60.0, price_per_kg=8500.0),
                Fertilizer(name="NPK Phonska 15-15-15", fertilizer_type="Compound", n_content=15.0, p_content=15.0, k_content=15.0, price_per_kg=10000.0)
            ]
            db.add_all(fertilizers_seed)
            db.commit()
            print("Successfully seeded Fertilizers database.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()


# ==========================================
# Routes & Endpoints
# ==========================================

@app.get("/")
def read_root(request: Request):
    """
    Renders the beautiful AgroAI dashboard page.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.post("/api/v1/recommend", response_model=RecommendationResponse)
def get_agro_recommendation(req: RecommendationRequest, db: Session = Depends(get_db)):
    """
    API endpoint for getting crop and fertilizer recommendations.
    """
    try:
        recommendations = get_recommendation(req, db)
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
