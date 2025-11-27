"""
Configuration du système de logging pour Kobiri.
Utilise Loguru pour un logging structuré et détaillé.
"""

import sys
from pathlib import Path
from typing import Optional, Dict
from loguru import logger


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/kobiri.log",
    rotation: str = "10 MB",
    retention: str = "30 days",
) -> None:
    """
    Configure le système de logging de l'application.
    
    Args:
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Chemin du fichier de log
        rotation: Taille maximale avant rotation
        retention: Durée de rétention des logs
    """
    # Supprimer le handler par défaut
    logger.remove()
    
    # Format personnalisé pour les logs
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Format pour fichier (sans couleurs)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    
    # Handler pour la console avec couleurs
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # Créer le répertoire de logs si nécessaire
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handler pour fichier avec rotation
    logger.add(
        log_file,
        format=file_format,
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Thread-safe
    )
    
    # Fichier séparé pour les erreurs
    error_log = str(log_path.parent / "errors.log")
    logger.add(
        error_log,
        format=file_format,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )
    
    logger.info("Système de logging initialisé")
    logger.debug(f"Niveau de log: {log_level}")
    logger.debug(f"Fichier de log: {log_file}")


# Logger pour les requêtes HTTP
def log_request(
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
) -> None:
    """
    Log une requête HTTP avec ses détails.
    
    Args:
        method: Méthode HTTP (GET, POST, etc.)
        url: URL de la requête
        status_code: Code de statut HTTP
        duration_ms: Durée de la requête en millisecondes
        user_id: ID de l'utilisateur (optionnel)
    """
    logger.bind(
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
    ).info(
        f"{method} {url} - {status_code} ({duration_ms:.2f}ms)"
    )


def log_database_query(
    query: str,
    duration_ms: float,
    params: Optional[Dict] = None,
) -> None:
    """
    Log une requête SQL avec sa durée.
    
    Args:
        query: Requête SQL
        duration_ms: Durée d'exécution
        params: Paramètres de la requête
    """
    logger.bind(
        query=query[:200],  # Tronquer les longues requêtes
        duration_ms=duration_ms,
        params=params,
    ).debug(
        f"SQL Query ({duration_ms:.2f}ms): {query[:100]}..."
    )


def log_payment_event(
    event_type: str,
    payment_id: str,
    amount: float,
    status: str,
    operator: str,
    details: Optional[Dict] = None,
) -> None:
    """
    Log un événement de paiement.
    
    Args:
        event_type: Type d'événement (initiation, callback, validation)
        payment_id: ID du paiement
        amount: Montant
        status: Statut du paiement
        operator: Opérateur mobile money
        details: Détails supplémentaires
    """
    logger.bind(
        event_type=event_type,
        payment_id=payment_id,
        amount=amount,
        status=status,
        operator=operator,
        details=details,
    ).info(
        f"Payment {event_type}: {payment_id} - {amount} FCFA via {operator} - Status: {status}"
    )


def log_notification_sent(
    notification_type: str,
    recipient: str,
    channel: str,
    success: bool,
    message_preview: str = "",
) -> None:
    """
    Log l'envoi d'une notification.
    
    Args:
        notification_type: Type de notification (rappel, confirmation, alerte)
        recipient: Destinataire
        channel: Canal (SMS, email, push)
        success: Succès de l'envoi
        message_preview: Aperçu du message
    """
    level = "info" if success else "warning"
    getattr(logger, level)(
        f"Notification {notification_type} via {channel} to {recipient}: "
        f"{'Sent' if success else 'Failed'} - {message_preview[:50]}"
    )


__all__ = [
    "logger",
    "setup_logging",
    "log_request",
    "log_database_query",
    "log_payment_event",
    "log_notification_sent",
]

