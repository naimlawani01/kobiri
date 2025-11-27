"""
Configuration de la base de données PostgreSQL avec SQLAlchemy.
Inclut la gestion des sessions et le modèle de base.
"""

from contextlib import contextmanager
from typing import Generator
import time

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.config import settings
from app.core.logging import logger, log_database_query


# Configuration du moteur SQLAlchemy avec pool de connexions optimisé
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,  # Nombre de connexions permanentes
    max_overflow=20,  # Connexions supplémentaires temporaires
    pool_timeout=30,  # Timeout pour obtenir une connexion
    pool_recycle=1800,  # Recycler les connexions après 30 minutes
    pool_pre_ping=True,  # Vérifier la connexion avant utilisation
    echo=settings.DEBUG,  # Afficher les requêtes SQL en mode debug
)

# Factory de sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Classe de base pour tous les modèles
Base = declarative_base()


# Event listener pour logger les requêtes SQL avec leur durée
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Enregistre le temps de début de la requête."""
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Calcule et log la durée de la requête."""
    total_time = time.time() - conn.info["query_start_time"].pop(-1)
    duration_ms = total_time * 1000
    
    # Logger uniquement si la requête prend plus de 10ms ou en mode debug
    if duration_ms > 10 or settings.DEBUG:
        log_database_query(
            query=statement,
            duration_ms=duration_ms,
            params=parameters if isinstance(parameters, dict) else None,
        )


def get_db() -> Generator[Session, None, None]:
    """
    Générateur de session de base de données pour l'injection de dépendances.
    
    Yields:
        Session SQLAlchemy active
        
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        logger.debug("Session de base de données ouverte")
        yield db
    except Exception as e:
        logger.error(f"Erreur lors de l'utilisation de la session: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("Session de base de données fermée")


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager pour utilisation hors FastAPI.
    
    Usage:
        with get_db_context() as db:
            users = db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Erreur de transaction: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialise la base de données en créant toutes les tables.
    À utiliser uniquement en développement ou pour les tests.
    En production, utiliser Alembic pour les migrations.
    """
    logger.info("Initialisation de la base de données...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées avec succès")


def check_db_connection() -> bool:
    """
    Vérifie que la connexion à la base de données fonctionne.
    
    Returns:
        True si la connexion est établie, False sinon
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connexion à la base de données établie")
        return True
    except Exception as e:
        logger.error(f"Impossible de se connecter à la base de données: {e}")
        return False


__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "get_db_context",
    "init_db",
    "check_db_connection",
]

