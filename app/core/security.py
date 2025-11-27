"""
Module de sécurité pour Kobiri.
Gestion de l'authentification JWT et du hashage des mots de passe.
"""

from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Union

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.core.logging import logger


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie si un mot de passe en clair correspond au hash stocké.
    
    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash du mot de passe stocké
        
    Returns:
        True si le mot de passe est correct, False sinon
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du mot de passe: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash un mot de passe pour le stockage sécurisé.
    
    Args:
        password: Mot de passe en clair
        
    Returns:
        Hash du mot de passe
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(
    subject: Union[str, int],
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Crée un token JWT d'accès.
    
    Args:
        subject: Identifiant de l'utilisateur (généralement l'ID)
        role: Rôle de l'utilisateur (membre, president, tresorier)
        expires_delta: Durée de validité du token
        extra_claims: Claims supplémentaires à inclure
        
    Returns:
        Token JWT encodé
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }
    
    if extra_claims:
        to_encode.update(extra_claims)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    logger.debug(f"Token d'accès créé pour l'utilisateur {subject} avec rôle {role}")
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Crée un token JWT de rafraîchissement.
    
    Args:
        subject: Identifiant de l'utilisateur
        expires_delta: Durée de validité du token
        
    Returns:
        Token JWT de rafraîchissement encodé
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    logger.debug(f"Token de rafraîchissement créé pour l'utilisateur {subject}")
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Vérifie et décode un token JWT.
    
    Args:
        token: Token JWT à vérifier
        token_type: Type de token attendu (access ou refresh)
        
    Returns:
        Payload du token si valide, None sinon
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Vérifier le type de token
        if payload.get("type") != token_type:
            logger.warning(f"Type de token invalide: attendu {token_type}, reçu {payload.get('type')}")
            return None
        
        # Vérifier l'expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
            logger.warning("Token expiré")
            return None
        
        return payload
        
    except JWTError as e:
        logger.warning(f"Erreur de vérification du token JWT: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la vérification du token: {e}")
        return None


def decode_token_unsafe(token: str) -> Optional[Dict[str, Any]]:
    """
    Décode un token sans vérification (pour debug uniquement).
    
    Args:
        token: Token JWT à décoder
        
    Returns:
        Payload du token ou None en cas d'erreur
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False}
        )
    except JWTError:
        return None


__all__ = [
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token_unsafe",
]

