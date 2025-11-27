"""
Module des schémas Pydantic pour Kobiri.
Définit les modèles de validation pour les requêtes et réponses API.
"""

from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB,
    UserLogin,
    Token,
    TokenPayload,
    PasswordChange,
    PasswordReset,
)
from .tontine import (
    TontineBase,
    TontineCreate,
    TontineUpdate,
    TontineResponse,
    TontineListResponse,
    TontineMemberBase,
    TontineMemberCreate,
    TontineMemberResponse,
    TontineMemberUpdate,
)
from .session import (
    SessionBase,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionListResponse,
    SessionStats,
)
from .payment import (
    PaymentBase,
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaymentListResponse,
    PaymentValidation,
    PaymentCallback,
    PaymentInitiate,
)
from .passage import (
    PassageBase,
    PassageCreate,
    PassageUpdate,
    PassageResponse,
    PassageListResponse,
    PassageOrderUpdate,
)
from .notification import (
    NotificationBase,
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkRead,
)

__all__ = [
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    "UserLogin",
    "Token",
    "TokenPayload",
    "PasswordChange",
    "PasswordReset",
    # Tontine
    "TontineBase",
    "TontineCreate",
    "TontineUpdate",
    "TontineResponse",
    "TontineListResponse",
    "TontineMemberBase",
    "TontineMemberCreate",
    "TontineMemberResponse",
    "TontineMemberUpdate",
    # Session
    "SessionBase",
    "SessionCreate",
    "SessionUpdate",
    "SessionResponse",
    "SessionListResponse",
    "SessionStats",
    # Payment
    "PaymentBase",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentResponse",
    "PaymentListResponse",
    "PaymentValidation",
    "PaymentCallback",
    "PaymentInitiate",
    # Passage
    "PassageBase",
    "PassageCreate",
    "PassageUpdate",
    "PassageResponse",
    "PassageListResponse",
    "PassageOrderUpdate",
    # Notification
    "NotificationBase",
    "NotificationCreate",
    "NotificationResponse",
    "NotificationListResponse",
    "NotificationMarkRead",
]

