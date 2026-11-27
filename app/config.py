"""Настройки приложения; секреты читаются только из окружения."""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent


@dataclass
class Settings:
    database: Path = field(
        default_factory=lambda: Path(
            os.getenv("DATABASE_PATH", str(BASE.parent / "var" / "inquiries.sqlite3"))
        )
    )
    secret: str = field(
        default_factory=lambda: os.getenv("APP_SECRET") or secrets.token_hex(32)
    )
    min_form_seconds: int = 2
    token_lifetime: int = 7200
    rate_limit: int = 5
    rate_window: int = 600
