"""
Schémas Pydantic pour les sessions de cotisation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

from app.models.session import SessionStatus


class SessionBase(BaseModel):
    """Schéma de base pour une session."""
    scheduled_date: datetime = Field(..., description="Date prévue de la session")
    due_date: datetime = Field(..., description="Date limite de paiement")
    notes: Optional[str] = Field(None, max_length=1000)
    
    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: datetime, info) -> datetime:
        if "scheduled_date" in info.data and v < info.data["scheduled_date"]:
            raise ValueError("La date limite doit être >= la date prévue")
        return v


class SessionCreate(SessionBase):
    """Schéma pour créer une session."""
    tontine_id: int = Field(..., description="ID de la tontine")
    beneficiary_id: Optional[int] = Field(None, description="ID du bénéficiaire")


class SessionUpdate(BaseModel):
    """Schéma pour mettre à jour une session."""
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: Optional[SessionStatus] = None
    beneficiary_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=1000)


class SessionResponse(BaseModel):
    """Schéma de réponse pour une session."""
    id: int
    tontine_id: int
    session_number: int
    scheduled_date: datetime
    due_date: datetime
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    status: SessionStatus
    expected_amount: Decimal
    collected_amount: Decimal
    beneficiary_id: Optional[int]
    notes: Optional[str]
    is_complete: bool
    collection_percentage: float
    remaining_amount: float
    is_overdue: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Informations du bénéficiaire
    beneficiary_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Schéma pour la liste des sessions."""
    items: List[SessionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SessionStats(BaseModel):
    """Statistiques d'une session."""
    session_id: int
    total_expected_payments: int
    total_received_payments: int
    missing_payments: int
    total_amount_expected: Decimal
    total_amount_collected: Decimal
    collection_rate: float
    late_payments: int
    penalties_collected: Decimal
    
    # Liste des membres qui n'ont pas encore payé
    pending_members: List[dict] = []


class SessionPaymentSummary(BaseModel):
    """Résumé des paiements d'une session."""
    paid_members: List[dict]
    pending_members: List[dict]
    late_members: List[dict]
    total_paid: Decimal
    total_pending: Decimal
    total_penalties: Decimal


class OpenSessionRequest(BaseModel):
    """Requête pour ouvrir une session."""
    send_notifications: bool = Field(default=True, description="Envoyer les notifications")


class CloseSessionRequest(BaseModel):
    """Requête pour fermer une session."""
    force: bool = Field(default=False, description="Forcer la fermeture même si incomplète")
    notes: Optional[str] = None

