"""
Schémas Pydantic pour les notifications.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.notification import (
    NotificationType, 
    NotificationChannel, 
    NotificationStatus,
)


class NotificationBase(BaseModel):
    """Schéma de base pour une notification."""
    type: NotificationType = Field(..., description="Type de notification")
    channel: NotificationChannel = Field(
        default=NotificationChannel.IN_APP,
        description="Canal d'envoi"
    )
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)


class NotificationCreate(NotificationBase):
    """Schéma pour créer une notification."""
    user_id: int = Field(..., description="ID du destinataire")
    data: Optional[Dict[str, Any]] = Field(None, description="Données supplémentaires")
    tontine_id: Optional[int] = None
    session_id: Optional[int] = None
    payment_id: Optional[int] = None
    scheduled_at: Optional[datetime] = Field(
        None, 
        description="Date d'envoi programmé"
    )


class NotificationResponse(BaseModel):
    """Schéma de réponse pour une notification."""
    id: int
    user_id: int
    type: NotificationType
    channel: NotificationChannel
    status: NotificationStatus
    title: str
    message: str
    data: Optional[Dict[str, Any]]
    tontine_id: Optional[int]
    session_id: Optional[int]
    payment_id: Optional[int]
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    is_read: bool
    is_sent: bool
    provider_message_id: Optional[str]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schéma pour la liste des notifications."""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    pages: int


class NotificationMarkRead(BaseModel):
    """Schéma pour marquer des notifications comme lues."""
    notification_ids: List[int] = Field(
        ..., 
        min_length=1,
        description="IDs des notifications à marquer"
    )


class NotificationMarkAllRead(BaseModel):
    """Schéma pour marquer toutes les notifications comme lues."""
    before_date: Optional[datetime] = Field(
        None,
        description="Marquer uniquement les notifications avant cette date"
    )


class NotificationPreferences(BaseModel):
    """Préférences de notification d'un utilisateur."""
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    in_app_enabled: bool = True
    
    # Préférences par type
    rappel_cotisation: List[NotificationChannel] = [
        NotificationChannel.SMS,
        NotificationChannel.IN_APP,
    ]
    confirmation_paiement: List[NotificationChannel] = [
        NotificationChannel.SMS,
        NotificationChannel.IN_APP,
    ]
    alerte_retard: List[NotificationChannel] = [
        NotificationChannel.SMS,
        NotificationChannel.EMAIL,
        NotificationChannel.IN_APP,
    ]
    tour_passage: List[NotificationChannel] = [
        NotificationChannel.SMS,
        NotificationChannel.EMAIL,
        NotificationChannel.IN_APP,
    ]


class BulkNotificationCreate(BaseModel):
    """Schéma pour envoyer des notifications en masse."""
    user_ids: List[int] = Field(..., min_length=1)
    type: NotificationType
    channel: NotificationChannel = NotificationChannel.IN_APP
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    data: Optional[Dict[str, Any]] = None
    tontine_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None


class NotificationStats(BaseModel):
    """Statistiques des notifications."""
    total_sent: int
    total_delivered: int
    total_read: int
    total_failed: int
    delivery_rate: float
    read_rate: float
    by_channel: Dict[str, int]
    by_type: Dict[str, int]


class SendReminderRequest(BaseModel):
    """Requête pour envoyer un rappel de cotisation."""
    session_id: int = Field(..., description="ID de la session")
    user_ids: Optional[List[int]] = Field(
        None, 
        description="IDs des utilisateurs (tous si vide)"
    )
    channel: NotificationChannel = Field(
        default=NotificationChannel.SMS,
        description="Canal d'envoi"
    )
    custom_message: Optional[str] = Field(
        None,
        max_length=500,
        description="Message personnalisé"
    )

