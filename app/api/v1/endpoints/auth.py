"""
Routes d'authentification - Inscription, connexion, tokens.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    verify_token,
)
from app.core.logging import logger
from app.config import settings
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    Token,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
)
from app.api.deps import get_current_user, get_current_active_user
from app.services.email_service import email_service


router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> Any:
    """
    Crée un nouveau compte utilisateur.
    
    - **email**: Adresse email unique
    - **phone**: Numéro de téléphone unique (format: +221XXXXXXXXX)
    - **password**: Mot de passe (min 8 caractères, 1 majuscule, 1 chiffre)
    - **first_name**: Prénom
    - **last_name**: Nom de famille
    """
    logger.info(f"Tentative d'inscription: {user_data.email}")
    
    # Vérifier si l'email existe déjà
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        logger.warning(f"Email déjà utilisé: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte existe déjà avec cet email",
        )
    
    # Vérifier si le téléphone existe déjà
    existing_phone = db.query(User).filter(User.phone == user_data.phone).first()
    if existing_phone:
        logger.warning(f"Téléphone déjà utilisé: {user_data.phone}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte existe déjà avec ce numéro de téléphone",
        )
    
    # Créer l'utilisateur
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        phone=user_data.phone,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        address=user_data.address,
        city=user_data.city,
        country=user_data.country,
        role="membre",
        is_active=True,
        is_verified=False,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Nouvel utilisateur créé: {user.email} (ID: {user.id})")
    
    # TODO: Envoyer email/SMS de vérification
    
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Connexion utilisateur",
)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
) -> Any:
    """
    Authentifie un utilisateur et retourne les tokens JWT.
    
    Peut se connecter avec email ou téléphone.
    """
    logger.info(f"Tentative de connexion: {credentials.email or credentials.phone}")
    
    # Trouver l'utilisateur par email ou téléphone
    user = None
    if credentials.email:
        user = db.query(User).filter(User.email == credentials.email).first()
    elif credentials.phone:
        user = db.query(User).filter(User.phone == credentials.phone).first()
    
    if not user:
        logger.warning(f"Utilisateur non trouvé: {credentials.email or credentials.phone}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email/téléphone ou mot de passe incorrect",
        )
    
    # Vérifier le mot de passe
    if not verify_password(credentials.password, user.hashed_password):
        logger.warning(f"Mot de passe incorrect pour: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email/téléphone ou mot de passe incorrect",
        )
    
    # Vérifier si le compte est actif
    if not user.is_active:
        logger.warning(f"Compte désactivé: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte a été désactivé",
        )
    
    # Mettre à jour la date de dernière connexion
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Générer les tokens
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
    )
    refresh_token = create_refresh_token(subject=user.id)
    
    logger.info(f"Connexion réussie: {user.email}")
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Rafraîchir le token d'accès",
)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db),
) -> Any:
    """
    Génère un nouveau token d'accès à partir du refresh token.
    """
    payload = verify_token(refresh_token, token_type="refresh")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré",
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé ou désactivé",
        )
    
    # Générer de nouveaux tokens
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
    )
    new_refresh_token = create_refresh_token(subject=user.id)
    
    logger.info(f"Token rafraîchi pour: {user.email}")
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Profil de l'utilisateur connecté",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retourne les informations de l'utilisateur connecté.
    """
    return current_user


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Changer le mot de passe",
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Change le mot de passe de l'utilisateur connecté.
    """
    # Vérifier l'ancien mot de passe
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect",
        )
    
    # Mettre à jour le mot de passe
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    logger.info(f"Mot de passe changé pour: {current_user.email}")
    
    return {"message": "Mot de passe mis à jour avec succès"}


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Demander la réinitialisation du mot de passe",
)
async def forgot_password(
    reset_data: PasswordReset,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    """
    Envoie un email avec un code de réinitialisation du mot de passe.
    """
    import random
    
    user = None
    if reset_data.email:
        user = db.query(User).filter(User.email == reset_data.email).first()
    elif reset_data.phone:
        user = db.query(User).filter(User.phone == reset_data.phone).first()
    
    # Pour des raisons de sécurité, ne pas révéler si l'utilisateur existe
    if user:
        # Générer un code à 6 chiffres
        reset_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        user.reset_token = reset_code
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        
        logger.info(f"Code de réinitialisation généré pour: {user.email}")
        
        # Envoyer l'email en arrière-plan
        background_tasks.add_task(
            email_service.send_password_reset_email,
            user.email,
            user.full_name,
            reset_code,
        )
    
    return {
        "message": "Si un compte existe avec ces informations, "
                   "vous recevrez un email avec un code de réinitialisation"
    }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Réinitialiser le mot de passe avec le code",
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> Any:
    """
    Réinitialise le mot de passe avec le code reçu par email.
    """
    # Trouver l'utilisateur par email
    user = db.query(User).filter(User.email == reset_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email non trouvé",
        )
    
    # Vérifier le code
    if not user.reset_token or user.reset_token != reset_data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code de réinitialisation invalide",
        )
    
    # Vérifier l'expiration
    if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le code a expiré. Veuillez en demander un nouveau.",
        )
    
    # Mettre à jour le mot de passe
    user.hashed_password = get_password_hash(reset_data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    
    logger.info(f"Mot de passe réinitialisé pour: {user.email}")
    
    return {"message": "Mot de passe réinitialisé avec succès"}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Déconnexion",
)
async def logout(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Déconnecte l'utilisateur.
    Note: Avec JWT, la déconnexion est gérée côté client en supprimant le token.
    Cette route peut être utilisée pour invalider le token côté serveur si nécessaire.
    """
    logger.info(f"Déconnexion: {current_user.email}")
    
    # TODO: Implémenter une blacklist de tokens si nécessaire
    
    return {"message": "Déconnexion réussie"}

