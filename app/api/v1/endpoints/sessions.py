"""
Routes CRUD pour les sessions de cotisation.
"""

from typing import Any, List, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.core.logging import logger
from app.models.user import User, UserRole
from app.models.tontine import Tontine, TontineMember
from app.models.session import CotisationSession, SessionStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.session import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionListResponse,
    SessionStats,
    OpenSessionRequest,
    CloseSessionRequest,
)
from app.api.deps import (
    get_current_active_user,
    TontinePermission,
)


router = APIRouter()


@router.post(
    "/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une session de cotisation",
)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Crée une nouvelle session de cotisation pour une tontine.
    """
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(session_data.tontine_id, current_user, db)
    
    tontine = db.query(Tontine).options(
        joinedload(Tontine.members)
    ).filter(Tontine.id == session_data.tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    # Calculer le numéro de session
    last_session = db.query(CotisationSession).filter(
        CotisationSession.tontine_id == session_data.tontine_id
    ).order_by(CotisationSession.session_number.desc()).first()
    
    session_number = (last_session.session_number + 1) if last_session else 1
    
    # Calculer le montant attendu
    active_members = len([m for m in tontine.members if m.is_active])
    expected_amount = float(tontine.contribution_amount) * active_members
    
    # Créer la session
    session = CotisationSession(
        tontine_id=session_data.tontine_id,
        session_number=session_number,
        scheduled_date=session_data.scheduled_date,
        due_date=session_data.due_date,
        expected_amount=expected_amount,
        beneficiary_id=session_data.beneficiary_id,
        notes=session_data.notes,
        status="programmee",
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    logger.info(
        f"Session #{session_number} créée pour tontine {session_data.tontine_id} "
        f"par {current_user.email}"
    )
    
    return session


@router.get(
    "/tontine/{tontine_id}",
    response_model=SessionListResponse,
    summary="Liste des sessions d'une tontine",
)
async def list_sessions(
    tontine_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[SessionStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste les sessions de cotisation d'une tontine.
    """
    # Vérifier l'accès
    permission = TontinePermission()
    await permission(tontine_id, current_user, db)
    
    query = db.query(CotisationSession).filter(
        CotisationSession.tontine_id == tontine_id
    )
    
    if status_filter:
        query = query.filter(CotisationSession.status == status_filter)
    
    total = query.count()
    sessions = query.order_by(
        CotisationSession.session_number.desc()
    ).offset(skip).limit(limit).all()
    
    return SessionListResponse(
        items=sessions,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Détails d'une session",
)
async def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les détails d'une session de cotisation.
    """
    session = db.query(CotisationSession).options(
        joinedload(CotisationSession.payments)
    ).filter(CotisationSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier l'accès
    permission = TontinePermission()
    await permission(session.tontine_id, current_user, db)
    
    # Enrichir avec le nom du bénéficiaire
    beneficiary_name = None
    if session.beneficiary_id:
        beneficiary = db.query(User).filter(User.id == session.beneficiary_id).first()
        if beneficiary:
            beneficiary_name = beneficiary.full_name
    
    response = SessionResponse.model_validate(session)
    response.beneficiary_name = beneficiary_name
    
    return response


@router.put(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Modifier une session",
)
async def update_session(
    session_id: int,
    session_data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Met à jour une session de cotisation.
    """
    session = db.query(CotisationSession).filter(
        CotisationSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(session.tontine_id, current_user, db)
    
    update_data = session_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)
    
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    logger.info(f"Session {session_id} mise à jour par {current_user.email}")
    
    return session


@router.post(
    "/{session_id}/open",
    response_model=SessionResponse,
    summary="Ouvrir une session",
)
async def open_session(
    session_id: int,
    request: OpenSessionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Ouvre une session pour la collecte des cotisations.
    """
    session = db.query(CotisationSession).filter(
        CotisationSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(session.tontine_id, current_user, db)
    
    if session.status != "programmee":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible d'ouvrir une session avec le statut {session.status}",
        )
    
    session.status = "en_cours"
    session.opened_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    logger.info(f"Session {session_id} ouverte par {current_user.email}")
    
    # Envoyer les notifications si demandé
    if request.send_notifications:
        # TODO: Implémenter l'envoi de notifications
        pass
    
    return session


@router.post(
    "/{session_id}/close",
    response_model=SessionResponse,
    summary="Fermer une session",
)
async def close_session(
    session_id: int,
    request: CloseSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Ferme une session de cotisation.
    """
    session = db.query(CotisationSession).options(
        joinedload(CotisationSession.payments)
    ).filter(CotisationSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(session.tontine_id, current_user, db)
    
    if session.status != "en_cours":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La session n'est pas en cours",
        )
    
    # Vérifier si tous les paiements sont reçus
    if not session.is_complete and not request.force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session incomplète ({session.collection_percentage:.1f}%). "
                   "Utilisez force=true pour fermer quand même.",
        )
    
    session.status = "terminee"
    session.closed_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    if request.notes:
        session.notes = request.notes
    
    db.commit()
    db.refresh(session)
    
    logger.info(f"Session {session_id} fermée par {current_user.email}")
    
    return session


@router.get(
    "/{session_id}/stats",
    response_model=SessionStats,
    summary="Statistiques d'une session",
)
async def get_session_stats(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les statistiques détaillées d'une session.
    """
    session = db.query(CotisationSession).options(
        joinedload(CotisationSession.payments).joinedload(Payment.user),
        joinedload(CotisationSession.tontine).joinedload(Tontine.members),
    ).filter(CotisationSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission()
    await permission(session.tontine_id, current_user, db)
    
    # Calculer les statistiques
    active_members = {m.user_id for m in session.tontine.members if m.is_active}
    paid_users = {
        p.user_id for p in session.payments 
        if p.status == "valide"
    }
    pending_users = active_members - paid_users
    
    # Paiements en retard
    late_payments = len([
        p for p in session.payments 
        if p.is_late and p.status == PaymentStatus.VALIDE
    ])
    
    # Pénalités collectées
    penalties = sum(
        float(p.penalty_amount) for p in session.payments 
        if p.status == "valide"
    )
    
    # Membres en attente
    pending_members = []
    for user_id in pending_users:
        member = next(
            (m for m in session.tontine.members if m.user_id == user_id), 
            None
        )
        if member and member.user:
            pending_members.append({
                "user_id": user_id,
                "name": member.user.full_name,
                "phone": member.user.phone,
            })
    
    return SessionStats(
        session_id=session.id,
        total_expected_payments=len(active_members),
        total_received_payments=len(paid_users),
        missing_payments=len(pending_users),
        total_amount_expected=session.expected_amount,
        total_amount_collected=session.collected_amount,
        collection_rate=session.collection_percentage,
        late_payments=late_payments,
        penalties_collected=penalties,
        pending_members=pending_members,
    )


@router.post(
    "/tontine/{tontine_id}/generate",
    response_model=List[SessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Générer automatiquement les sessions",
)
async def generate_sessions(
    tontine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Génère automatiquement toutes les sessions pour une tontine
    selon la fréquence et le nombre de membres actifs.
    Chaque membre aura une session où il sera bénéficiaire.
    """
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(tontine_id, current_user, db)
    
    tontine = db.query(Tontine).options(
        joinedload(Tontine.members).joinedload(TontineMember.user)
    ).filter(Tontine.id == tontine_id).first()
    
    if not tontine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tontine non trouvée",
        )
    
    # Vérifier qu'il n'y a pas déjà des sessions
    existing = db.query(CotisationSession).filter(
        CotisationSession.tontine_id == tontine_id
    ).count()
    
    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cette tontine a déjà {existing} session(s). Supprimez-les d'abord.",
        )
    
    # Récupérer les membres actifs triés par ordre de passage
    active_members = sorted(
        [m for m in tontine.members if m.is_active],
        key=lambda m: m.order_position or 999
    )
    
    if len(active_members) < tontine.min_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Il faut au moins {tontine.min_members} membres actifs pour générer les sessions.",
        )
    
    # Calculer l'intervalle entre les sessions selon la fréquence
    frequency_deltas = {
        "quotidien": timedelta(days=1),
        "hebdomadaire": timedelta(weeks=1),
        "bimensuel": timedelta(weeks=2),
        "mensuel": relativedelta(months=1),
        "trimestriel": relativedelta(months=3),
    }
    
    delta = frequency_deltas.get(tontine.frequency, relativedelta(months=1))
    expected_amount = float(tontine.contribution_amount) * len(active_members)
    
    sessions = []
    current_date = tontine.start_date
    
    for i, member in enumerate(active_members):
        session = CotisationSession(
            tontine_id=tontine_id,
            session_number=i + 1,
            scheduled_date=current_date,
            due_date=current_date + timedelta(days=tontine.grace_period_days),
            expected_amount=expected_amount,
            beneficiary_id=member.user_id,
            status="programmee",
            notes=f"Bénéficiaire: {member.user.full_name if member.user else 'Membre'}",
        )
        db.add(session)
        sessions.append(session)
        
        # Avancer à la prochaine date
        if isinstance(delta, timedelta):
            current_date = current_date + delta
        else:
            current_date = current_date + delta
    
    db.commit()
    
    # Rafraîchir toutes les sessions
    for s in sessions:
        db.refresh(s)
    
    logger.info(
        f"{len(sessions)} sessions générées pour la tontine {tontine_id} "
        f"par {current_user.email}"
    )
    
    return sessions


@router.get(
    "/{session_id}/payments-status",
    summary="Statut des paiements par membre",
)
async def get_session_payment_status(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère le statut de paiement de chaque membre pour une session.
    Indique qui a payé, qui n'a pas payé, et les montants.
    """
    session = db.query(CotisationSession).filter(
        CotisationSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission()
    await permission(session.tontine_id, current_user, db)
    
    # Récupérer la tontine avec les membres
    tontine = db.query(Tontine).options(
        joinedload(Tontine.members).joinedload(TontineMember.user)
    ).filter(Tontine.id == session.tontine_id).first()
    
    # Récupérer les paiements de la session
    payments = db.query(Payment).filter(
        Payment.session_id == session_id
    ).all()
    
    # Créer un dict des paiements par user_id
    payments_by_user = {p.user_id: p for p in payments}
    
    # Construire la liste de statut pour chaque membre
    members_status = []
    for member in tontine.members:
        if not member.is_active:
            continue
            
        payment = payments_by_user.get(member.user_id)
        
        member_status = {
            "user_id": member.user_id,
            "member_id": member.id,
            "name": member.user.full_name if member.user else "Membre",
            "phone": member.user.phone if member.user else None,
            "email": member.user.email if member.user else None,
            "order_position": member.order_position,
            "is_beneficiary": member.user_id == session.beneficiary_id,
            "has_paid": payment is not None and payment.status == "valide",
            "payment_status": payment.status if payment else None,
            "payment_amount": float(payment.amount) if payment else None,
            "payment_date": payment.created_at.isoformat() if payment else None,
            "payment_method": payment.method if payment else None,
            "is_late": payment.is_late if payment else False,
            "expected_amount": float(tontine.contribution_amount),
        }
        members_status.append(member_status)
    
    # Trier par ordre de passage
    members_status.sort(key=lambda x: x["order_position"] or 999)
    
    # Résumé
    paid_count = len([m for m in members_status if m["has_paid"]])
    total_count = len(members_status)
    
    return {
        "session_id": session.id,
        "session_number": session.session_number,
        "status": session.status,
        "scheduled_date": session.scheduled_date.isoformat(),
        "beneficiary_id": session.beneficiary_id,
        "beneficiary_name": next(
            (m["name"] for m in members_status if m["is_beneficiary"]), 
            None
        ),
        "expected_amount": float(session.expected_amount),
        "collected_amount": float(session.collected_amount),
        "progress_percent": (session.collected_amount / session.expected_amount * 100) if session.expected_amount > 0 else 0,
        "paid_count": paid_count,
        "pending_count": total_count - paid_count,
        "total_members": total_count,
        "members": members_status,
    }


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Annuler une session",
)
async def cancel_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Annule une session programmée.
    """
    session = db.query(CotisationSession).filter(
        CotisationSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president"])
    await permission(session.tontine_id, current_user, db)
    
    if session.status not in ["programmee", "en_attente"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les sessions programmées ou en attente peuvent être annulées",
        )
    
    session.status = "annulee"
    session.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Session {session_id} annulée par {current_user.email}")

