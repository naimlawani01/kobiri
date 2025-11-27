"""
Modèle CotisationSession - Sessions de cotisation.
Gère les cycles de collecte des cotisations.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    Numeric, ForeignKey, Index, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.database import Base


class SessionStatus(str, enum.Enum):
    """Statuts possibles d'une session de cotisation."""
    PROGRAMMEE = "programmee"   # Session planifiée mais pas encore ouverte
    EN_COURS = "en_cours"       # Collecte en cours
    EN_ATTENTE = "en_attente"   # En attente de validation
    TERMINEE = "terminee"       # Session terminée avec succès
    ANNULEE = "annulee"         # Session annulée


class CotisationSession(Base):
    """
    Modèle représentant une session de cotisation.
    
    Une session correspond à un cycle de collecte (ex: une semaine, un mois)
    durant lequel tous les membres doivent cotiser.
    
    Attributes:
        id: Identifiant unique
        tontine_id: ID de la tontine associée
        session_number: Numéro de la session (1, 2, 3...)
        scheduled_date: Date prévue de la session
        due_date: Date limite de paiement
        status: Statut actuel de la session
        expected_amount: Montant total attendu
        collected_amount: Montant total collecté
        notes: Notes additionnelles
        beneficiary_id: ID du membre qui reçoit le pot (pour tontine rotative)
    """
    
    __tablename__ = "cotisation_sessions"
    
    # Identifiant
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Référence à la tontine
    tontine_id = Column(Integer, ForeignKey("tontines.id"), nullable=False)
    
    # Numérotation
    session_number = Column(Integer, nullable=False)
    
    # Dates
    scheduled_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Statut
    status = Column(
        PgEnum('programmee', 'en_cours', 'en_attente', 'terminee', 'annulee', name='sessionstatus', create_type=False),
        default='programmee',
        nullable=False
    )
    
    # Montants
    expected_amount = Column(Numeric(14, 2), nullable=False)
    collected_amount = Column(Numeric(14, 2), default=0, nullable=False)
    
    # Bénéficiaire (pour tontine rotative)
    beneficiary_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    tontine = relationship("Tontine", back_populates="sessions")
    payments = relationship(
        "Payment",
        back_populates="session",
        lazy="selectin",
    )
    
    # Index et contraintes
    __table_args__ = (
        Index("idx_session_tontine", "tontine_id"),
        Index("idx_session_status", "status"),
        Index("idx_session_scheduled", "scheduled_date"),
        Index("idx_session_tontine_number", "tontine_id", "session_number"),
        CheckConstraint("expected_amount >= 0", name="non_negative_expected"),
        CheckConstraint("collected_amount >= 0", name="non_negative_collected"),
        CheckConstraint("session_number > 0", name="positive_session_number"),
    )
    
    def __repr__(self) -> str:
        return f"<CotisationSession(id={self.id}, tontine={self.tontine_id}, number={self.session_number}, status={self.status})>"
    
    @property
    def is_complete(self) -> bool:
        """Vérifie si tous les paiements attendus ont été reçus."""
        return float(self.collected_amount) >= float(self.expected_amount)
    
    @property
    def collection_percentage(self) -> float:
        """Retourne le pourcentage de collecte."""
        if float(self.expected_amount) == 0:
            return 0
        return (float(self.collected_amount) / float(self.expected_amount)) * 100
    
    @property
    def remaining_amount(self) -> float:
        """Montant restant à collecter."""
        return max(0, float(self.expected_amount) - float(self.collected_amount))
    
    @property
    def is_overdue(self) -> bool:
        """Vérifie si la session est en retard."""
        return (
            self.status == "en_cours" and 
            datetime.utcnow() > self.due_date
        )
    
    def get_missing_payments_count(self) -> int:
        """Retourne le nombre de paiements manquants."""
        paid_users = {p.user_id for p in self.payments if p.status == "valide"}
        tontine_members = {m.user_id for m in self.tontine.members if m.is_active}
        return len(tontine_members - paid_users)

