"""
Routes pour la gestion des paiements.
Supporte les paiements manuels et les callbacks des opérateurs mobile money.
"""

from typing import Any, List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.core.logging import logger, log_payment_event
from app.models.user import User, UserRole
from app.models.tontine import Tontine, TontineMember
from app.models.session import CotisationSession, SessionStatus
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.schemas.payment import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaymentListResponse,
    PaymentValidation,
    PaymentInitiate,
    PaymentCallback,
    OrangeMoneyCallback,
    MTNMoMoCallback,
    WaveCallback,
)
from app.api.deps import (
    get_current_active_user,
    TontinePermission,
)


router = APIRouter()


def generate_payment_reference() -> str:
    """Génère une référence unique pour le paiement."""
    return f"KOB-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un paiement manuel",
)
async def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Enregistre un paiement manuel (espèces ou preuve de paiement).
    Le paiement sera en attente de validation par un gestionnaire.
    """
    # Récupérer la session
    session = db.query(CotisationSession).options(
        joinedload(CotisationSession.tontine)
    ).filter(CotisationSession.id == payment_data.session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    if session.status != "en_cours":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La session n'est pas ouverte aux paiements",
        )
    
    # Vérifier que l'utilisateur est membre
    member = db.query(TontineMember).filter(
        TontineMember.tontine_id == session.tontine_id,
        TontineMember.user_id == current_user.id,
        TontineMember.is_active == True,
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas membre de cette tontine",
        )
    
    # Vérifier s'il n'y a pas déjà un paiement validé pour cette session
    existing = db.query(Payment).filter(
        Payment.session_id == session.id,
        Payment.user_id == current_user.id,
        Payment.status.in_(["valide", "en_cours"]),
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous avez déjà un paiement pour cette session",
        )
    
    # Vérifier si c'est en retard
    is_late = datetime.utcnow() > session.due_date
    penalty = float(session.tontine.penalty_amount) if is_late else 0
    
    # Créer le paiement
    payment = Payment(
        user_id=current_user.id,
        session_id=session.id,
        tontine_id=session.tontine_id,
        amount=payment_data.amount,
        currency=session.tontine.currency,
        method=payment_data.method,
        status="en_attente",
        operator_reference=generate_payment_reference(),
        phone_number=payment_data.phone_number,
        proof_url=payment_data.proof_url,
        proof_description=payment_data.proof_description,
        penalty_amount=penalty,
        is_late=is_late,
        notes=payment_data.notes,
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    log_payment_event(
        event_type="creation",
        payment_id=str(payment.id),
        amount=float(payment.amount),
        status=payment.status.value,
        operator=payment.method.value,
        details={"user_id": current_user.id, "session_id": session.id},
    )
    
    return payment


@router.post(
    "/initiate",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initier un paiement mobile money",
)
async def initiate_mobile_payment(
    payment_data: PaymentInitiate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Initie un paiement via mobile money (Orange Money, Wave, MTN MoMo, etc.).
    """
    session = db.query(CotisationSession).options(
        joinedload(CotisationSession.tontine)
    ).filter(CotisationSession.id == payment_data.session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    if session.status != "en_cours":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La session n'est pas ouverte",
        )
    
    # Vérifier l'appartenance
    member = db.query(TontineMember).filter(
        TontineMember.tontine_id == session.tontine_id,
        TontineMember.user_id == current_user.id,
        TontineMember.is_active == True,
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas membre de cette tontine",
        )
    
    # Calculer les montants
    amount = float(session.tontine.contribution_amount)
    is_late = datetime.utcnow() > session.due_date
    penalty = float(session.tontine.penalty_amount) if is_late else 0
    
    reference = generate_payment_reference()
    
    # Créer le paiement en attente
    payment = Payment(
        user_id=current_user.id,
        session_id=session.id,
        tontine_id=session.tontine_id,
        amount=amount,
        currency=session.tontine.currency,
        method=payment_data.method,
        status="en_cours",
        operator_reference=reference,
        phone_number=payment_data.phone_number,
        penalty_amount=penalty,
        is_late=is_late,
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    # TODO: Appeler l'API de l'opérateur mobile money
    # Ceci serait fait via le service de paiement
    
    log_payment_event(
        event_type="initiation",
        payment_id=str(payment.id),
        amount=amount + penalty,
        status=payment.status.value,
        operator=payment.method.value,
        details={"reference": reference, "phone": payment_data.phone_number},
    )
    
    return payment


@router.get(
    "/",
    response_model=PaymentListResponse,
    summary="Liste des paiements",
)
async def list_payments(
    session_id: Optional[int] = Query(None),
    tontine_id: Optional[int] = Query(None),
    status_filter: Optional[PaymentStatus] = Query(None, alias="status"),
    method: Optional[PaymentMethod] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste les paiements avec filtres.
    """
    query = db.query(Payment).options(joinedload(Payment.user))
    
    # Filtre par session ou tontine
    if session_id:
        query = query.filter(Payment.session_id == session_id)
    elif tontine_id:
        query = query.filter(Payment.tontine_id == tontine_id)
    else:
        # Par défaut, montrer uniquement les paiements de l'utilisateur
        if current_user.role != "admin":
            query = query.filter(Payment.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    if method:
        query = query.filter(Payment.method == method)
    
    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    
    return PaymentListResponse(
        items=payments,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Détails d'un paiement",
)
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les détails d'un paiement.
    """
    payment = db.query(Payment).options(
        joinedload(Payment.user)
    ).filter(Payment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paiement non trouvé",
        )
    
    # Vérifier les permissions
    if payment.user_id != current_user.id and current_user.role != "admin":
        # Vérifier si gestionnaire de la tontine
        membership = db.query(TontineMember).filter(
            TontineMember.tontine_id == payment.tontine_id,
            TontineMember.user_id == current_user.id,
            TontineMember.role.in_(["president", "tresorier"]),
        ).first()
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé",
            )
    
    return payment


@router.post(
    "/{payment_id}/validate",
    response_model=PaymentResponse,
    summary="Valider ou rejeter un paiement",
)
async def validate_payment(
    payment_id: int,
    validation: PaymentValidation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Valide ou rejette un paiement manuel.
    Réservé aux gestionnaires de la tontine (président/trésorier).
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paiement non trouvé",
        )
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(payment.tontine_id, current_user, db)
    
    if payment.status != "en_attente":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de valider un paiement avec le statut {payment.status}",
        )
    
    if validation.action == "approve":
        payment.status = "valide"
        payment.validated_by_id = current_user.id
        payment.validated_at = datetime.utcnow()
        payment.completed_at = datetime.utcnow()
        
        # Mettre à jour le montant collecté de la session
        session = db.query(CotisationSession).filter(
            CotisationSession.id == payment.session_id
        ).first()
        if session:
            session.collected_amount = float(session.collected_amount) + float(payment.amount)
        
        # Mettre à jour les stats du membre
        member = db.query(TontineMember).filter(
            TontineMember.tontine_id == payment.tontine_id,
            TontineMember.user_id == payment.user_id,
        ).first()
        if member:
            member.total_contributions = float(member.total_contributions) + float(payment.amount)
        
        log_payment_event(
            event_type="validation",
            payment_id=str(payment.id),
            amount=float(payment.amount),
            status="approved",
            operator=payment.method.value,
            details={"validated_by": current_user.id},
        )
        
    else:  # reject
        payment.status = "echoue"
        payment.rejection_reason = validation.rejection_reason
        payment.validated_by_id = current_user.id
        payment.validated_at = datetime.utcnow()
        
        log_payment_event(
            event_type="rejection",
            payment_id=str(payment.id),
            amount=float(payment.amount),
            status="rejected",
            operator=payment.method.value,
            details={"reason": validation.rejection_reason},
        )
    
    payment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(payment)
    
    return payment


# ============== Callbacks des opérateurs ==============

@router.post(
    "/callback/orange",
    status_code=status.HTTP_200_OK,
    summary="Callback Orange Money",
)
async def orange_money_callback(
    callback_data: OrangeMoneyCallback,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    """
    Reçoit les callbacks d'Orange Money.
    """
    logger.info(f"Callback Orange Money reçu: {callback_data.order_id}")
    
    payment = db.query(Payment).filter(
        Payment.operator_reference == callback_data.order_id
    ).first()
    
    if not payment:
        logger.warning(f"Paiement non trouvé pour référence: {callback_data.order_id}")
        return {"status": "error", "message": "Payment not found"}
    
    # Mapper les statuts Orange Money
    status_mapping = {
        "SUCCESS": "valide",
        "FAILED": "echoue",
        "PENDING": "en_cours",
        "CANCELLED": "annule",
    }
    
    new_status = status_mapping.get(callback_data.txnstatus, "en_cours")
    
    # Mettre à jour le paiement
    payment.status = new_status
    payment.operator_transaction_id = callback_data.txnid
    payment.operator_callback_data = callback_data.model_dump()
    payment.updated_at = datetime.utcnow()
    
    if new_status == "valide":
        payment.completed_at = datetime.utcnow()
        
        # Mettre à jour la session
        session = db.query(CotisationSession).filter(
            CotisationSession.id == payment.session_id
        ).first()
        if session:
            session.collected_amount = float(session.collected_amount) + float(payment.amount)
        
        # Mettre à jour les stats du membre
        member = db.query(TontineMember).filter(
            TontineMember.tontine_id == payment.tontine_id,
            TontineMember.user_id == payment.user_id,
        ).first()
        if member:
            member.total_contributions = float(member.total_contributions) + float(payment.amount)
    
    db.commit()
    
    log_payment_event(
        event_type="callback",
        payment_id=str(payment.id),
        amount=float(payment.amount),
        status=new_status.value,
        operator="orange_money",
        details={"txn_id": callback_data.txnid},
    )
    
    # TODO: Envoyer notification à l'utilisateur
    
    return {"status": "ok"}


@router.post(
    "/callback/mtn",
    status_code=status.HTTP_200_OK,
    summary="Callback MTN MoMo",
)
async def mtn_momo_callback(
    callback_data: MTNMoMoCallback,
    db: Session = Depends(get_db),
) -> Any:
    """
    Reçoit les callbacks de MTN Mobile Money.
    """
    logger.info(f"Callback MTN MoMo reçu: {callback_data.externalId}")
    
    payment = db.query(Payment).filter(
        Payment.operator_reference == callback_data.externalId
    ).first()
    
    if not payment:
        return {"status": "error", "message": "Payment not found"}
    
    status_mapping = {
        "SUCCESSFUL": "valide",
        "FAILED": "echoue",
        "PENDING": "en_cours",
    }
    
    new_status = status_mapping.get(callback_data.status, "en_cours")
    
    payment.status = new_status
    payment.operator_transaction_id = callback_data.financialTransactionId
    payment.operator_callback_data = callback_data.model_dump()
    payment.updated_at = datetime.utcnow()
    
    if new_status == "valide":
        payment.completed_at = datetime.utcnow()
        session = db.query(CotisationSession).filter(
            CotisationSession.id == payment.session_id
        ).first()
        if session:
            session.collected_amount = float(session.collected_amount) + float(payment.amount)
    
    db.commit()
    
    log_payment_event(
        event_type="callback",
        payment_id=str(payment.id),
        amount=float(payment.amount),
        status=new_status.value,
        operator="mtn_momo",
    )
    
    return {"status": "ok"}


@router.post(
    "/callback/wave",
    status_code=status.HTTP_200_OK,
    summary="Callback Wave",
)
async def wave_callback(
    callback_data: WaveCallback,
    db: Session = Depends(get_db),
) -> Any:
    """
    Reçoit les callbacks de Wave.
    """
    logger.info(f"Callback Wave reçu: {callback_data.client_reference}")
    
    payment = db.query(Payment).filter(
        Payment.operator_reference == callback_data.client_reference
    ).first()
    
    if not payment:
        return {"status": "error", "message": "Payment not found"}
    
    status_mapping = {
        "succeeded": "valide",
        "failed": "echoue",
        "pending": "en_cours",
        "cancelled": "annule",
    }
    
    new_status = status_mapping.get(callback_data.checkout_status, "en_cours")
    
    payment.status = new_status
    payment.operator_transaction_id = callback_data.id
    payment.operator_callback_data = callback_data.model_dump()
    payment.updated_at = datetime.utcnow()
    
    if new_status == "valide":
        payment.completed_at = datetime.utcnow()
        session = db.query(CotisationSession).filter(
            CotisationSession.id == payment.session_id
        ).first()
        if session:
            session.collected_amount = float(session.collected_amount) + float(payment.amount)
    
    db.commit()
    
    log_payment_event(
        event_type="callback",
        payment_id=str(payment.id),
        amount=float(payment.amount),
        status=new_status.value,
        operator="wave",
    )
    
    return {"status": "ok"}


@router.get(
    "/my",
    response_model=List[PaymentResponse],
    summary="Mes paiements",
)
async def my_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste tous les paiements de l'utilisateur connecté.
    """
    payments = db.query(Payment).filter(
        Payment.user_id == current_user.id
    ).order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    
    return payments

