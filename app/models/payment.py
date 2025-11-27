"""
Modèle Payment - Gestion des paiements et cotisations.
Supporte les paiements manuels et automatisés via mobile money.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    Numeric, ForeignKey, Index, CheckConstraint, JSON,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.database import Base


class PaymentStatus(str, enum.Enum):
    """Statuts possibles d'un paiement."""
    EN_ATTENTE = "en_attente"       # Paiement initié, en attente de confirmation
    EN_COURS = "en_cours"           # Transaction en cours côté opérateur
    VALIDE = "valide"               # Paiement validé et confirmé
    ECHOUE = "echoue"               # Transaction échouée
    ANNULE = "annule"               # Paiement annulé
    REMBOURSE = "rembourse"         # Paiement remboursé


class PaymentMethod(str, enum.Enum):
    """Méthodes de paiement disponibles."""
    ESPECES = "especes"             # Paiement en espèces (manuel)
    ORANGE_MONEY = "orange_money"   # Orange Money
    MTN_MOMO = "mtn_momo"           # MTN Mobile Money
    WAVE = "wave"                   # Wave
    FREE_MONEY = "free_money"       # Free Money
    MOOV_MONEY = "moov_money"       # Moov Money
    BANK_TRANSFER = "bank_transfer" # Virement bancaire


class Payment(Base):
    """
    Modèle représentant un paiement/cotisation.
    
    Gère à la fois les paiements manuels (espèces) et les paiements
    automatisés via les opérateurs mobile money.
    
    Attributes:
        id: Identifiant unique
        user_id: ID de l'utilisateur qui paie
        session_id: ID de la session de cotisation
        tontine_id: ID de la tontine (redondant mais utile pour les requêtes)
        amount: Montant du paiement
        currency: Devise
        method: Méthode de paiement
        status: Statut du paiement
        operator_reference: Référence de l'opérateur mobile money
        operator_transaction_id: ID de transaction de l'opérateur
        phone_number: Numéro de téléphone utilisé pour le paiement
        proof_url: URL de la preuve de paiement (pour espèces)
        validated_by_id: ID de l'utilisateur qui a validé (manuel)
        notes: Notes additionnelles
    """
    
    __tablename__ = "payments"
    
    # Identifiant
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Références
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("cotisation_sessions.id"), nullable=False)
    tontine_id = Column(Integer, ForeignKey("tontines.id"), nullable=False)
    
    # Montant
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="FCFA", nullable=False)
    
    # Méthode et statut
    method = Column(
        PgEnum('especes', 'orange_money', 'mtn_momo', 'wave', 'free_money', 'moov_money', 'bank_transfer', name='paymentmethod', create_type=False),
        nullable=False
    )
    status = Column(
        PgEnum('en_attente', 'en_cours', 'valide', 'echoue', 'annule', 'rembourse', name='paymentstatus', create_type=False),
        default='en_attente',
        nullable=False
    )
    
    # Informations opérateur mobile money
    operator_reference = Column(String(100), unique=True, nullable=True, index=True)
    operator_transaction_id = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    
    # Données de callback de l'opérateur
    operator_callback_data = Column(JSON, nullable=True)
    
    # Preuve de paiement (pour paiements manuels)
    proof_url = Column(String(500), nullable=True)
    proof_description = Column(Text, nullable=True)
    
    # Validation manuelle
    validated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Pénalité de retard
    penalty_amount = Column(Numeric(10, 2), default=0, nullable=False)
    is_late = Column(Boolean, default=False, nullable=False)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    initiated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    user = relationship("User", back_populates="payments", foreign_keys=[user_id])
    session = relationship("CotisationSession", back_populates="payments")
    
    # Index et contraintes
    __table_args__ = (
        Index("idx_payment_user", "user_id"),
        Index("idx_payment_session", "session_id"),
        Index("idx_payment_tontine", "tontine_id"),
        Index("idx_payment_status", "status"),
        Index("idx_payment_method", "method"),
        Index("idx_payment_user_session", "user_id", "session_id"),
        Index("idx_payment_operator_ref", "operator_reference"),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("penalty_amount >= 0", name="non_negative_penalty"),
    )
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user={self.user_id}, amount={self.amount}, status={self.status})>"
    
    @property
    def total_amount(self) -> float:
        """Montant total incluant les pénalités."""
        return float(self.amount) + float(self.penalty_amount)
    
    @property
    def is_mobile_money(self) -> bool:
        """Vérifie si le paiement est via mobile money."""
        return self.method in [
            "orange_money",
            "mtn_momo",
            "wave",
            "free_money",
            "moov_money",
        ]
    
    @property
    def is_manual(self) -> bool:
        """Vérifie si le paiement nécessite une validation manuelle."""
        return self.method == "especes"
    
    @property
    def requires_validation(self) -> bool:
        """Vérifie si le paiement attend une validation."""
        return self.status == "en_attente" and self.is_manual

