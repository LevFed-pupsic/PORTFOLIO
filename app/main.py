"""Маршруты сайта и JSON API формы. Публичного API чтения заявок нет."""

import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from .config import BASE, Settings
from .database import initialize
from .schemas import Inquiry
from .services import create_token, submit

logger = logging.getLogger(__name__)


def create_app(settings=None):
    settings = settings or Settings()
    content = json.loads((BASE / "data" / "content.json").read_text(encoding="utf-8"))

    @asynccontextmanager
    async def lifespan(app):
        initialize(settings.database)
        yield

    app = FastAPI(
        title="Morozov Photography",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    templates = Jinja2Templates(directory=BASE / "templates")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "X-Frame-Options": "SAMEORIGIN",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                "Content-Security-Policy": "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'",
            }
        )
        if request.url.path in ("/", "/portfolio") or request.url.path.startswith(
            "/api/"
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"site": content, "token": create_token(settings)},
        )

    @app.get("/portfolio", response_class=HTMLResponse)
    async def portfolio(request: Request):
        return templates.TemplateResponse(
            request=request, name="portfolio.html", context={"site": content}
        )

    @app.get("/privacy", response_class=HTMLResponse)
    async def privacy(request: Request):
        return templates.TemplateResponse(
            request=request, name="privacy.html", context={"site": content}
        )

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots():
        return "User-agent: *\nDisallow: /api/\n"

    @app.post("/api/inquiries")
    async def contact(request: Request):
        # Ограничение применяется к реальному потоку, не только Content-Length.
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"message": "Ожидается JSON."}, status_code=415)
        origin = request.headers.get("origin")
        if origin and (urlsplit(origin).scheme, urlsplit(origin).netloc) != (
            request.url.scheme,
            request.url.netloc,
        ):
            return JSONResponse(
                {"message": "Отправьте форму с этого сайта."}, status_code=403
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                return JSONResponse(
                    {"message": "Заявка слишком большая."}, status_code=413
                )
        try:
            data = Inquiry.model_validate_json(body)
        except ValidationError:
            return JSONResponse(
                {
                    "message": "Проверьте имя, email, сообщение (10–2000 символов) и согласие."
                },
                status_code=422,
            )
        if data.service not in [s["id"] for s in content["services"]]:
            return JSONResponse(
                {"message": "Выберите услугу из списка."}, status_code=422
            )
        try:
            result = await run_in_threadpool(
                submit,
                data,
                settings,
                request.client.host if request.client else "unknown",
            )
        except sqlite3.Error:
            logger.error("Не удалось сохранить заявку в SQLite")
            return JSONResponse(
                {"message": "Не удалось сохранить заявку. Попробуйте позже."},
                status_code=503,
            )
        if result == "expired":
            return JSONResponse(
                {
                    "message": "Срок формы истёк. Скопируйте сообщение и обновите страницу."
                },
                status_code=403,
            )
        if result == "spam":
            return JSONResponse(
                {"message": "Подождите несколько секунд и повторите отправку."},
                status_code=400,
            )
        if result == "limited":
            return JSONResponse(
                {"message": "Слишком много заявок. Попробуйте через 10 минут."},
                status_code=429,
                headers={"Retry-After": str(settings.rate_window)},
            )
        if result == "duplicate":
            return JSONResponse(
                {
                    "message": "Эта заявка уже сохранена. Повторно отправлять её не нужно."
                }
            )
        return JSONResponse(
            {
                "message": "Спасибо! Ваша заявка сохранена. Это демоверсия: ответ фотографа не предусмотрен."
            },
            status_code=201,
        )

    return app


app = create_app()
