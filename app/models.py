from sqlalchemy import Column, Integer, String, Float
from pydantic import BaseModel
from typing import List, Dict, Optional
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
    seed_cost_per_ha = Column(Float, default=0.0)
    yield_per_ha = Column(Float, default=0.0)


class Fertilizer(Base):
    __tablename__ = "fertilizers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)         # e.g., "Urea", "SP-36", "KCl", "NPK Phonska"
    fertilizer_type = Column(String, nullable=False) # "Single" or "Compound"
    n_content = Column(Float, default=0.0)        # Percentage of N content (0-100)
    p_content = Column(Float, default=0.0)        # Percentage of P2O5 content (0-100)
    k_content = Column(Float, default=0.0)        # Percentage of K2O content (0-100)
    price_per_kg = Column(Float, nullable=False)


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    land_area_ha = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    soil_type = Column(String, nullable=False)
    elevation_mdpl = Column(Integer, nullable=False)
    best_crop = Column(String, nullable=False)
    result_json = Column(String, nullable=False)


# ==========================================
# Pydantic Schemas (Request/Response)
# ==========================================

class RecommendationRequest(BaseModel):
    latitude: float
    longitude: float
    land_area_ha: float
    soil_type: Optional[str] = None
    elevation_mdpl: Optional[int] = None
    location: Optional[str] = None
    force_local: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": -7.3,
                "longitude": 110.1,
                "land_area_ha": 2.5,
                "soil_type": "Aluvial",
                "elevation_mdpl": 150,
                "location": "Jawa Tengah"
            }
        }


class CropRecommendation(BaseModel):
    name: str
    suitability_score: float
    estimated_price_per_kg: float
    reasoning: str
    yield_per_ha: float = 0.0
    seed_cost_per_ha: float = 0.0
    harvest_revenue: float = 0.0
    fertilizer_cost_npk: float = 0.0
    fertilizer_cost_single: float = 0.0
    profit_npk: float = 0.0
    profit_single: float = 0.0

    # Kuantitas pupuk dalam kg
    fertilizer_qty_npk: float = 0.0
    fertilizer_qty_single: float = 0.0
    fertilizer_urea_kg: float = 0.0
    fertilizer_sp36_kg: float = 0.0
    fertilizer_kcl_kg: float = 0.0

    # Representasi string harga dan kuantitas untuk UI terformat Rupiah & kg
    estimated_price_per_kg_str: str = ""
    seed_cost_per_ha_str: str = ""
    seed_cost_total_str: str = ""
    harvest_revenue_str: str = ""
    fertilizer_cost_npk_str: str = ""
    fertilizer_cost_single_str: str = ""
    profit_npk_str: str = ""
    profit_single_str: str = ""
    fertilizer_qty_npk_str: str = ""
    fertilizer_qty_single_str: str = ""
    fertilizer_urea_kg_str: str = ""
    fertilizer_sp36_kg_str: str = ""
    fertilizer_kcl_kg_str: str = ""


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


class ReasoningStep(BaseModel):
    step: int
    icon: str
    title: str
    description: str


class RecommendationResponse(BaseModel):
    recommended_crops: List[CropRecommendation]
    fertilization_plan: FertilizationPlan
    ai_mode: str = "local"
    reasoning_chain: List[ReasoningStep] = []
    analysis_summary: str = ""
