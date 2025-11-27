"""
Modèle Tontine - Groupes d'épargne rotatif.
Gère les paramètres de la tontine, les membres et l'ordre de passage.
"""

import enum
from datetime import datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    Numeric, ForeignKey, Index, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.database import Base


class TontineType(str, enum.Enum):
    """Types de tontine disponibles."""
    ROTATIVE = "rotative"       # Chaque membre reçoit à tour de rôle
    CUMULATIVE = "cumulative"   # Accumulation jusqu'à la fin
    MIXTE = "mixte"             # Combinaison des deux


class TontineFrequency(str, enum.Enum):
    """Fréquence des cotisations."""
    QUOTIDIEN = "quotidien"
    HEBDOMADAIRE = "hebdomadaire"
    BIMENSUEL = "bimensuel"     # Deux fois par mois
    MENSUEL = "mensuel"
    TRIMESTRIEL = "trimestriel"


class Tontine(Base):
    """
    Modèle représentant une tontine.
    
    Attributes:
        id: Identifiant unique
        name: Nom de la tontine
        description: Description détaillée
        type: Type de tontine (rotative, cumulative, mixte)
        frequency: Fréquence des cotisations
        contribution_amount: Montant de la cotisation par membre
        currency: Devise (défaut: FCFA)
        max_members: Nombre maximum de membres
        start_date: Date de début
        end_date: Date de fin prévue
        is_active: Tontine active ou non
        rules: Règles spécifiques de la tontine
        penalty_amount: Montant de la pénalité de retard
        grace_period_days: Jours de grâce avant pénalité
        created_by_id: ID de l'utilisateur créateur
    """
    
    __tablename__ = "tontines"
    
    # Identifiant
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Informations de base
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    code = Column(String(10), unique=True, nullable=False, index=True)  # Code court pour rejoindre
    
    # Configuration
    type = Column(
        PgEnum('rotative', 'cumulative', 'mixte', name='tontinetype', create_type=False),
        default='rotative',
        nullable=False
    )
    frequency = Column(
        PgEnum('quotidien', 'hebdomadaire', 'bimensuel', 'mensuel', 'trimestriel', name='tontinefrequency', create_type=False),
        default='mensuel',
        nullable=False
    )
    contribution_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="FCFA", nullable=False)
    
    # Limites
    max_members = Column(Integer, default=12, nullable=False)
    min_members = Column(Integer, default=3, nullable=False)
    
    # Dates
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    
    # Règles
    rules = Column(Text, nullable=True)
    penalty_amount = Column(Numeric(10, 2), default=0, nullable=False)
    grace_period_days = Column(Integer, default=3, nullable=False)
    
    # Statut
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)  # Visible pour tous
    
    # Créateur
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    members = relationship(
        "TontineMember",
        back_populates="tontine",
        lazy="selectin",
        order_by="TontineMember.order_position",
    )
    sessions = relationship(
        "CotisationSession",
        back_populates="tontine",
        lazy="selectin",
        order_by="CotisationSession.scheduled_date.desc()",
    )
    passages = relationship(
        "Passage",
        back_populates="tontine",
        lazy="selectin",
        order_by="Passage.order_number",
    )
    
    # Index et contraintes
    __table_args__ = (
        Index("idx_tontine_active", "is_active"),
        Index("idx_tontine_created_by", "created_by_id"),
        Index("idx_tontine_public_active", "is_public", "is_active"),
        CheckConstraint("contribution_amount > 0", name="positive_contribution"),
        CheckConstraint("max_members >= min_members", name="valid_member_limits"),
        CheckConstraint("penalty_amount >= 0", name="non_negative_penalty"),
    )
    
    def __repr__(self) -> str:
        return f"<Tontine(id={self.id}, name='{self.name}', type={self.type})>"
    
    @property
    def member_count(self) -> int:
        """Retourne le nombre actuel de membres."""
        return len([m for m in self.members if m.is_active])
    
    @property
    def is_full(self) -> bool:
        """Vérifie si la tontine est complète."""
        return self.member_count >= self.max_members
    
    @property
    def total_pot(self) -> float:
        """Calcule le montant total du pot par session."""
        return float(self.contribution_amount) * self.member_count


class TontineMember(Base):
    """
    Association entre utilisateurs et tontines.
    Gère le rôle du membre dans la tontine et sa position dans l'ordre de passage.
    
    Attributes:
        user_id: ID de l'utilisateur
        tontine_id: ID de la tontine
        role: Rôle dans cette tontine spécifique
        order_position: Position dans l'ordre de passage
        is_active: Membre actif dans la tontine
        joined_at: Date d'adhésion
    """
    
    __tablename__ = "tontine_members"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Clés étrangères
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tontine_id = Column(Integer, ForeignKey("tontines.id"), nullable=False)
    
    # Rôle dans la tontine (peut différer du rôle global)
    role = Column(String(50), default="membre", nullable=False)  # membre, president, tresorier
    
    # Ordre de passage
    order_position = Column(Integer, nullable=True)  # NULL si pas encore défini
    
    # Statut
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)
    
    # Statistiques du membre
    total_contributions = Column(Numeric(14, 2), default=0, nullable=False)
    total_received = Column(Numeric(14, 2), default=0, nullable=False)
    missed_payments = Column(Integer, default=0, nullable=False)
    
    # Relations
    user = relationship("User", back_populates="tontine_memberships")
    tontine = relationship("Tontine", back_populates="members")
    
    # Contraintes
    __table_args__ = (
        UniqueConstraint("user_id", "tontine_id", name="unique_membership"),
        Index("idx_member_tontine", "tontine_id", "is_active"),
        Index("idx_member_user", "user_id", "is_active"),
        Index("idx_member_order", "tontine_id", "order_position"),
    )
    
    def __repr__(self) -> str:
        return f"<TontineMember(user_id={self.user_id}, tontine_id={self.tontine_id}, role='{self.role}')>"

