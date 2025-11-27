"""
Schémas Pydantic pour les tontines et membres.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

from app.models.tontine import TontineType, TontineFrequency


class TontineBase(BaseModel):
    """Schéma de base pour une tontine."""
    name: str = Field(..., min_length=3, max_length=200, description="Nom de la tontine")
    description: Optional[str] = Field(None, max_length=1000)
    type: TontineType = Field(default=TontineType.ROTATIVE)
    frequency: TontineFrequency = Field(default=TontineFrequency.MENSUEL)
    contribution_amount: Decimal = Field(..., gt=0, description="Montant de la cotisation")
    currency: str = Field(default="FCFA", max_length=10)


class TontineCreate(TontineBase):
    """Schéma pour la création d'une tontine."""
    max_members: int = Field(default=12, ge=3, le=100)
    min_members: int = Field(default=3, ge=2, le=50)
    start_date: datetime = Field(..., description="Date de début")
    end_date: Optional[datetime] = None
    rules: Optional[str] = Field(None, max_length=5000)
    penalty_amount: Decimal = Field(default=Decimal("0"), ge=0)
    grace_period_days: int = Field(default=3, ge=0, le=30)
    is_public: bool = Field(default=False)
    
    @field_validator("max_members")
    @classmethod
    def validate_max_members(cls, v: int, info) -> int:
        if "min_members" in info.data and v < info.data["min_members"]:
            raise ValueError("max_members doit être >= min_members")
        return v
    
    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v and "start_date" in info.data:
            if v <= info.data["start_date"]:
                raise ValueError("La date de fin doit être après la date de début")
        return v


class TontineUpdate(BaseModel):
    """Schéma pour la mise à jour d'une tontine."""
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    rules: Optional[str] = Field(None, max_length=5000)
    penalty_amount: Optional[Decimal] = Field(None, ge=0)
    grace_period_days: Optional[int] = Field(None, ge=0, le=30)
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class TontineResponse(BaseModel):
    """Schéma de réponse pour une tontine."""
    id: int
    name: str
    description: Optional[str]
    code: str
    type: TontineType
    frequency: TontineFrequency
    contribution_amount: Decimal
    currency: str
    max_members: int
    min_members: int
    start_date: datetime
    end_date: Optional[datetime]
    rules: Optional[str]
    penalty_amount: Decimal
    grace_period_days: int
    is_active: bool
    is_public: bool
    created_by_id: int
    member_count: int
    is_full: bool
    total_pot: float
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TontineListResponse(BaseModel):
    """Schéma pour la liste des tontines."""
    items: List[TontineResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TontineMemberBase(BaseModel):
    """Schéma de base pour un membre de tontine."""
    user_id: int = Field(..., description="ID de l'utilisateur")
    role: str = Field(default="membre", description="Rôle dans la tontine")


class TontineMemberCreate(TontineMemberBase):
    """Schéma pour ajouter un membre."""
    tontine_id: Optional[int] = None  # Peut être fourni dans l'URL
    order_position: Optional[int] = Field(None, ge=1)


class TontineMemberUpdate(BaseModel):
    """Schéma pour modifier un membre."""
    role: Optional[str] = None
    order_position: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class TontineMemberResponse(BaseModel):
    """Schéma de réponse pour un membre."""
    id: int
    user_id: int
    tontine_id: int
    role: str
    order_position: Optional[int]
    is_active: bool
    joined_at: datetime
    left_at: Optional[datetime]
    total_contributions: Decimal
    total_received: Decimal
    missed_payments: int
    
    # Informations utilisateur incluses
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    
    class Config:
        from_attributes = True


class TontineStats(BaseModel):
    """Statistiques d'une tontine."""
    total_members: int
    active_members: int
    total_sessions: int
    completed_sessions: int
    total_collected: Decimal
    total_distributed: Decimal
    average_contribution_rate: float  # Pourcentage
    next_session_date: Optional[datetime]
    next_beneficiary_name: Optional[str]


class JoinTontineRequest(BaseModel):
    """Schéma pour rejoindre une tontine via code."""
    code: str = Field(..., min_length=4, max_length=10, description="Code de la tontine")

