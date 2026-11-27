"""Нормализация и серверная проверка заявки."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Inquiry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr = Field(max_length=254)
    service: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=10, max_length=2000)
    consent: bool
    website: str = Field(default="", max_length=200)
    token: str = Field(min_length=10, max_length=300)

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value):
        if not value:
            raise ValueError("Необходимо согласие на обработку заявки")
        return value

    @field_validator("name", "message")
    @classmethod
    def no_controls(cls, value):
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Недопустимые управляющие символы")
        return value
