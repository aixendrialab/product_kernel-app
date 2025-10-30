# product_kernel/web/errors.py
from __future__ import annotations
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, NoResultFound
import traceback


def error_envelope(code: str, message: str, details=None):
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except IntegrityError:
        return JSONResponse(
            error_envelope("CONFLICT", "Integrity violation"), status_code=409
        )
    except NoResultFound:
        return JSONResponse(
            error_envelope("NOT_FOUND", "Resource not found"), status_code=404
        )
    except ValueError as e:
        return JSONResponse(error_envelope("BAD_REQUEST", str(e)), status_code=400)
    except Exception as e:
        print("⚠️ Unexpected error:", traceback.format_exc())
        return JSONResponse(
            error_envelope("SERVER_ERROR", "Unexpected error"), status_code=500
        )


def add_error_handlers(app: FastAPI) -> None:
    """Attach global exception middleware & handlers to app."""
    app.middleware("http")(exception_middleware)
    print("✅ [kernel] Global error handlers registered")
