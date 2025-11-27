"""
Module API - Points d'entrée RESTful de l'application.
"""

from .deps import get_current_user, get_current_active_user, require_roles

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_roles",
]

