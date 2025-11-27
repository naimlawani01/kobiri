"""
Routes pour la gestion des notifications.
"""

from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.core.logging import logger
from app.models.user import User, UserRole
from app.models.notification import (
    Notification, 
    NotificationType, 
    NotificationChannel,
    NotificationStatus,
)
from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkRead,
    NotificationMarkAllRead,
    BulkNotificationCreate,
    SendReminderRequest,
)
from app.api.deps import (
    get_current_active_user,
    require_admin,
    TontinePermission,
)


router = APIRouter()


@router.get(
    "/",
    response_model=NotificationListResponse,
    summary="Liste des notifications",
)
async def list_notifications(
    unread_only: bool = Query(False, description="Uniquement les non lues"),
    type_filter: Optional[NotificationType] = Query(None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Liste les notifications de l'utilisateur connecté.
    """
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(Notification.status != "lue")
    
    if type_filter:
        query = query.filter(Notification.type == type_filter)
    
    total = query.count()
    unread_count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.status != "lue",
    ).scalar()
    
    notifications = query.order_by(
        Notification.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return NotificationListResponse(
        items=notifications,
        total=total,
        unread_count=unread_count or 0,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get(
    "/unread-count",
    summary="Nombre de notifications non lues",
)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retourne le nombre de notifications non lues.
    """
    count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.status != "lue",
    ).scalar()
    
    return {"unread_count": count or 0}


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Détails d'une notification",
)
async def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Récupère les détails d'une notification.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification non trouvée",
        )
    
    if notification.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé",
        )
    
    return notification


@router.post(
    "/mark-read",
    status_code=status.HTTP_200_OK,
    summary="Marquer des notifications comme lues",
)
async def mark_as_read(
    request: NotificationMarkRead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Marque une ou plusieurs notifications comme lues.
    """
    notifications = db.query(Notification).filter(
        Notification.id.in_(request.notification_ids),
        Notification.user_id == current_user.id,
    ).all()
    
    if not notifications:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune notification trouvée",
        )
    
    count = 0
    for notif in notifications:
        if notif.status != "lue":
            notif.status = "lue"
            notif.read_at = datetime.utcnow()
            notif.updated_at = datetime.utcnow()
            count += 1
    
    db.commit()
    
    logger.debug(f"{count} notifications marquées comme lues pour {current_user.id}")
    
    return {"marked_count": count}


@router.post(
    "/mark-all-read",
    status_code=status.HTTP_200_OK,
    summary="Marquer toutes les notifications comme lues",
)
async def mark_all_as_read(
    request: NotificationMarkAllRead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Marque toutes les notifications comme lues.
    """
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.status != "lue",
    )
    
    if request.before_date:
        query = query.filter(Notification.created_at <= request.before_date)
    
    notifications = query.all()
    
    count = 0
    for notif in notifications:
        notif.status = "lue"
        notif.read_at = datetime.utcnow()
        notif.updated_at = datetime.utcnow()
        count += 1
    
    db.commit()
    
    logger.info(f"Toutes les notifications ({count}) marquées comme lues pour {current_user.id}")
    
    return {"marked_count": count}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une notification",
)
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Supprime une notification.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification non trouvée",
        )
    
    db.delete(notification)
    db.commit()
    
    logger.debug(f"Notification {notification_id} supprimée")


# ============== Routes admin pour l'envoi de notifications ==============

@router.post(
    "/send",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Envoyer une notification (admin)",
)
async def send_notification(
    notification_data: NotificationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Crée et envoie une notification à un utilisateur (admin uniquement).
    """
    # Vérifier que l'utilisateur existe
    user = db.query(User).filter(User.id == notification_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    
    notification = Notification(
        user_id=notification_data.user_id,
        type=notification_data.type,
        channel=notification_data.channel,
        title=notification_data.title,
        message=notification_data.message,
        data=notification_data.data,
        tontine_id=notification_data.tontine_id,
        session_id=notification_data.session_id,
        payment_id=notification_data.payment_id,
        scheduled_at=notification_data.scheduled_at,
        status="en_attente",
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    # Si pas de planification, envoyer immédiatement
    if not notification_data.scheduled_at:
        background_tasks.add_task(
            send_notification_task,
            notification.id,
        )
    
    logger.info(
        f"Notification créée pour {user.email}: {notification_data.title}"
    )
    
    return notification


@router.post(
    "/send-bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Envoyer des notifications en masse (admin)",
)
async def send_bulk_notifications(
    notification_data: BulkNotificationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Envoie des notifications à plusieurs utilisateurs.
    """
    # Vérifier que les utilisateurs existent
    users = db.query(User).filter(User.id.in_(notification_data.user_ids)).all()
    user_ids_found = {u.id for u in users}
    
    notifications_created = []
    
    for user_id in notification_data.user_ids:
        if user_id not in user_ids_found:
            continue
        
        notification = Notification(
            user_id=user_id,
            type=notification_data.type,
            channel=notification_data.channel,
            title=notification_data.title,
            message=notification_data.message,
            data=notification_data.data,
            tontine_id=notification_data.tontine_id,
            scheduled_at=notification_data.scheduled_at,
            status="en_attente",
        )
        
        db.add(notification)
        notifications_created.append(notification)
    
    db.commit()
    
    # Envoyer les notifications en background
    if not notification_data.scheduled_at:
        for notif in notifications_created:
            background_tasks.add_task(send_notification_task, notif.id)
    
    logger.info(
        f"{len(notifications_created)} notifications créées par {current_user.email}"
    )
    
    return {
        "created_count": len(notifications_created),
        "skipped_count": len(notification_data.user_ids) - len(notifications_created),
    }


@router.post(
    "/send-reminder",
    status_code=status.HTTP_200_OK,
    summary="Envoyer un rappel de cotisation",
)
async def send_reminder(
    request: SendReminderRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Envoie des rappels de cotisation aux membres d'une session.
    """
    from app.models.session import CotisationSession
    from app.models.tontine import TontineMember
    from app.models.payment import Payment, PaymentStatus
    
    session = db.query(CotisationSession).filter(
        CotisationSession.id == request.session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvée",
        )
    
    # Vérifier les permissions
    permission = TontinePermission(roles=["president", "tresorier"])
    await permission(session.tontine_id, current_user, db)
    
    # Trouver les membres qui n'ont pas encore payé
    paid_users = db.query(Payment.user_id).filter(
        Payment.session_id == session.id,
        Payment.status == "valide",
    ).subquery()
    
    query = db.query(TontineMember).filter(
        TontineMember.tontine_id == session.tontine_id,
        TontineMember.is_active == True,
        ~TontineMember.user_id.in_(paid_users),
    )
    
    if request.user_ids:
        query = query.filter(TontineMember.user_id.in_(request.user_ids))
    
    members = query.all()
    
    # Créer les notifications
    tontine = session.tontine
    notifications_count = 0
    
    for member in members:
        message = request.custom_message or (
            f"Rappel: Votre cotisation de {tontine.contribution_amount} {tontine.currency} "
            f"pour {tontine.name} est attendue avant le {session.due_date.strftime('%d/%m/%Y')}."
        )
        
        notification = Notification(
            user_id=member.user_id,
            type="rappel_cotisation",
            channel=request.channel,
            title=f"Rappel - {tontine.name}",
            message=message,
            data={
                "tontine_id": tontine.id,
                "session_id": session.id,
                "amount": str(tontine.contribution_amount),
                "due_date": session.due_date.isoformat(),
            },
            tontine_id=tontine.id,
            session_id=session.id,
            status="en_attente",
        )
        
        db.add(notification)
        notifications_count += 1
    
    db.commit()
    
    logger.info(
        f"{notifications_count} rappels envoyés pour la session {session.id} "
        f"par {current_user.email}"
    )
    
    return {
        "reminders_sent": notifications_count,
        "session_id": session.id,
    }


async def send_notification_task(notification_id: int):
    """
    Tâche d'envoi de notification en background.
    À implémenter avec les services SMS/Email.
    """
    from app.database import get_db_context
    
    with get_db_context() as db:
        notification = db.query(Notification).filter(
            Notification.id == notification_id
        ).first()
        
        if not notification:
            return
        
        try:
            # TODO: Implémenter l'envoi réel selon le canal
            # if notification.channel == NotificationChannel.SMS:
            #     send_sms(...)
            # elif notification.channel == NotificationChannel.EMAIL:
            #     send_email(...)
            
            # Pour l'instant, marquer comme envoyé
            notification.status = "envoyee"
            notification.sent_at = datetime.utcnow()
            notification.updated_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Notification {notification_id} envoyée")
            
        except Exception as e:
            notification.status = "echouee"
            notification.error_message = str(e)
            notification.retry_count += 1
            notification.updated_at = datetime.utcnow()
            
            db.commit()
            
            logger.error(f"Erreur envoi notification {notification_id}: {e}")

