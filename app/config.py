"""Настройки приложения; секреты читаются только из окружения."""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

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

    site_url: str = field(default_factory=lambda: os.getenv(
        "SITE_URL", "https://morozov-photography.de2.netrun.io"
    ).rstrip("/"))

    def __post_init__(self):
        url = urlsplit(self.site_url)
        if (url.scheme not in ("http", "https") or not url.hostname
                or url.username or url.password or url.path or url.query or url.fragment):
            raise ValueError("SITE_URL must be an absolute http(s) origin without a path")
        # Accessing port also rejects malformed values during startup.
        _ = url.port
