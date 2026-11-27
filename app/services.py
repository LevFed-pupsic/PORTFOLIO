"""Подпись формы, антиспам и сохранение заявки."""

import hashlib
import hmac
import secrets
import time
from .database import save_inquiry


def digest(secret, value):
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_token(settings):
    # Временная метка подписана: посетитель не может сам сделать форму старше.
    payload = f"{int(time.time())}.{secrets.token_hex(16)}"
    return payload + "." + digest(settings.secret, payload)


def token_age(token, settings):
    try:
        stamp, nonce, signature = token.split(".")
        payload = stamp + "." + nonce
        if not hmac.compare_digest(signature, digest(settings.secret, payload)):
            return None
        return int(time.time()) - int(stamp)
    except (ValueError, TypeError):
        return None


def submit(data, settings, client):
    age = token_age(data.token, settings)
    if age is None or age < 0 or age > settings.token_lifetime:
        return "expired"
    if data.website or age < settings.min_form_seconds:
        return "spam"
    fingerprint = digest(
        settings.secret,
        "\0".join(
            (
                data.name.casefold(),
                str(data.email).casefold(),
                data.service,
                data.message,
            )
        ),
    )
    return save_inquiry(
        settings.database,
        data,
        fingerprint,
        digest(settings.secret, client),
        int(time.time()),
        settings.rate_limit,
        settings.rate_window,
    )
