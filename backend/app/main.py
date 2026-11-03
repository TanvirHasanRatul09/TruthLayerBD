from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.api.analyses import router as analyses_router
from app.core.rate_limit import rate_limit_middleware
from app.core.visitor import visitor_session_middleware
from app.db.session import get_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.app_env == "production" and (settings.app_secret_key == "replace-with-a-long-random-value" or len(settings.app_secret_key) < 32):
        raise RuntimeError("Set a unique APP_SECRET_KEY of at least 32 characters before production startup.")
    get_engine(get_settings().database_url)
    yield

settings = get_settings()
app = FastAPI(title="TruthLayer BD API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.include_router(analyses_router, prefix="/api/v1")
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(visitor_session_middleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/v1/analyses"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    codes = {400: "BAD_REQUEST", 404: "NOT_FOUND", 409: "CONFLICT", 413: "UPLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED", 503: "UNAVAILABLE"}
    return JSONResponse(status_code=exc.status_code, headers=exc.headers, content={"code": codes.get(exc.status_code, "REQUEST_ERROR"), "detail": exc.detail if isinstance(exc.detail, str) else "Request could not be completed."})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"code": "VALIDATION_ERROR", "detail": "Invalid request data."})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error("Unhandled %s on %s", type(exc).__name__, request.url.path)
    return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR", "detail": "The request could not be completed. Please try again."})


@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "database": {"configured": bool(settings.database_url)},
        "providers": {
            "gemini": {"configured": settings.gemini_enabled and bool(settings.gemini_api_key)},
            "tavily": {"configured": settings.tavily_enabled and bool(settings.tavily_api_key)},
        },
    }


# Mount after every API route: a root mount otherwise hides later endpoints.
# A production build can share the API's origin under one tunnel or hostname.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
