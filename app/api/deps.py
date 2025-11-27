"""
Dépendances FastAPI pour l'injection de dépendances.
Gère l'authentification, les autorisations et l'accès à la base de données.
"""

from typing import List, Optional, Union
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.core.security import verify_token
from app.core.logging import logger
from app.models.user import User, UserRole


# Schéma de sécurité Bearer Token
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Récupère l'utilisateur courant à partir du token JWT.
    
    Args:
        credentials: Token Bearer JWT
        db: Session de base de données
        
    Returns:
        Instance User de l'utilisateur authentifié
        
    Raises:
        HTTPException: Si le token est invalide ou l'utilisateur non trouvé
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token d'authentification invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        logger.warning("Tentative d'accès sans token")
        raise credentials_exception
    
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        logger.warning("Token invalide ou expiré")
        raise credentials_exception
    
    user_id = payload.get("sub")
    if user_id is None:
        logger.warning("Token sans identifiant utilisateur")
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if user is None:
        logger.warning(f"Utilisateur {user_id} non trouvé")
        raise credentials_exception
    
    logger.debug(f"Utilisateur authentifié: {user.email}")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Vérifie que l'utilisateur courant est actif.
    
    Args:
        current_user: Utilisateur courant
        
    Returns:
        Utilisateur si actif
        
    Raises:
        HTTPException: Si l'utilisateur est désactivé
    """
    if not current_user.is_active:
        logger.warning(f"Tentative d'accès par utilisateur désactivé: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte utilisateur désactivé",
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Vérifie que l'utilisateur est vérifié.
    
    Args:
        current_user: Utilisateur actif
        
    Returns:
        Utilisateur si vérifié
        
    Raises:
        HTTPException: Si l'utilisateur n'est pas vérifié
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte non vérifié. Veuillez vérifier votre email/téléphone.",
        )
    return current_user


def require_roles(allowed_roles: List[str]):
    """
    Décorateur/Dépendance pour restreindre l'accès à certains rôles.
    
    Args:
        allowed_roles: Liste des rôles autorisés
        
    Returns:
        Dépendance FastAPI qui vérifie le rôle
        
    Usage:
        @app.get("/admin", dependencies=[Depends(require_roles([UserRole.ADMIN]))])
        def admin_only():
            pass
            
        # Ou comme dépendance de route
        @app.get("/president")
        def president_view(user: User = Depends(require_roles([UserRole.PRESIDENT, UserRole.ADMIN]))):
            pass
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                f"Accès refusé pour {current_user.email}: "
                f"rôle {current_user.role} non autorisé"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôles requis: {allowed_roles}",
            )
        return current_user
    
    return role_checker


# Dépendances prédéfinies pour les rôles courants
require_admin = require_roles(["admin"])
require_president = require_roles(["president", "admin"])
require_tresorier = require_roles(["tresorier", "president", "admin"])
require_gestionnaire = require_roles(["president", "tresorier", "admin"])


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Récupère l'utilisateur courant si authentifié, sinon None.
    Utile pour les routes accessibles aux utilisateurs anonymes et authentifiés.
    
    Args:
        credentials: Token Bearer JWT (optionnel)
        db: Session de base de données
        
    Returns:
        Utilisateur si authentifié, None sinon
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        
        if payload is None:
            return None
        
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user if user and user.is_active else None
        
    except Exception:
        return None


class TontinePermission:
    """
    Vérification des permissions pour une tontine spécifique.
    Vérifie que l'utilisateur est membre et a le rôle requis dans la tontine.
    """
    
    def __init__(self, roles: List[str] = None, allow_members: bool = True):
        """
        Args:
            roles: Rôles autorisés dans la tontine (president, tresorier)
            allow_members: Autoriser les membres simples
        """
        self.roles = roles or []
        self.allow_members = allow_members
    
    async def __call__(
        self,
        tontine_id: int,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        """
        Vérifie les permissions de l'utilisateur pour la tontine.
        
        Args:
            tontine_id: ID de la tontine
            current_user: Utilisateur courant
            db: Session de base de données
            
        Returns:
            Utilisateur si autorisé
            
        Raises:
            HTTPException: Si non autorisé
        """
        from app.models.tontine import TontineMember
        
        # Admin a tous les droits
        if current_user.role == "admin":
            return current_user
        
        # Vérifier l'appartenance à la tontine
        membership = db.query(TontineMember).filter(
            TontineMember.tontine_id == tontine_id,
            TontineMember.user_id == current_user.id,
            TontineMember.is_active == True,
        ).first()
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas membre de cette tontine",
            )
        
        # Si des rôles spécifiques sont requis
        if self.roles and membership.role not in self.roles:
            if not self.allow_members:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Rôle requis: {self.roles}",
                )
        
        return current_user


# Instances de permissions prédéfinies
tontine_member = TontinePermission(allow_members=True)
tontine_manager = TontinePermission(roles=["president", "tresorier"], allow_members=False)
tontine_president = TontinePermission(roles=["president"], allow_members=False)


__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "get_current_verified_user",
    "get_optional_current_user",
    "require_roles",
    "require_admin",
    "require_president",
    "require_tresorier",
    "require_gestionnaire",
    "TontinePermission",
    "tontine_member",
    "tontine_manager",
    "tontine_president",
    "security",
]

