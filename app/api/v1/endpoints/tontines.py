"""
Routes CRUD pour les tontines et leurs membres.
"""

from typing import Any, List, Optional
from datetime import datetime
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.database import get_db
from app.core.logging import logger
from app.models.user import User, UserRole
from app.models.tontine import Tontine, TontineMember, TontineType, TontineFrequency
from app.schemas.tontine import (
    TontineCreate,
    TontineUpdate,
    TontineResponse,
    TontineListResponse,
    TontineMemberCreate,
    TontineMemberUpdate,
    TontineMemberResponse,
    JoinTontineRequest,
)
from app.api.deps import (
    get_current_active_user,
    TontinePermission,
    tontine_manager,
)


router = APIRouter()


def generate_tontine_code(length: int = 6) -> str:
    """Génère un code unique pour la tontine."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.post(
    "/",
    response_model=TontineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une tontine",
)
async def create_tontine(
    tontine_data: TontineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Crée une nouvelle tontine.
    Le créateur devient automatiquement président de la tontine.
    """
    logger.info(f"Création de tontine par {current_user.email}: {tontine_data.name}")
    
    # Générer un code unique
    code = generate_tontine_code()
    while db.query(Tontine).filter(Tontine.code == code).first():
        code = generate_tontine_code()
    
    # Créer la tontine
    tontine = Tontine(
        name=tontine_data.name,
        description=tontine_data.description,
        code=code,
        type=tontine_data.type.value if hasattr(tontine_data.type, 'value') else tontine_data.type,
        frequency=tontine_data.frequency.value if hasattr(tontine_data.frequency, 'value') else tontine_data.frequency,
        contribution_amount=tontine_data.contribution_amount,
        currency=tontine_data.currency,
        max_members=tontine_data.max_members,
        min_members=tontine_data.min_members,
        start_date=tontine_data.start_date,
        end_date=tontine_data.end_date,
        rules=tontine_data.rules,
        penalty_amount=tontine_data.penalty_amount,
        grace_period_days=tontine_data.grace_period_days,
        is_public=tontine_data.is_public,
        created_by_id=current_user.id,
    )
    
    db.add(tontine)
    db.flush()
    
    # Ajouter le créateur comme président
    member = TontineMember(
        user_id=current_user.id,
        tontine_id=tontine.id,
        role="president",
        order_position=1,
    )
    db.add(member)
    
    db.commit()
    db.refresh(tontine)
    
    logger.info(f"Tontine créée: {tontine.name} (ID: {tontine.id}, Code: {tontine.code})")
    
    return tontine


@router.get(
    "/",
    response_model=TontineListResponse,
    summary="Liste des tontines",
)
async def list_tontines(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Recherche par nom"),
    type: Optional[TontineType] = Query(None),
    frequency: Optional[TontineFrequency] = Query(None),
    is_public: Optional[bool] = Query(None),
    my_tontines: bool = Query(False, description="Uniquement mes tontines"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste les tontines accessibles à l'utilisateur.
    """
    query = db.query(Tontine).options(joinedload(Tontine.members))
    
    if my_tontines:
        # Seulement les tontines où l'utilisateur est membre
        member_tontine_ids = db.query(TontineMember.tontine_id).filter(
            TontineMember.user_id == current_user.id,
            TontineMember.is_active == True,
        ).subquery()
        query = query.filter(Tontine.id.in_(member_tontine_ids))
    elif current_user.role != "admin":
        # Tontines publiques ou dont l'utilisateur est membre
        member_tontine_ids = db.query(TontineMember.tontine_id).filter(
            TontineMember.user_id == current_user.id,
            TontineMember.is_active == True,
        ).subquery()
        query = query.filter(
            or_(
                Tontine.is_public == True,
                Tontine.id.in_(member_tontine_ids),
            )
        )
    
    # Filtres
    if search:
        query = query.filter(Tontine.name.ilike(f"%{search}%"))
    if type:
        query = query.filter(Tontine.type == type)
    if frequency:
        query = query.filter(Tontine.frequency == frequency)
    if is_public is not None:
        query = query.filter(Tontine.is_public == is_public)
    
    query = query.filter(Tontine.is_active == True)
    
    total = query.count()
    tontines = query.order_by(Tontine.created_at.desc()).offset(skip).limit(limit).all()
    
    return TontineListResponse(
        items=tontines,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get(
    "/{tontine_id}",
    response_model=TontineResponse,
    summary="Détails d'une tontine",
)
async def get_tontine(
    tontine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les détails d'une tontine.
    """
    tontine = db.query(Tontine).options(
        joinedload(Tontine.members).joinedload(TontineMember.user)
    ).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    # Vérifier les permissions
    is_member = any(m.user_id == current_user.id for m in tontine.members)
    if not tontine.is_public and not is_member and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cette tontine",
        )
    
    return tontine


@router.put(
    "/{tontine_id}",
    response_model=TontineResponse,
    summary="Mettre à jour une tontine",
)
async def update_tontine(
    tontine_id: int,
    tontine_data: TontineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(TontinePermission(roles=["president"])),
) -> Any:
    """
    Met à jour une tontine (président uniquement).
    """
    tontine = db.query(Tontine).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    update_data = tontine_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tontine, field, value)
    
    tontine.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tontine)
    
    logger.info(f"Tontine {tontine_id} mise à jour par {current_user.email}")
    
    return tontine


@router.delete(
    "/{tontine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver une tontine",
)
async def delete_tontine(
    tontine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(TontinePermission(roles=["president"])),
) -> None:
    """
    Désactive une tontine (soft delete).
    """
    tontine = db.query(Tontine).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    tontine.is_active = False
    tontine.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Tontine {tontine_id} désactivée par {current_user.email}")


# ============== Routes pour les membres ==============

@router.post(
    "/{tontine_id}/members",
    response_model=TontineMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un membre",
)
async def add_member(
    tontine_id: int,
    member_data: TontineMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(TontinePermission(roles=["president", "tresorier"])),
) -> Any:
    """
    Ajoute un membre à la tontine (gestionnaire uniquement).
    """
    tontine = db.query(Tontine).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    if tontine.is_full:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La tontine est complète",
        )
    
    # Vérifier si l'utilisateur existe
    user = db.query(User).filter(User.id == member_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    # Vérifier si déjà membre
    existing = db.query(TontineMember).filter(
        TontineMember.tontine_id == tontine_id,
        TontineMember.user_id == member_data.user_id,
    ).first()
    
    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cet utilisateur est déjà membre de la tontine",
            )
        else:
            # Réactiver le membre
            existing.is_active = True
            existing.left_at = None
            db.commit()
            db.refresh(existing)
            return existing
    
    # Créer le membre
    member = TontineMember(
        user_id=member_data.user_id,
        tontine_id=tontine_id,
        role=member_data.role,
        order_position=member_data.order_position,
    )
    
    db.add(member)
    db.commit()
    db.refresh(member)
    
    logger.info(f"Membre {member_data.user_id} ajouté à la tontine {tontine_id}")
    
    return member


@router.post(
    "/join",
    response_model=TontineMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rejoindre une tontine par code",
)
async def join_tontine(
    join_data: JoinTontineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Permet à un utilisateur de rejoindre une tontine en utilisant son code.
    """
    tontine = db.query(Tontine).filter(
        Tontine.code == join_data.code.upper(),
        Tontine.is_active == True,
    ).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code de tontine invalide",
        )
    
    if tontine.is_full:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette tontine est complète",
        )
    
    # Vérifier si déjà membre
    existing = db.query(TontineMember).filter(
        TontineMember.tontine_id == tontine.id,
        TontineMember.user_id == current_user.id,
    ).first()
    
    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous êtes déjà membre de cette tontine",
            )
        else:
            existing.is_active = True
            existing.left_at = None
            db.commit()
            db.refresh(existing)
            return existing
    
    # Rejoindre
    member = TontineMember(
        user_id=current_user.id,
        tontine_id=tontine.id,
        role="membre",
    )
    
    db.add(member)
    db.commit()
    db.refresh(member)
    
    logger.info(f"Utilisateur {current_user.id} a rejoint la tontine {tontine.id}")
    
    return member


@router.get(
    "/{tontine_id}/members",
    response_model=List[TontineMemberResponse],
    summary="Liste des membres",
)
async def list_members(
    tontine_id: int,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste les membres d'une tontine.
    """
    tontine = db.query(Tontine).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    query = db.query(TontineMember).options(
        joinedload(TontineMember.user)
    ).filter(TontineMember.tontine_id == tontine_id)
    
    if not include_inactive:
        query = query.filter(TontineMember.is_active == True)
    
    members = query.order_by(TontineMember.order_position.nullsfirst()).all()
    
    # Enrichir avec les infos utilisateur
    result = []
    for m in members:
        member_dict = {
            "id": m.id,
            "user_id": m.user_id,
            "tontine_id": m.tontine_id,
            "role": m.role,
            "order_position": m.order_position,
            "is_active": m.is_active,
            "joined_at": m.joined_at,
            "left_at": m.left_at,
            "total_contributions": m.total_contributions,
            "total_received": m.total_received,
            "missed_payments": m.missed_payments,
            "user_email": m.user.email if m.user else None,
            "user_name": m.user.full_name if m.user else None,
            "user_phone": m.user.phone if m.user else None,
        }
        result.append(member_dict)
    
    return result


@router.put(
    "/{tontine_id}/members/{member_id}",
    response_model=TontineMemberResponse,
    summary="Modifier un membre",
)
async def update_member(
    tontine_id: int,
    member_id: int,
    member_data: TontineMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(TontinePermission(roles=["president"])),
) -> Any:
    """
    Modifie le rôle ou la position d'un membre (président uniquement).
    """
    member = db.query(TontineMember).filter(
        TontineMember.id == member_id,
        TontineMember.tontine_id == tontine_id,
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membre non trouvé",
        )
    
    update_data = member_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(member, field, value)
    
    db.commit()
    db.refresh(member)
    
    logger.info(f"Membre {member_id} modifié dans la tontine {tontine_id}")
    
    return member


@router.delete(
    "/{tontine_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un membre",
)
async def remove_member(
    tontine_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(TontinePermission(roles=["president"])),
) -> None:
    """
    Retire un membre de la tontine (soft delete).
    """
    member = db.query(TontineMember).filter(
        TontineMember.id == member_id,
        TontineMember.tontine_id == tontine_id,
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membre non trouvé",
        )
    
    # Ne pas permettre au président de se retirer lui-même
    if member.role == "president" and member.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le président ne peut pas se retirer. Transférez d'abord le rôle.",
        )
    
    member.is_active = False
    member.left_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Membre {member_id} retiré de la tontine {tontine_id}")


@router.post(
    "/{tontine_id}/leave",
    status_code=status.HTTP_200_OK,
    summary="Quitter une tontine",
)
async def leave_tontine(
    tontine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Permet à l'utilisateur de quitter une tontine.
    """
    member = db.query(TontineMember).filter(
        TontineMember.tontine_id == tontine_id,
        TontineMember.user_id == current_user.id,
        TontineMember.is_active == True,
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vous n'êtes pas membre de cette tontine",
        )
    
    if member.role == "president":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le président ne peut pas quitter la tontine. Transférez d'abord le rôle.",
        )
    
    member.is_active = False
    member.left_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Utilisateur {current_user.id} a quitté la tontine {tontine_id}")
    
    return {"message": "Vous avez quitté la tontine"}

