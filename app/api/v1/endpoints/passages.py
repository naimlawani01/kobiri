"""
Routes pour la gestion des tours de passage.
"""

from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.core.logging import logger
from app.models.user import User, UserRole
from app.models.tontine import Tontine, TontineMember
from app.models.session import CotisationSession
from app.models.passage import Passage, PassageStatus, generate_passage_order
from app.schemas.passage import (
    PassageCreate,
    PassageUpdate,
    PassageResponse,
    PassageListResponse,
    PassageOrderUpdate,
    GeneratePassageOrder,
    PassageConfirmation,
    PassagePayout,
    PassageSchedule,
)
from app.api.deps import (
    get_current_active_user,
    TontinePermission,
)


router = APIRouter()


@router.post(
    "/generate/{tontine_id}",
    response_model=List[PassageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Générer l'ordre de passage",
)
async def generate_order(
    tontine_id: int,
    request: GeneratePassageOrder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Génère automatiquement l'ordre de passage pour une tontine.
    Méthodes disponibles: random, alphabetical, join_date
    """
    # Vérifier les permissions
    permission = TontinePermission(roles=["president"])
    await permission(tontine_id, current_user, db)
    
    tontine = db.query(Tontine).options(
        joinedload(Tontine.members).joinedload(TontineMember.user)
    ).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    # Vérifier qu'il n'y a pas déjà des passages
    existing = db.query(Passage).filter(Passage.tontine_id == tontine_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'ordre de passage existe déjà. Utilisez PUT pour modifier.",
        )
    
    active_members = [m for m in tontine.members if m.is_active]
    
    if len(active_members) < tontine.min_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pas assez de membres. Minimum requis: {tontine.min_members}",
        )
    
    # Générer l'ordre
    order = generate_passage_order(tontine_id, active_members, request.method)
    
    # Calculer le montant attendu par passage
    expected_amount = float(tontine.contribution_amount) * len(active_members)
    
    # Créer les passages
    passages = []
    for item in order:
        # Calculer la date prévue en fonction de la fréquence
        from dateutil.relativedelta import relativedelta
        
        frequency_delta = {
            "quotidien": relativedelta(days=1),
            "hebdomadaire": relativedelta(weeks=1),
            "bimensuel": relativedelta(weeks=2),
            "mensuel": relativedelta(months=1),
            "trimestriel": relativedelta(months=3),
        }
        
        delta = frequency_delta.get(tontine.frequency.value, relativedelta(months=1))
        scheduled_date = tontine.start_date + (delta * (item["order_number"] - 1))
        
        passage = Passage(
            tontine_id=tontine_id,
            member_id=item["member_id"],
            order_number=item["order_number"],
            scheduled_date=scheduled_date,
            expected_amount=expected_amount,
            status="programme",
        )
        
        db.add(passage)
        passages.append(passage)
        
        # Mettre à jour la position du membre
        member = db.query(TontineMember).filter(
            TontineMember.id == item["member_id"]
        ).first()
        if member:
            member.order_position = item["order_number"]
    
    db.commit()
    
    for p in passages:
        db.refresh(p)
    
    logger.info(
        f"Ordre de passage généré pour tontine {tontine_id} "
        f"({len(passages)} passages) par {current_user.email}"
    )
    
    return passages


@router.get(
    "/tontine/{tontine_id}",
    response_model=PassageListResponse,
    summary="Liste des passages d'une tontine",
)
async def list_passages(
    tontine_id: int,
    status_filter: Optional[PassageStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste les passages d'une tontine ordonnés par numéro.
    """
    # Vérifier l'accès
    permission = TontinePermission()
    await permission(tontine_id, current_user, db)
    
    query = db.query(Passage).options(
        joinedload(Passage.member).joinedload(TontineMember.user)
    ).filter(Passage.tontine_id == tontine_id)
    
    if status_filter:
        query = query.filter(Passage.status == status_filter)
    
    total = query.count()
    passages = query.order_by(Passage.order_number).offset(skip).limit(limit).all()
    
    return PassageListResponse(
        items=passages,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get(
    "/tontine/{tontine_id}/schedule",
    response_model=PassageSchedule,
    summary="Planning complet des passages",
)
async def get_schedule(
    tontine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère le planning complet des passages avec le passage actuel et le prochain.
    """
    permission = TontinePermission()
    await permission(tontine_id, current_user, db)
    
    tontine = db.query(Tontine).filter(Tontine.id == tontine_id).first()
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    passages = db.query(Passage).options(
        joinedload(Passage.member).joinedload(TontineMember.user)
    ).filter(
        Passage.tontine_id == tontine_id
    ).order_by(Passage.order_number).all()
    
    current = next(
        (p for p in passages if p.status == "en_cours"),
        None
    )
    
    next_passage = next(
        (p for p in passages if p.status == "programme"),
        None
    )
    
    completed = len([p for p in passages if p.status == "complete"])
    remaining = len([p for p in passages if p.status in ["programme", "en_cours"]])
    
    return PassageSchedule(
        tontine_id=tontine_id,
        tontine_name=tontine.name,
        passages=passages,
        current_passage=current,
        next_passage=next_passage,
        completed_count=completed,
        remaining_count=remaining,
    )


@router.get(
    "/{passage_id}",
    response_model=PassageResponse,
    summary="Détails d'un passage",
)
async def get_passage(
    passage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les détails d'un passage.
    """
    passage = db.query(Passage).options(
        joinedload(Passage.member).joinedload(TontineMember.user)
    ).filter(Passage.id == passage_id).first()
    
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passage non trouvé",
        )
    
    permission = TontinePermission()
    await permission(passage.tontine_id, current_user, db)
    
    return passage


@router.put(
    "/{passage_id}",
    response_model=PassageResponse,
    summary="Modifier un passage",
)
async def update_passage(
    passage_id: int,
    passage_data: PassageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Modifie un passage (date, statut, notes).
    """
    passage = db.query(Passage).filter(Passage.id == passage_id).first()
    
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passage non trouvé",
        )
    
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(passage.tontine_id, current_user, db)
    
    update_data = passage_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(passage, field, value)
    
    passage.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(passage)
    
    logger.info(f"Passage {passage_id} modifié par {current_user.email}")
    
    return passage


@router.put(
    "/tontine/{tontine_id}/order",
    response_model=List[PassageResponse],
    summary="Modifier l'ordre des passages",
)
async def update_order(
    tontine_id: int,
    order_data: PassageOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Modifie l'ordre des passages pour une tontine.
    """
    permission = TontinePermission(roles=["president"])
    await permission(tontine_id, current_user, db)
    
    passages = db.query(Passage).filter(
        Passage.tontine_id == tontine_id
    ).all()
    
    if not passages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun passage trouvé pour cette tontine",
        )
    
    # Vérifier qu'aucun passage n'est déjà complété
    completed = [p for p in passages if p.status == "complete"]
    if completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de modifier l'ordre après des passages complétés",
        )
    
    # Mettre à jour les ordres
    passage_dict = {p.member_id: p for p in passages}
    
    for item in order_data.passages:
        member_id = item["member_id"]
        order_number = item["order_number"]
        
        if member_id in passage_dict:
            passage_dict[member_id].order_number = order_number
            passage_dict[member_id].updated_at = datetime.utcnow()
    
    db.commit()
    
    updated_passages = db.query(Passage).filter(
        Passage.tontine_id == tontine_id
    ).order_by(Passage.order_number).all()
    
    logger.info(f"Ordre de passage modifié pour tontine {tontine_id}")
    
    return updated_passages


@router.post(
    "/{passage_id}/start",
    response_model=PassageResponse,
    summary="Démarrer un passage",
)
async def start_passage(
    passage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Marque un passage comme en cours (c'est le tour de ce membre).
    """
    passage = db.query(Passage).filter(Passage.id == passage_id).first()
    
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passage non trouvé",
        )
    
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(passage.tontine_id, current_user, db)
    
    if passage.status != "programme":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le passage n'est pas programmé (statut: {passage.status})",
        )
    
    passage.status = "en_cours"
    passage.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(passage)
    
    logger.info(f"Passage {passage_id} démarré par {current_user.email}")
    
    # TODO: Envoyer notification au bénéficiaire
    
    return passage


@router.post(
    "/{passage_id}/payout",
    response_model=PassageResponse,
    summary="Effectuer le versement",
)
async def payout_passage(
    passage_id: int,
    payout_data: PassagePayout,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Enregistre le versement du pot au bénéficiaire.
    """
    passage = db.query(Passage).filter(Passage.id == passage_id).first()
    
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passage non trouvé",
        )
    
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(passage.tontine_id, current_user, db)
    
    if passage.status != "en_cours":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le passage n'est pas en cours",
        )
    
    # Enregistrer le versement
    passage.payout_method = payout_data.payout_method
    passage.payout_phone = payout_data.payout_phone
    passage.payout_reference = payout_data.payout_reference
    passage.amount_received = payout_data.amount
    passage.actual_date = datetime.utcnow()
    passage.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(passage)
    
    logger.info(
        f"Versement de {payout_data.amount} FCFA effectué pour passage {passage_id}"
    )
    
    # TODO: Envoyer notification de versement
    
    return passage


@router.post(
    "/{passage_id}/confirm",
    response_model=PassageResponse,
    summary="Confirmer la réception",
)
async def confirm_passage(
    passage_id: int,
    confirmation: PassageConfirmation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Le bénéficiaire confirme la réception du pot.
    """
    passage = db.query(Passage).options(
        joinedload(Passage.member)
    ).filter(Passage.id == passage_id).first()
    
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passage non trouvé",
        )
    
    # Vérifier que c'est bien le bénéficiaire
    if passage.member.user_id != current_user.id and current_user.role != "admin":
        permission = TontinePermission(roles=["president", "tresorier"])
        await permission(passage.tontine_id, current_user, db)
    
    passage.confirmed_by_member = True
    passage.confirmed_at = datetime.utcnow()
    passage.amount_received = confirmation.amount_received
    passage.status = "complete"
    
    if confirmation.notes:
        passage.notes = confirmation.notes
    
    passage.updated_at = datetime.utcnow()
    
    # Mettre à jour les stats du membre
    member = passage.member
    member.total_received = float(member.total_received) + float(confirmation.amount_received)
    
    db.commit()
    db.refresh(passage)
    
    logger.info(f"Passage {passage_id} confirmé par le bénéficiaire")
    
    return passage


@router.post(
    "/{passage_id}/postpone",
    response_model=PassageResponse,
    summary="Reporter un passage",
)
async def postpone_passage(
    passage_id: int,
    new_date: datetime,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Reporte un passage à une nouvelle date.
    """
    passage = db.query(Passage).filter(Passage.id == passage_id).first()
    
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passage non trouvé",
        )
    
    permission = TontinePermission(roles=["president"])
    await permission(passage.tontine_id, current_user, db)
    
    if passage.status == "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de reporter un passage complété",
        )
    
    passage.status = "reporte"
    passage.scheduled_date = new_date
    passage.postpone_reason = reason
    passage.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(passage)
    
    logger.info(f"Passage {passage_id} reporté au {new_date}")
    
    return passage

