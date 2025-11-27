"""
Routes CRUD pour les utilisateurs.
"""

from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.core.logging import logger
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.api.deps import (
    get_current_active_user,
    require_roles,
    require_admin,
)


router = APIRouter()


@router.get(
    "/",
    response_model=List[UserResponse],
    summary="Liste des utilisateurs",
)
async def list_users(
    skip: int = Query(0, ge=0, description="Nombre d'éléments à sauter"),
    limit: int = Query(50, ge=1, le=100, description="Nombre max d'éléments"),
    search: Optional[str] = Query(None, description="Recherche par nom/email/téléphone"),
    role: Optional[UserRole] = Query(None, description="Filtrer par rôle"),
    is_active: Optional[bool] = Query(None, description="Filtrer par statut actif"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Liste tous les utilisateurs (admin uniquement).
    Supporte la pagination et les filtres.
    """
    logger.info(f"Liste des utilisateurs demandée par {current_user.email}")
    
    query = db.query(User)
    
    # Filtre de recherche
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term),
                User.phone.ilike(search_term),
            )
        )
    
    # Filtre par rôle
    if role:
        query = query.filter(User.role == role)
    
    # Filtre par statut
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    return users


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Détails d'un utilisateur",
)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les détails d'un utilisateur.
    Les utilisateurs peuvent voir leur propre profil, les admins peuvent voir tous.
    """
    # Vérifier les permissions
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez accéder qu'à votre propre profil",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Mettre à jour un utilisateur",
)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Met à jour les informations d'un utilisateur.
    Les utilisateurs peuvent modifier leur propre profil.
    """
    # Vérifier les permissions
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez modifier que votre propre profil",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    # Vérifier l'unicité du téléphone si modifié
    if user_data.phone and user_data.phone != user.phone:
        existing = db.query(User).filter(
            User.phone == user_data.phone,
            User.id != user_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce numéro de téléphone est déjà utilisé",
            )
    
    # Mettre à jour les champs fournis
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    logger.info(f"Utilisateur {user_id} mis à jour par {current_user.email}")
    
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un utilisateur",
)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """
    Désactive un compte utilisateur (soft delete).
    Admin uniquement.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte",
        )
    
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Utilisateur {user_id} désactivé par {current_user.email}")


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Réactiver un utilisateur",
)
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Réactive un compte utilisateur désactivé.
    Admin uniquement.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    user.is_active = True
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    logger.info(f"Utilisateur {user_id} réactivé par {current_user.email}")
    
    return user


@router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Changer le rôle d'un utilisateur",
)
async def change_user_role(
    user_id: int,
    role: UserRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Change le rôle d'un utilisateur.
    Admin uniquement.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas changer votre propre rôle",
        )
    
    old_role = user.role
    user.role = role
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    logger.info(
        f"Rôle de l'utilisateur {user_id} changé de {old_role} à {role} "
        f"par {current_user.email}"
    )
    
    return user

