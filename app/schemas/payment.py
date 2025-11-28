"""
Schémas Pydantic pour les paiements.
Supporte les paiements manuels et via mobile money.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
import re

from app.models.payment import PaymentStatus, PaymentMethod


class PaymentBase(BaseModel):
    """Schéma de base pour un paiement."""
    amount: Decimal = Field(..., gt=0, description="Montant du paiement")
    method: PaymentMethod = Field(..., description="Méthode de paiement")
    notes: Optional[str] = Field(None, max_length=500)


class PaymentCreate(PaymentBase):
    """Schéma pour créer un paiement (manuel ou initier mobile money)."""
    tontine_id: int = Field(..., description="ID de la tontine")
    session_id: Optional[int] = Field(None, description="ID de la session (optionnel, utilise la session en cours si non fourni)")
    transaction_id: Optional[str] = Field(None, max_length=100, description="ID de transaction mobile money")
    phone_number: Optional[str] = Field(
        None, 
        description="Numéro pour mobile money"
    )
    proof_url: Optional[str] = Field(
        None, 
        max_length=500, 
        description="URL de la preuve (paiement espèces)"
    )
    proof_description: Optional[str] = Field(None, max_length=500)
    is_manual: bool = Field(default=True, description="Paiement déclaré manuellement")
    
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str], info) -> Optional[str]:
        if v is None:
            return v
        cleaned = re.sub(r"[\s\-]", "", v)
        if not re.match(r"^\+?[0-9]{8,15}$", cleaned):
            raise ValueError("Format de téléphone invalide")
        return cleaned


class PaymentUpdate(BaseModel):
    """Schéma pour mettre à jour un paiement."""
    status: Optional[PaymentStatus] = None
    notes: Optional[str] = Field(None, max_length=500)
    proof_url: Optional[str] = None
    proof_description: Optional[str] = None


class PaymentResponse(BaseModel):
    """Schéma de réponse pour un paiement."""
    id: int
    user_id: int
    session_id: int
    tontine_id: int
    amount: Decimal
    currency: str
    method: PaymentMethod
    status: PaymentStatus
    operator_reference: Optional[str]
    operator_transaction_id: Optional[str]
    phone_number: Optional[str]
    proof_url: Optional[str]
    proof_description: Optional[str]
    validated_by_id: Optional[int]
    validated_at: Optional[datetime]
    rejection_reason: Optional[str]
    penalty_amount: Decimal
    is_late: bool
    total_amount: float
    is_mobile_money: bool
    is_manual: bool
    requires_validation: bool
    notes: Optional[str]
    initiated_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime
    
    # Informations utilisateur
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    
    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """Schéma pour la liste des paiements."""
    items: List[PaymentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PaymentValidation(BaseModel):
    """Schéma pour valider/rejeter un paiement manuel."""
    action: str = Field(..., description="approve ou reject")
    rejection_reason: Optional[str] = Field(
        None, 
        max_length=500, 
        description="Raison du rejet (obligatoire si reject)"
    )
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ["approve", "reject"]:
            raise ValueError("action doit être 'approve' ou 'reject'")
        return v
    
    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("action") == "reject" and not v:
            raise ValueError("La raison du rejet est obligatoire")
        return v


class PaymentInitiate(BaseModel):
    """Schéma pour initier un paiement mobile money."""
    session_id: int = Field(..., description="ID de la session")
    method: PaymentMethod = Field(..., description="Opérateur mobile money")
    phone_number: str = Field(..., description="Numéro de téléphone")
    
    @field_validator("method")
    @classmethod
    def validate_method(cls, v: PaymentMethod) -> PaymentMethod:
        mobile_methods = [
            PaymentMethod.ORANGE_MONEY,
            PaymentMethod.MTN_MOMO,
            PaymentMethod.WAVE,
            PaymentMethod.FREE_MONEY,
            PaymentMethod.MOOV_MONEY,
        ]
        if v not in mobile_methods:
            raise ValueError("Méthode de paiement mobile money invalide")
        return v
    
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-]", "", v)
        if not re.match(r"^\+?[0-9]{8,15}$", cleaned):
            raise ValueError("Format de téléphone invalide")
        return cleaned


class PaymentCallback(BaseModel):
    """
    Schéma pour recevoir les callbacks des opérateurs mobile money.
    Ce schéma est générique et peut être adapté selon l'opérateur.
    """
    operator: str = Field(..., description="Nom de l'opérateur")
    reference: str = Field(..., description="Référence de la transaction")
    transaction_id: Optional[str] = Field(None, description="ID transaction opérateur")
    status: str = Field(..., description="Statut de la transaction")
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    phone_number: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Données brutes du callback"
    )


class OrangeMoneyCallback(BaseModel):
    """Callback spécifique Orange Money."""
    status: str
    notif_token: str
    txnid: str
    txnmode: Optional[str] = None
    txnstatus: str
    message: Optional[str] = None
    call_back_url: Optional[str] = None
    amount: str
    order_id: str
    payment_date: Optional[str] = None


class MTNMoMoCallback(BaseModel):
    """Callback spécifique MTN Mobile Money."""
    financialTransactionId: str
    externalId: str
    amount: str
    currency: str
    payer: Optional[Dict[str, str]] = None
    payerMessage: Optional[str] = None
    payeeNote: Optional[str] = None
    status: str


class WaveCallback(BaseModel):
    """Callback spécifique Wave."""
    id: str
    amount: str
    currency: str
    checkout_status: str
    client_reference: str
    sender_mobile: Optional[str] = None
    sender_name: Optional[str] = None
    when_completed: Optional[str] = None
    when_created: Optional[str] = None


class PaymentStats(BaseModel):
    """Statistiques de paiement pour un utilisateur."""
    total_payments: int
    total_amount_paid: Decimal
    successful_payments: int
    failed_payments: int
    pending_payments: int
    late_payments: int
    total_penalties: Decimal
    favorite_payment_method: Optional[str]
    last_payment_date: Optional[datetime]

