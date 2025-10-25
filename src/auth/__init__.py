"""
Authentication module for Google Photos API.
"""

from .google_photos_auth import SCOPES, GooglePhotosAPI, auth_router

__all__ = ["GooglePhotosAPI", "auth_router", "SCOPES"]
