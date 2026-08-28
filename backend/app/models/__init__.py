"""
app/models/__init__.py
Import all models so Alembic's autogenerate picks them up.
"""
from app.models.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.scan import Scan, ScanStatus, SourceType  # noqa: F401
from app.models.finding import SecurityFinding, DependencyFinding  # noqa: F401
from app.models.report import Report  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Scan",
    "ScanStatus",
    "SourceType",
    "SecurityFinding",
    "DependencyFinding",
    "Report",
]
