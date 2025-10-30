from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            print(f"💥 [error] {type(e).__name__}: {e}")
            return JSONResponse({"detail": str(e)}, status_code=500)
