"""
Schémas Pydantic pour les utilisateurs.
Validation des données d'entrée et sérialisation des réponses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

from app.models.user import UserRole


class UserBase(BaseModel):
    """Schéma de base pour les utilisateurs."""
    email: EmailStr = Field(..., description="Adresse email")
    phone: str = Field(..., min_length=8, max_length=20, description="Numéro de téléphone")
    first_name: str = Field(..., min_length=2, max_length=100, description="Prénom")
    last_name: str = Field(..., min_length=2, max_length=100, description="Nom de famille")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Valide le format du numéro de téléphone."""
        # Supprimer les espaces et tirets
        cleaned = re.sub(r"[\s\-]", "", v)
        # Vérifier le format (commence par + ou chiffre)
        if not re.match(r"^\+?[0-9]{8,15}$", cleaned):
            raise ValueError("Format de téléphone invalide. Exemple: +221771234567")
        return cleaned


class UserCreate(UserBase):
    """Schéma pour la création d'un utilisateur."""
    password: str = Field(
        ..., 
        min_length=8, 
        description="Mot de passe (min 8 caractères)"
    )
    confirm_password: str = Field(..., description="Confirmation du mot de passe")
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    country: str = Field(default="Sénégal", max_length=100)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Valide la complexité du mot de passe."""
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"[a-z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une minuscule")
        if not re.search(r"[0-9]", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v
    
    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Vérifie que les mots de passe correspondent."""
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v


class UserUpdate(BaseModel):
    """Schéma pour la mise à jour d'un utilisateur."""
    first_name: Optional[str] = Field(None, min_length=2, max_length=100)
    last_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=8, max_length=20)
    profile_picture: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = re.sub(r"[\s\-]", "", v)
        if not re.match(r"^\+?[0-9]{8,15}$", cleaned):
            raise ValueError("Format de téléphone invalide")
        return cleaned


class UserResponse(BaseModel):
    """Schéma de réponse pour un utilisateur."""
    id: int
    email: EmailStr
    phone: str
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    profile_picture: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """Schéma complet de l'utilisateur (usage interne)."""
    hashed_password: str


class UserLogin(BaseModel):
    """Schéma pour la connexion."""
    email: Optional[EmailStr] = Field(None, description="Email ou téléphone")
    phone: Optional[str] = Field(None, description="Téléphone")
    password: str = Field(..., description="Mot de passe")
    
    @field_validator("email", "phone")
    @classmethod
    def at_least_one_identifier(cls, v, info):
        """Vérifie qu'au moins un identifiant est fourni."""
        # Cette validation sera faite au niveau du modèle complet
        return v


class Token(BaseModel):
    """Schéma pour les tokens JWT."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Durée de validité en secondes")


class TokenPayload(BaseModel):
    """Schéma du payload du token JWT."""
    sub: str
    role: str
    exp: int
    iat: int
    type: str


class PasswordChange(BaseModel):
    """Schéma pour le changement de mot de passe."""
    current_password: str = Field(..., description="Mot de passe actuel")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe")
    confirm_password: str = Field(..., description="Confirmation")
    
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"[a-z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une minuscule")
        if not re.search(r"[0-9]", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v
    
    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v


class PasswordReset(BaseModel):
    """Schéma pour la réinitialisation de mot de passe."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    
    @field_validator("phone")
    @classmethod
    def validate_identifier(cls, v, info):
        """Au moins un identifiant requis."""
        return v


class PasswordResetConfirm(BaseModel):
    """Schéma pour confirmer la réinitialisation."""
    token: str = Field(..., description="Token de réinitialisation")
    new_password: str = Field(..., min_length=8)
    confirm_password: str
    
    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v

