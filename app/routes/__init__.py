# app/routes/__init__.py

from .registration_routes import registration_bp
from .confirmation_routes import confirmation_bp
from .preview_routes import preview_bp

__all__ = ["registration_bp", "confirmation_bp", "preview_bp"]
