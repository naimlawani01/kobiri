"""
Modèle Notification - Système de notifications.
Gère les rappels, confirmations et alertes envoyés aux utilisateurs.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Index, JSON,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.database import Base


class NotificationType(str, enum.Enum):
    """Types de notifications."""
    RAPPEL_COTISATION = "rappel_cotisation"       # Rappel de paiement
    CONFIRMATION_PAIEMENT = "confirmation_paiement"  # Paiement reçu
    ALERTE_RETARD = "alerte_retard"               # Retard de paiement
    TOUR_PASSAGE = "tour_passage"                 # C'est votre tour
    NOUVEAU_MEMBRE = "nouveau_membre"             # Nouveau membre dans la tontine
    MEMBRE_DEPART = "membre_depart"               # Départ d'un membre
    SESSION_OUVERTE = "session_ouverte"           # Nouvelle session de cotisation
    SESSION_TERMINEE = "session_terminee"         # Session terminée
    PAIEMENT_RECU = "paiement_recu"              # Vous avez reçu le pot
    PENALITE = "penalite"                         # Pénalité appliquée
    INFORMATION = "information"                    # Information générale
    SYSTEME = "systeme"                           # Notification système


class NotificationChannel(str, enum.Enum):
    """Canaux d'envoi des notifications."""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"                    # Notification push mobile
    IN_APP = "in_app"                # Notification dans l'application


class NotificationStatus(str, enum.Enum):
    """Statuts d'une notification."""
    EN_ATTENTE = "en_attente"        # Notification créée, pas encore envoyée
    ENVOYEE = "envoyee"              # Notification envoyée
    DELIVREE = "delivree"            # Notification délivrée (confirmé par le provider)
    LUE = "lue"                      # Notification lue par l'utilisateur
    ECHOUEE = "echouee"              # Échec d'envoi
    ANNULEE = "annulee"              # Notification annulée


class Notification(Base):
    """
    Modèle représentant une notification.
    
    Gère l'envoi de rappels, confirmations et alertes via
    différents canaux (SMS, email, push, in-app).
    
    Attributes:
        id: Identifiant unique
        user_id: ID de l'utilisateur destinataire
        type: Type de notification
        channel: Canal d'envoi
        status: Statut de la notification
        title: Titre court
        message: Message complet
        data: Données supplémentaires (JSON)
        scheduled_at: Date d'envoi programmé
        sent_at: Date d'envoi effectif
        read_at: Date de lecture
    """
    
    __tablename__ = "notifications"
    
    # Identifiant
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Destinataire
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Type et canal
    type = Column(
        PgEnum('rappel_cotisation', 'confirmation_paiement', 'alerte_retard', 'tour_passage', 
               'nouveau_membre', 'membre_depart', 'session_ouverte', 'session_terminee',
               'paiement_recu', 'penalite', 'information', 'systeme', name='notificationtype', create_type=False),
        nullable=False
    )
    channel = Column(
        PgEnum('sms', 'email', 'push', 'in_app', name='notificationchannel', create_type=False),
        default='in_app',
        nullable=False
    )
    
    # Statut
    status = Column(
        PgEnum('en_attente', 'envoyee', 'delivree', 'lue', 'echouee', 'annulee', name='notificationstatus', create_type=False),
        default='en_attente',
        nullable=False
    )
    
    # Contenu
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    # Données supplémentaires (ex: ID tontine, montant, etc.)
    data = Column(JSON, nullable=True)
    
    # Références optionnelles pour faciliter le suivi
    tontine_id = Column(Integer, ForeignKey("tontines.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("cotisation_sessions.id"), nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    
    # Planification
    scheduled_at = Column(DateTime, nullable=True)
    
    # Timestamps d'envoi
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    
    # Informations de delivery
    provider_message_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    user = relationship("User", back_populates="notifications")
    
    # Index
    __table_args__ = (
        Index("idx_notification_user", "user_id"),
        Index("idx_notification_type", "type"),
        Index("idx_notification_status", "status"),
        Index("idx_notification_channel", "channel"),
        Index("idx_notification_scheduled", "scheduled_at"),
        Index("idx_notification_user_unread", "user_id", "status"),
        Index("idx_notification_tontine", "tontine_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user={self.user_id}, type={self.type}, status={self.status})>"
    
    @property
    def is_read(self) -> bool:
        """Vérifie si la notification a été lue."""
        return self.status == "lue" or self.read_at is not None
    
    @property
    def is_sent(self) -> bool:
        """Vérifie si la notification a été envoyée."""
        return self.status in ["envoyee", "delivree", "lue"]
    
    @property
    def can_retry(self) -> bool:
        """Vérifie si l'envoi peut être réessayé."""
        return self.status == "echouee" and self.retry_count < 3


# Templates de notifications prédéfinis
NOTIFICATION_TEMPLATES = {
    NotificationType.RAPPEL_COTISATION: {
        "title": "Rappel de cotisation",
        "message": "Bonjour {user_name}, n'oubliez pas votre cotisation de {amount} FCFA pour la tontine {tontine_name}. Date limite: {due_date}.",
    },
    NotificationType.CONFIRMATION_PAIEMENT: {
        "title": "Paiement confirmé",
        "message": "Votre paiement de {amount} FCFA pour la tontine {tontine_name} a été confirmé. Merci!",
    },
    NotificationType.ALERTE_RETARD: {
        "title": "Retard de paiement",
        "message": "Attention {user_name}, votre cotisation pour {tontine_name} est en retard. Pénalité applicable: {penalty} FCFA.",
    },
    NotificationType.TOUR_PASSAGE: {
        "title": "C'est votre tour!",
        "message": "Félicitations {user_name}! C'est votre tour de recevoir le pot de la tontine {tontine_name}. Montant prévu: {amount} FCFA.",
    },
    NotificationType.NOUVEAU_MEMBRE: {
        "title": "Nouveau membre",
        "message": "{new_member_name} a rejoint la tontine {tontine_name}. Bienvenue!",
    },
    NotificationType.SESSION_OUVERTE: {
        "title": "Nouvelle session de cotisation",
        "message": "La session #{session_number} de la tontine {tontine_name} est ouverte. Cotisation: {amount} FCFA avant le {due_date}.",
    },
    NotificationType.SESSION_TERMINEE: {
        "title": "Session terminée",
        "message": "La session #{session_number} de {tontine_name} est terminée. Montant collecté: {collected_amount} FCFA.",
    },
    NotificationType.PAIEMENT_RECU: {
        "title": "Pot reçu!",
        "message": "Vous avez reçu {amount} FCFA de la tontine {tontine_name}. Vérifiez votre compte.",
    },
    NotificationType.PENALITE: {
        "title": "Pénalité appliquée",
        "message": "Une pénalité de {penalty} FCFA a été appliquée pour retard sur la tontine {tontine_name}.",
    },
}


def create_notification_from_template(
    notification_type: NotificationType,
    user_id: int,
    channel: NotificationChannel = NotificationChannel.IN_APP,
    **kwargs
) -> dict:
    """
    Crée les données d'une notification à partir d'un template.
    
    Args:
        notification_type: Type de notification
        user_id: ID du destinataire
        channel: Canal d'envoi
        **kwargs: Variables pour le template
        
    Returns:
        Dictionnaire avec les données de la notification
    """
    template = NOTIFICATION_TEMPLATES.get(notification_type, {})
    
    title = template.get("title", "Notification")
    message = template.get("message", "").format(**kwargs)
    
    return {
        "user_id": user_id,
        "type": notification_type,
        "channel": channel,
        "title": title,
        "message": message,
        "data": kwargs,
    }

