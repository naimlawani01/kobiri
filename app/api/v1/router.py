"""
Routeur principal de l'API v1.
Regroupe toutes les routes des différents modules.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    tontines,
    sessions,
    payments,
    passages,
    notifications,
)

api_router = APIRouter()

# Routes d'authentification
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentification"],
)

# Routes utilisateurs
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Utilisateurs"],
)

# Routes tontines
api_router.include_router(
    tontines.router,
    prefix="/tontines",
    tags=["Tontines"],
)

# Routes sessions de cotisation
api_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["Sessions de cotisation"],
)

# Routes paiements
api_router.include_router(
    payments.router,
    prefix="/payments",
    tags=["Paiements"],
)

# Routes passages
api_router.include_router(
    passages.router,
    prefix="/passages",
    tags=["Tours de passage"],
)

# Routes notifications
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)

