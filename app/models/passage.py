"""
Modèle Passage - Gestion des tours de passage.
Définit l'ordre dans lequel les membres reçoivent le pot de la tontine.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Dict

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    Numeric, ForeignKey, Index, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.database import Base


class PassageStatus(str, enum.Enum):
    """Statuts possibles d'un passage."""
    PROGRAMME = "programme"     # Passage planifié
    EN_COURS = "en_cours"       # C'est le tour de ce membre
    COMPLETE = "complete"       # Le membre a reçu son pot
    REPORTE = "reporte"         # Passage reporté
    ANNULE = "annule"           # Passage annulé


class Passage(Base):
    """
    Modèle représentant un tour de passage dans une tontine.
    
    Dans une tontine rotative, chaque membre a un tour où il reçoit
    la totalité des cotisations collectées.
    
    Attributes:
        id: Identifiant unique
        tontine_id: ID de la tontine
        member_id: ID du membre bénéficiaire
        session_id: ID de la session de cotisation associée
        order_number: Numéro d'ordre du passage (1, 2, 3...)
        scheduled_date: Date prévue du passage
        status: Statut du passage
        amount_received: Montant réellement reçu
        notes: Notes additionnelles
    """
    
    __tablename__ = "passages"
    
    # Identifiant
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Références
    tontine_id = Column(Integer, ForeignKey("tontines.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("tontine_members.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("cotisation_sessions.id"), nullable=True)
    
    # Ordre de passage
    order_number = Column(Integer, nullable=False)
    
    # Dates
    scheduled_date = Column(DateTime, nullable=False)
    actual_date = Column(DateTime, nullable=True)
    
    # Statut
    status = Column(
        PgEnum('programme', 'en_cours', 'complete', 'reporte', 'annule', name='passagestatus', create_type=False),
        default='programme',
        nullable=False
    )
    
    # Montants
    expected_amount = Column(Numeric(14, 2), nullable=False)
    amount_received = Column(Numeric(14, 2), default=0, nullable=False)
    
    # Méthode de versement
    payout_method = Column(String(50), nullable=True)  # especes, mobile_money, virement
    payout_reference = Column(String(100), nullable=True)
    payout_phone = Column(String(20), nullable=True)
    
    # Confirmations
    confirmed_by_member = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    postpone_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    tontine = relationship("Tontine", back_populates="passages")
    member = relationship("TontineMember")
    session = relationship("CotisationSession")
    
    # Index et contraintes
    __table_args__ = (
        UniqueConstraint("tontine_id", "order_number", name="unique_order_in_tontine"),
        UniqueConstraint("tontine_id", "member_id", name="unique_member_passage"),
        Index("idx_passage_tontine", "tontine_id"),
        Index("idx_passage_member", "member_id"),
        Index("idx_passage_status", "status"),
        Index("idx_passage_scheduled", "scheduled_date"),
        Index("idx_passage_order", "tontine_id", "order_number"),
        CheckConstraint("order_number > 0", name="positive_order_number"),
        CheckConstraint("expected_amount >= 0", name="non_negative_expected"),
        CheckConstraint("amount_received >= 0", name="non_negative_received"),
    )
    
    def __repr__(self) -> str:
        return f"<Passage(id={self.id}, tontine={self.tontine_id}, order={self.order_number}, status={self.status})>"
    
    @property
    def is_pending(self) -> bool:
        """Vérifie si le passage est en attente."""
        return self.status == "programme"
    
    @property
    def is_complete(self) -> bool:
        """Vérifie si le passage est terminé."""
        return self.status == "complete"
    
    @property
    def amount_difference(self) -> float:
        """Différence entre montant attendu et reçu."""
        return float(self.amount_received) - float(self.expected_amount)
    
    @property
    def is_overdue(self) -> bool:
        """Vérifie si le passage est en retard."""
        return (
            self.status == "programme" and 
            datetime.utcnow() > self.scheduled_date
        )


def generate_passage_order(tontine_id: int, members: list, method: str = "random") -> List[Dict]:
    """
    Génère l'ordre de passage pour une tontine.
    
    Args:
        tontine_id: ID de la tontine
        members: Liste des membres
        method: Méthode de génération (random, alphabetical, join_date)
        
    Returns:
        Liste de dictionnaires avec l'ordre de passage
    """
    import random
    
    if method == "random":
        shuffled = members.copy()
        random.shuffle(shuffled)
        return [
            {"member_id": m.id, "order_number": i + 1}
            for i, m in enumerate(shuffled)
        ]
    elif method == "alphabetical":
        sorted_members = sorted(members, key=lambda m: m.user.last_name)
        return [
            {"member_id": m.id, "order_number": i + 1}
            for i, m in enumerate(sorted_members)
        ]
    elif method == "join_date":
        sorted_members = sorted(members, key=lambda m: m.joined_at)
        return [
            {"member_id": m.id, "order_number": i + 1}
            for i, m in enumerate(sorted_members)
        ]
    
    return []

