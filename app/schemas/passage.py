"""
Schémas Pydantic pour les passages/tours.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

from app.models.passage import PassageStatus


class PassageBase(BaseModel):
    """Schéma de base pour un passage."""
    scheduled_date: datetime = Field(..., description="Date prévue du passage")
    notes: Optional[str] = Field(None, max_length=500)


class PassageCreate(PassageBase):
    """Schéma pour créer un passage."""
    tontine_id: int = Field(..., description="ID de la tontine")
    member_id: int = Field(..., description="ID du membre bénéficiaire")
    order_number: int = Field(..., ge=1, description="Numéro d'ordre")
    expected_amount: Decimal = Field(..., ge=0, description="Montant attendu")


class PassageUpdate(BaseModel):
    """Schéma pour mettre à jour un passage."""
    scheduled_date: Optional[datetime] = None
    status: Optional[PassageStatus] = None
    payout_method: Optional[str] = Field(None, max_length=50)
    payout_reference: Optional[str] = Field(None, max_length=100)
    payout_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=500)
    postpone_reason: Optional[str] = Field(None, max_length=500)


class PassageResponse(BaseModel):
    """Schéma de réponse pour un passage."""
    id: int
    tontine_id: int
    member_id: int
    session_id: Optional[int]
    order_number: int
    scheduled_date: datetime
    actual_date: Optional[datetime]
    status: PassageStatus
    expected_amount: Decimal
    amount_received: Decimal
    payout_method: Optional[str]
    payout_reference: Optional[str]
    payout_phone: Optional[str]
    confirmed_by_member: bool
    confirmed_at: Optional[datetime]
    notes: Optional[str]
    postpone_reason: Optional[str]
    is_pending: bool
    is_complete: bool
    amount_difference: float
    is_overdue: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Informations du membre
    member_name: Optional[str] = None
    member_phone: Optional[str] = None
    member_email: Optional[str] = None
    
    class Config:
        from_attributes = True


class PassageListResponse(BaseModel):
    """Schéma pour la liste des passages."""
    items: List[PassageResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PassageOrderUpdate(BaseModel):
    """Schéma pour mettre à jour l'ordre des passages."""
    passages: List[dict] = Field(
        ..., 
        description="Liste des {member_id, order_number}"
    )
    
    @field_validator("passages")
    @classmethod
    def validate_passages(cls, v: List[dict]) -> List[dict]:
        """Valide la liste des passages."""
        if not v:
            raise ValueError("La liste des passages ne peut pas être vide")
        
        # Vérifier que chaque élément a les champs requis
        for passage in v:
            if "member_id" not in passage or "order_number" not in passage:
                raise ValueError("Chaque passage doit avoir member_id et order_number")
        
        # Vérifier l'unicité des ordres
        orders = [p["order_number"] for p in v]
        if len(orders) != len(set(orders)):
            raise ValueError("Les numéros d'ordre doivent être uniques")
        
        return v


class GeneratePassageOrder(BaseModel):
    """Schéma pour générer l'ordre de passage."""
    method: str = Field(
        default="random",
        description="Méthode: random, alphabetical, join_date"
    )
    
    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        valid_methods = ["random", "alphabetical", "join_date"]
        if v not in valid_methods:
            raise ValueError(f"Méthode invalide. Valeurs acceptées: {valid_methods}")
        return v


class PassageConfirmation(BaseModel):
    """Schéma pour confirmer la réception du pot."""
    amount_received: Decimal = Field(..., ge=0, description="Montant réellement reçu")
    notes: Optional[str] = Field(None, max_length=500)


class PassagePayout(BaseModel):
    """Schéma pour effectuer le versement du pot."""
    payout_method: str = Field(
        ..., 
        description="Méthode: especes, orange_money, wave, mtn_momo, virement"
    )
    payout_phone: Optional[str] = Field(
        None, 
        description="Numéro pour mobile money"
    )
    payout_reference: Optional[str] = Field(
        None, 
        max_length=100,
        description="Référence du versement"
    )
    amount: Decimal = Field(..., gt=0, description="Montant à verser")
    
    @field_validator("payout_method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        valid = ["especes", "orange_money", "wave", "mtn_momo", "free_money", "moov_money", "virement"]
        if v not in valid:
            raise ValueError(f"Méthode invalide. Valeurs: {valid}")
        return v


class PassageSchedule(BaseModel):
    """Planning des passages d'une tontine."""
    tontine_id: int
    tontine_name: str
    passages: List[PassageResponse]
    current_passage: Optional[PassageResponse]
    next_passage: Optional[PassageResponse]
    completed_count: int
    remaining_count: int

