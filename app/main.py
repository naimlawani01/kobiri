"""
Kobiri - Point d'entrée principal de l'application.
Plateforme de gestion de tontines pour l'Afrique de l'Ouest.
"""

import time
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import check_db_connection, init_db
from app.core.logging import setup_logging, logger, log_request
from app.api.v1.router import api_router


# Configuration du logging au démarrage
setup_logging(
    log_level="DEBUG" if settings.DEBUG else "INFO",
    log_file="logs/kobiri.log",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application.
    Exécuté au démarrage et à l'arrêt.
    """
    # Démarrage
    logger.info("=" * 60)
    logger.info(f"Démarrage de {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environnement: {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    
    # Vérifier la connexion à la base de données
    if not check_db_connection():
        logger.error("Impossible de se connecter à la base de données!")
        # En mode développement, on peut initialiser la base
        if settings.DEBUG:
            logger.info("Mode DEBUG: Tentative d'initialisation de la base...")
            try:
                init_db()
            except Exception as e:
                logger.error(f"Erreur d'initialisation: {e}")
    
    logger.info("Application prête à recevoir des requêtes")
    
    yield
    
    # Arrêt
    logger.info("Arrêt de l'application...")
    logger.info("Application arrêtée proprement")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## Kobiri - Plateforme de gestion de tontines
    
    ### Fonctionnalités principales:
    
    * **Gestion des utilisateurs** - Inscription, authentification JWT, profils
    * **Gestion des tontines** - Création, paramétrage, membres, règles
    * **Sessions de cotisation** - Planification, suivi des paiements
    * **Paiements** - Espèces, Orange Money, Wave, MTN MoMo
    * **Tours de passage** - Ordre, versements, confirmations
    * **Notifications** - SMS, Email, Push, In-App
    
    ### Rôles:
    
    * **Membre** - Participe aux cotisations
    * **Président** - Gère la tontine
    * **Trésorier** - Gère les finances
    * **Admin** - Administration de la plateforme
    
    ### Documentation API:
    
    * Swagger UI: `/docs`
    * ReDoc: `/redoc`
    * OpenAPI JSON: `/openapi.json`
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_tags=[
        {"name": "Authentification", "description": "Inscription, connexion, tokens JWT"},
        {"name": "Utilisateurs", "description": "Gestion des profils utilisateurs"},
        {"name": "Tontines", "description": "Création et gestion des tontines"},
        {"name": "Sessions de cotisation", "description": "Cycles de collecte"},
        {"name": "Paiements", "description": "Cotisations et transactions"},
        {"name": "Tours de passage", "description": "Ordre de réception du pot"},
        {"name": "Notifications", "description": "Alertes et rappels"},
    ],
)


# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:8080",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de logging des requêtes
@app.middleware("http")
async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware pour logger toutes les requêtes HTTP.
    """
    start_time = time.time()
    
    # Récupérer l'ID utilisateur du token si présent
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        from app.core.security import decode_token_unsafe
        token = auth_header[7:]
        payload = decode_token_unsafe(token)
        if payload:
            user_id = payload.get("sub")
    
    # Exécuter la requête
    response = await call_next(request)
    
    # Calculer la durée
    duration_ms = (time.time() - start_time) * 1000
    
    # Logger la requête
    log_request(
        method=request.method,
        url=str(request.url.path),
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=user_id,
    )
    
    # Ajouter des headers de performance
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    
    return response


# Gestionnaire d'erreurs de validation
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    Gestionnaire personnalisé pour les erreurs de validation Pydantic.
    """
    logger.warning(f"Erreur de validation: {exc.errors()}")
    
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Erreur de validation des données",
            "errors": errors,
        },
    )


# Gestionnaire d'erreurs SQLAlchemy
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """
    Gestionnaire pour les erreurs de base de données.
    """
    logger.error(f"Erreur SQLAlchemy: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Erreur de base de données",
            "message": "Une erreur est survenue lors de l'accès aux données",
        },
    )


# Gestionnaire d'erreurs génériques
@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Gestionnaire pour toutes les autres exceptions.
    """
    logger.error(f"Erreur non gérée: {exc}", exc_info=True)
    
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
            },
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Une erreur interne est survenue",
        },
    )


# Inclusion du routeur API v1
app.include_router(api_router, prefix="/api/v1")


# Route de santé
@app.get(
    "/health",
    tags=["Système"],
    summary="Vérification de l'état de l'application",
)
async def health_check():
    """
    Endpoint de health check pour les load balancers et monitoring.
    """
    db_status = "ok" if check_db_connection() else "error"
    
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }


# Route racine
@app.get("/", tags=["Système"])
async def root():
    """
    Point d'entrée racine de l'API.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Plateforme de gestion de tontines pour l'Afrique de l'Ouest",
        "docs": "/docs" if settings.DEBUG else "Documentation désactivée en production",
        "health": "/health",
        "api": "/api/v1",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )

