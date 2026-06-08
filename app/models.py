from sqlalchemy import Column, Integer, String, Float
from pydantic import BaseModel
from typing import List, Dict
from app.database import Base

# ==========================================
# SQLAlchemy Models
# ==========================================

class Crop(Base):
    __tablename__ = "crops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    soil_type = Column(String, nullable=False)  # e.g., "Aluvial", "Andosol", "Pasir", "Liat"
    elevation_min = Column(Integer, default=0)    # mdpl min
    elevation_max = Column(Integer, default=5000) # mdpl max
    estimated_price_per_kg = Column(Float, nullable=False)
    base_reasoning = Column(String, nullable=False)


class Fertilizer(Base):
    __tablename__ = "fertilizers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)         # e.g., "Urea", "SP-36", "KCl", "NPK Phonska"
    fertilizer_type = Column(String, nullable=False) # "Single" or "Compound"
    n_content = Column(Float, default=0.0)        # Percentage of N content (0-100)
    p_content = Column(Float, default=0.0)        # Percentage of P2O5 content (0-100)
    k_content = Column(Float, default=0.0)        # Percentage of K2O content (0-100)
    price_per_kg = Column(Float, nullable=False)


# ==========================================
# Pydantic Schemas (Request/Response)
# ==========================================

class RecommendationRequest(BaseModel):
    soil_type: str
    elevation_mdpl: int
    land_area_ha: float
    location: str

    class Config:
        json_schema_extra = {
            "example": {
                "soil_type": "Aluvial",
                "elevation_mdpl": 150,
                "land_area_ha": 2.5,
                "location": "Jawa Tengah"
            }
        }


class CropRecommendation(BaseModel):
    name: str
    suitability_score: float
    estimated_price_per_kg: float
    reasoning: str


class NutrientPhase(BaseModel):
    N: str
    P: str
    K: str


class CostDetail(BaseModel):
    total_cost: float
    label: str


class CostComparison(BaseModel):
    npk_compound: CostDetail
    single_fertilizer_mix: CostDetail
    recommendation: str


class FertilizationPlan(BaseModel):
    vegetative_phase: NutrientPhase
    generative_phase: NutrientPhase
    cost_comparison: CostComparison


class RecommendationResponse(BaseModel):
    recommended_crops: List[CropRecommendation]
    fertilization_plan: FertilizationPlan
