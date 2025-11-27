"""
Service de gestion des notifications.
Gère l'envoi de SMS, emails et notifications push.
"""

import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from app.config import settings
from app.core.logging import logger, log_notification_sent
from app.models.notification import (
    Notification, 
    NotificationType, 
    NotificationChannel,
    NotificationStatus,
    NOTIFICATION_TEMPLATES,
)
from app.database import get_db_context


class NotificationProvider(ABC):
    """Interface abstraite pour les providers de notification."""
    
    @abstractmethod
    async def send(
        self,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Envoie une notification."""
        pass


class SMSProvider(NotificationProvider):
    """
    Provider SMS.
    Peut être adapté pour différents fournisseurs (Twilio, Orange SMS API, etc.)
    """
    
    def __init__(self):
        self.api_key = settings.SMS_API_KEY
        self.sender_id = settings.SMS_SENDER_ID
        # URL exemple pour un provider SMS générique
        self.base_url = "https://api.sms-provider.com/v1"
    
    async def send(
        self,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Envoie un SMS.
        
        Args:
            recipient: Numéro de téléphone
            message: Contenu du message (max 160 caractères par segment)
            subject: Non utilisé pour SMS
            
        Returns:
            Résultat de l'envoi
        """
        logger.info(f"Envoi SMS à {recipient[:6]}***")
        
        try:
            # En production, décommenter et adapter selon le provider
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         f"{self.base_url}/messages",
            #         headers={"Authorization": f"Bearer {self.api_key}"},
            #         json={
            #             "to": recipient,
            #             "from": self.sender_id,
            #             "text": message[:160],  # Limiter à 160 caractères
            #         },
            #     )
            #     if response.status_code in [200, 201]:
            #         data = response.json()
            #         return {
            #             "success": True,
            #             "message_id": data.get("id"),
            #         }
            #     return {"success": False, "error": response.text}
            
            # Mode simulation
            log_notification_sent(
                notification_type="sms",
                recipient=recipient,
                channel="SMS",
                success=True,
                message_preview=message[:50],
            )
            
            return {
                "success": True,
                "message_id": f"sim_{datetime.utcnow().timestamp()}",
                "simulated": True,
            }
            
        except Exception as e:
            logger.error(f"Erreur envoi SMS: {e}")
            log_notification_sent(
                notification_type="sms",
                recipient=recipient,
                channel="SMS",
                success=False,
                message_preview=str(e),
            )
            return {"success": False, "error": str(e)}


class EmailProvider(NotificationProvider):
    """
    Provider Email.
    Utilise SMTP ou peut être adapté pour SendGrid, Mailgun, etc.
    """
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAIL_FROM
    
    async def send(
        self,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Envoie un email.
        
        Args:
            recipient: Adresse email
            message: Corps du message (peut être HTML)
            subject: Sujet de l'email
            
        Returns:
            Résultat de l'envoi
        """
        logger.info(f"Envoi email à {recipient}")
        
        try:
            # En production, utiliser aiosmtplib ou un service email
            # import aiosmtplib
            # from email.mime.text import MIMEText
            # from email.mime.multipart import MIMEMultipart
            #
            # msg = MIMEMultipart()
            # msg["From"] = self.from_email
            # msg["To"] = recipient
            # msg["Subject"] = subject or "Notification Kobiri"
            # msg.attach(MIMEText(message, "html"))
            #
            # await aiosmtplib.send(
            #     msg,
            #     hostname=self.smtp_host,
            #     port=self.smtp_port,
            #     username=self.smtp_user,
            #     password=self.smtp_password,
            #     use_tls=True,
            # )
            
            # Mode simulation
            log_notification_sent(
                notification_type="email",
                recipient=recipient,
                channel="EMAIL",
                success=True,
                message_preview=subject or message[:50],
            )
            
            return {
                "success": True,
                "message_id": f"email_{datetime.utcnow().timestamp()}",
                "simulated": True,
            }
            
        except Exception as e:
            logger.error(f"Erreur envoi email: {e}")
            log_notification_sent(
                notification_type="email",
                recipient=recipient,
                channel="EMAIL",
                success=False,
                message_preview=str(e),
            )
            return {"success": False, "error": str(e)}


class PushProvider(NotificationProvider):
    """
    Provider Push Notifications.
    Peut être adapté pour Firebase Cloud Messaging, OneSignal, etc.
    """
    
    def __init__(self):
        self.fcm_api_key = None  # À configurer
        self.base_url = "https://fcm.googleapis.com/fcm/send"
    
    async def send(
        self,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Envoie une notification push.
        
        Args:
            recipient: Token FCM de l'appareil
            message: Corps de la notification
            subject: Titre de la notification
            
        Returns:
            Résultat de l'envoi
        """
        logger.info(f"Envoi push notification")
        
        try:
            # En production avec FCM:
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         self.base_url,
            #         headers={
            #             "Authorization": f"key={self.fcm_api_key}",
            #             "Content-Type": "application/json",
            #         },
            #         json={
            #             "to": recipient,
            #             "notification": {
            #                 "title": subject or "Kobiri",
            #                 "body": message,
            #             },
            #         },
            #     )
            
            # Mode simulation
            log_notification_sent(
                notification_type="push",
                recipient=recipient[:20] + "...",
                channel="PUSH",
                success=True,
                message_preview=message[:50],
            )
            
            return {
                "success": True,
                "message_id": f"push_{datetime.utcnow().timestamp()}",
                "simulated": True,
            }
            
        except Exception as e:
            logger.error(f"Erreur push notification: {e}")
            return {"success": False, "error": str(e)}


class NotificationService:
    """
    Service principal de gestion des notifications.
    Orchestre les différents providers selon le canal.
    """
    
    def __init__(self):
        self.providers = {
            "sms": SMSProvider(),
            "email": EmailProvider(),
            "push": PushProvider(),
        }
    
    def get_provider(self, channel: NotificationChannel) -> Optional[NotificationProvider]:
        """Retourne le provider pour un canal donné."""
        return self.providers.get(channel)
    
    async def send_notification(
        self,
        notification: Notification,
        recipient_contact: str,
    ) -> Dict[str, Any]:
        """
        Envoie une notification via le canal approprié.
        
        Args:
            notification: Instance de la notification
            recipient_contact: Contact du destinataire (email, téléphone, token)
            
        Returns:
            Résultat de l'envoi
        """
        # Pour les notifications in-app, pas besoin d'envoi externe
        if notification.channel == "in_app":
            return {"success": True, "in_app": True}
        
        provider = self.get_provider(notification.channel)
        
        if not provider:
            logger.warning(f"Canal non supporté: {notification.channel}")
            return {"success": False, "error": "Canal non supporté"}
        
        return await provider.send(
            recipient=recipient_contact,
            message=notification.message,
            subject=notification.title,
        )
    
    async def send_bulk_sms(
        self,
        recipients: List[str],
        message: str,
    ) -> Dict[str, Any]:
        """
        Envoie un SMS en masse.
        
        Args:
            recipients: Liste des numéros de téléphone
            message: Message à envoyer
            
        Returns:
            Résultat global de l'envoi
        """
        sms_provider = self.providers["sms"]
        
        results = {
            "total": len(recipients),
            "success": 0,
            "failed": 0,
            "errors": [],
        }
        
        for recipient in recipients:
            result = await sms_provider.send(recipient, message)
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "recipient": recipient,
                    "error": result.get("error"),
                })
        
        logger.info(
            f"Envoi SMS en masse: {results['success']}/{results['total']} réussis"
        )
        
        return results
    
    def create_notification_from_template(
        self,
        notification_type: NotificationType,
        user_id: int,
        channel: str = "in_app",
        tontine_id: Optional[int] = None,
        session_id: Optional[int] = None,
        **template_vars,
    ) -> Notification:
        """
        Crée une notification à partir d'un template prédéfini.
        
        Args:
            notification_type: Type de notification
            user_id: ID du destinataire
            channel: Canal d'envoi
            tontine_id: ID de la tontine associée
            session_id: ID de la session associée
            **template_vars: Variables pour le template
            
        Returns:
            Instance Notification (non sauvegardée)
        """
        template = NOTIFICATION_TEMPLATES.get(notification_type, {})
        
        title = template.get("title", str(notification_type.value))
        message_template = template.get("message", "")
        
        try:
            message = message_template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Variable manquante dans le template: {e}")
            message = message_template
        
        return Notification(
            user_id=user_id,
            type=notification_type,
            channel=channel,
            title=title,
            message=message,
            data=template_vars,
            tontine_id=tontine_id,
            session_id=session_id,
            status="en_attente",
        )
    
    async def send_payment_reminder(
        self,
        session_id: int,
        user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Envoie des rappels de paiement pour une session.
        
        Args:
            session_id: ID de la session
            user_ids: Liste des utilisateurs à notifier (tous si None)
            
        Returns:
            Résultat de l'envoi
        """
        from app.models.session import CotisationSession
        from app.models.tontine import Tontine, TontineMember
        from app.models.payment import Payment, PaymentStatus
        from app.models.user import User
        
        with get_db_context() as db:
            session = db.query(CotisationSession).filter(
                CotisationSession.id == session_id
            ).first()
            
            if not session:
                return {"success": False, "error": "Session non trouvée"}
            
            tontine = session.tontine
            
            # Trouver les membres qui n'ont pas encore payé
            paid_user_ids = {
                p.user_id for p in db.query(Payment).filter(
                    Payment.session_id == session_id,
                    Payment.status == "valide",
                ).all()
            }
            
            members_to_notify = db.query(TontineMember).join(User).filter(
                TontineMember.tontine_id == tontine.id,
                TontineMember.is_active == True,
                ~TontineMember.user_id.in_(paid_user_ids),
            )
            
            if user_ids:
                members_to_notify = members_to_notify.filter(
                    TontineMember.user_id.in_(user_ids)
                )
            
            members = members_to_notify.all()
            
            results = {
                "total": len(members),
                "success": 0,
                "failed": 0,
            }
            
            for member in members:
                user = member.user
                
                notification = self.create_notification_from_template(
                    notification_type="rappel_cotisation",
                    user_id=user.id,
                    channel="sms",
                    tontine_id=tontine.id,
                    session_id=session_id,
                    user_name=user.first_name,
                    amount=str(tontine.contribution_amount),
                    tontine_name=tontine.name,
                    due_date=session.due_date.strftime("%d/%m/%Y"),
                )
                
                db.add(notification)
                
                # Envoyer le SMS
                result = await self.send_notification(notification, user.phone)
                
                if result.get("success"):
                    notification.status = "envoyee"
                    notification.sent_at = datetime.utcnow()
                    results["success"] += 1
                else:
                    notification.status = "echouee"
                    notification.error_message = result.get("error")
                    results["failed"] += 1
            
            db.commit()
        
        logger.info(
            f"Rappels envoyés pour session {session_id}: "
            f"{results['success']}/{results['total']} réussis"
        )
        
        return results
    
    async def notify_payment_success(
        self,
        payment_id: int,
    ) -> Dict[str, Any]:
        """
        Notifie un utilisateur du succès de son paiement.
        """
        from app.models.payment import Payment
        from app.models.user import User
        
        with get_db_context() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            
            if not payment:
                return {"success": False, "error": "Paiement non trouvé"}
            
            user = db.query(User).filter(User.id == payment.user_id).first()
            tontine_name = payment.session.tontine.name if payment.session else "Tontine"
            
            notification = self.create_notification_from_template(
                notification_type="confirmation_paiement",
                user_id=user.id,
                channel=NotificationChannel.SMS,
                tontine_id=payment.tontine_id,
                session_id=payment.session_id,
                amount=str(payment.amount),
                tontine_name=tontine_name,
            )
            
            db.add(notification)
            
            result = await self.send_notification(notification, user.phone)
            
            if result.get("success"):
                notification.status = NotificationStatus.ENVOYEE
                notification.sent_at = datetime.utcnow()
            else:
                notification.status = NotificationStatus.ECHOUEE
                notification.error_message = result.get("error")
            
            db.commit()
        
        return result


# Instance singleton du service
notification_service = NotificationService()

