"""
Modèle User - Utilisateurs de la plateforme Kobiri.
Gère les informations personnelles, l'authentification et les rôles.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    Index, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """Rôles disponibles pour les utilisateurs."""
    MEMBRE = "membre"           # Membre standard d'une tontine
    PRESIDENT = "president"     # Président d'une tontine (gestionnaire)
    TRESORIER = "tresorier"     # Trésorier (gestion financière)
    ADMIN = "admin"             # Administrateur de la plateforme


class User(Base):
    """
    Modèle représentant un utilisateur de la plateforme.
    
    Attributes:
        id: Identifiant unique
        email: Adresse email (unique)
        phone: Numéro de téléphone (unique, format international)
        hashed_password: Mot de passe hashé
        first_name: Prénom
        last_name: Nom de famille
        role: Rôle par défaut de l'utilisateur
        is_active: Compte actif ou non
        is_verified: Email/téléphone vérifié
        profile_picture: URL de la photo de profil
        address: Adresse postale
        city: Ville
        country: Pays (défaut: Sénégal)
        created_at: Date de création du compte
        updated_at: Date de dernière mise à jour
        last_login: Date de dernière connexion
    """
    
    __tablename__ = "users"
    
    # Identifiant
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Authentification
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Informations personnelles
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    profile_picture = Column(String(500), nullable=True)
    
    # Adresse
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), default="Sénégal")
    
    # Rôle et statut
    role = Column(
        PgEnum('membre', 'president', 'tresorier', 'admin', name='userrole', create_type=False),
        default='membre',
        nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Token de réinitialisation de mot de passe
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    
    # Code de vérification
    verification_code = Column(String(6), nullable=True)
    verification_code_expires = Column(DateTime, nullable=True)
    
    # Relations
    tontine_memberships = relationship(
        "TontineMember",
        back_populates="user",
        lazy="selectin",  # Chargement optimisé
    )
    payments = relationship(
        "Payment",
        back_populates="user",
        foreign_keys="[Payment.user_id]",
        lazy="selectin",
    )
    notifications = relationship(
        "Notification",
        back_populates="user",
        foreign_keys="[Notification.user_id]",
        lazy="selectin",
    )
    
    # Index et contraintes
    __table_args__ = (
        Index("idx_user_email_active", "email", "is_active"),
        Index("idx_user_phone_active", "phone", "is_active"),
        Index("idx_user_role", "role"),
        CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name="valid_email"),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role={self.role})>"
    
    @property
    def full_name(self) -> str:
        """Retourne le nom complet de l'utilisateur."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur est administrateur."""
        return self.role == "admin"
    
    def can_manage_tontine(self) -> bool:
        """Vérifie si l'utilisateur peut gérer une tontine."""
        return self.role in ["president", "tresorier", "admin"]

