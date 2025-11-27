"""
Configuration de l'application Kobiri.
Gestion centralisée de toutes les variables d'environnement.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuration principale de l'application.
    Les valeurs sont chargées depuis les variables d'environnement ou le fichier .env
    """
    
    # Configuration de l'application
    APP_NAME: str = "Kobiri"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Configuration de la base de données
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/kobiri"
    
    # Configuration JWT
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Configuration des opérateurs de paiement mobile
    ORANGE_MONEY_API_KEY: Optional[str] = None
    ORANGE_MONEY_API_SECRET: Optional[str] = None
    ORANGE_MONEY_CALLBACK_URL: Optional[str] = None
    
    MTN_MOMO_API_KEY: Optional[str] = None
    MTN_MOMO_API_SECRET: Optional[str] = None
    MTN_MOMO_CALLBACK_URL: Optional[str] = None
    
    WAVE_API_KEY: Optional[str] = None
    WAVE_API_SECRET: Optional[str] = None
    WAVE_CALLBACK_URL: Optional[str] = None
    
    # Configuration SMS
    SMS_API_KEY: Optional[str] = None
    SMS_SENDER_ID: str = "KOBIRI"
    
    # Configuration Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@kobiri.com"
    
    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne une instance unique des paramètres (singleton pattern).
    Utilise le cache LRU pour éviter de recharger les variables à chaque appel.
    """
    return Settings()


# Instance globale des paramètres
settings = get_settings()

