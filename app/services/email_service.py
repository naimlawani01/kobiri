"""
Service d'envoi d'emails pour Kobiri.
Gère l'envoi des emails de notification, réinitialisation de mot de passe, etc.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import settings
from app.core.logging import logger


class EmailService:
    """Service pour l'envoi d'emails."""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_from = settings.EMAIL_FROM
    
    def _create_connection(self) -> smtplib.SMTP:
        """Crée une connexion SMTP."""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        if self.smtp_user and self.smtp_password:
            server.login(self.smtp_user, self.smtp_password)
        return server
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Envoie un email.
        
        Args:
            to_email: Adresse email du destinataire
            subject: Sujet de l'email
            html_content: Contenu HTML de l'email
            text_content: Contenu texte (fallback)
        
        Returns:
            True si l'envoi a réussi, False sinon
        """
        if not self.smtp_user or not self.smtp_password:
            logger.warning("Configuration SMTP manquante - Email non envoyé")
            logger.info(f"Email simulé vers {to_email}: {subject}")
            return True  # Retourner True pour ne pas bloquer en dev
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.APP_NAME} <{self.email_from}>"
            msg["To"] = to_email
            
            # Ajouter le contenu texte
            if text_content:
                part1 = MIMEText(text_content, "plain", "utf-8")
                msg.attach(part1)
            
            # Ajouter le contenu HTML
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part2)
            
            # Envoyer l'email
            with self._create_connection() as server:
                server.sendmail(self.email_from, to_email, msg.as_string())
            
            logger.info(f"Email envoyé à {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email à {to_email}: {e}")
            return False
    
    def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_code: str,
    ) -> bool:
        """
        Envoie un email de réinitialisation de mot de passe.
        
        Args:
            to_email: Email du destinataire
            user_name: Nom de l'utilisateur
            reset_code: Code de réinitialisation (6 chiffres)
        """
        subject = f"🔐 {settings.APP_NAME} - Réinitialisation de votre mot de passe"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #D4AF37 0%, #B8860B 100%); padding: 30px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 28px; }}
                .content {{ padding: 30px; }}
                .code-box {{ background: #f8f9fa; border: 2px dashed #D4AF37; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }}
                .code {{ font-size: 36px; font-weight: bold; color: #D4AF37; letter-spacing: 8px; font-family: monospace; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                p {{ color: #333; line-height: 1.6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 {settings.APP_NAME}</h1>
                </div>
                <div class="content">
                    <p>Bonjour <strong>{user_name}</strong>,</p>
                    <p>Vous avez demandé la réinitialisation de votre mot de passe. Voici votre code de vérification :</p>
                    
                    <div class="code-box">
                        <div class="code">{reset_code}</div>
                    </div>
                    
                    <p>Entrez ce code dans l'application pour créer un nouveau mot de passe.</p>
                    
                    <div class="warning">
                        ⏱️ <strong>Ce code expire dans 1 heure.</strong><br>
                        Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
                    </div>
                </div>
                <div class="footer">
                    <p>Cet email a été envoyé automatiquement par {settings.APP_NAME}.</p>
                    <p>© 2024 {settings.APP_NAME} - Tous droits réservés</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Bonjour {user_name},
        
        Vous avez demandé la réinitialisation de votre mot de passe.
        
        Votre code de vérification : {reset_code}
        
        Ce code expire dans 1 heure.
        
        Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
        
        L'équipe {settings.APP_NAME}
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
    ) -> bool:
        """Envoie un email de bienvenue après inscription."""
        subject = f"🎉 Bienvenue sur {settings.APP_NAME} !"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #D4AF37 0%, #B8860B 100%); padding: 30px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 28px; }}
                .content {{ padding: 30px; }}
                .feature {{ display: flex; align-items: center; margin: 15px 0; }}
                .feature-icon {{ font-size: 24px; margin-right: 15px; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                p {{ color: #333; line-height: 1.6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Bienvenue !</h1>
                </div>
                <div class="content">
                    <p>Bonjour <strong>{user_name}</strong>,</p>
                    <p>Nous sommes ravis de vous accueillir sur <strong>{settings.APP_NAME}</strong>, votre application de gestion de tontines !</p>
                    
                    <p>Avec {settings.APP_NAME}, vous pouvez :</p>
                    <div class="feature"><span class="feature-icon">👥</span> Créer et rejoindre des tontines</div>
                    <div class="feature"><span class="feature-icon">💰</span> Gérer vos cotisations facilement</div>
                    <div class="feature"><span class="feature-icon">📊</span> Suivre vos paiements en temps réel</div>
                    <div class="feature"><span class="feature-icon">🔔</span> Recevoir des rappels automatiques</div>
                    
                    <p>Commencez dès maintenant en créant votre première tontine !</p>
                </div>
                <div class="footer">
                    <p>L'équipe {settings.APP_NAME}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)


# Instance globale du service
email_service = EmailService()

