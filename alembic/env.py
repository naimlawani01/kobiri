"""
Configuration Alembic pour les migrations de base de données Kobiri.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import de la configuration et des modèles
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import Base

# Import de tous les modèles pour qu'ils soient enregistrés avec Base
from app.models import (
    User,
    Tontine,
    TontineMember,
    CotisationSession,
    Payment,
    Passage,
    Notification,
)


# Configuration Alembic
config = context.config

# Configurer le logging depuis alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées du modèle pour autogenerate
target_metadata = Base.metadata

# Surcharger l'URL de la base de données depuis les settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Exécute les migrations en mode 'offline'.
    
    Configure le contexte avec seulement une URL, sans Engine.
    En utilisant script.generate_revision(), les migrations peuvent
    être générées sans connexion à la base de données.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Exécute les migrations en mode 'online'.
    
    Crée un Engine et associe une connexion au contexte.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,  # Détecter les changements de type
            compare_server_default=True,  # Détecter les changements de valeur par défaut
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

