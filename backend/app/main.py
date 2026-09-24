import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.storage import ensure_bucket
from app.routers import admin_exams, admin_management, auth, results, student

logger = logging.getLogger(__name__)

app = FastAPI(title="Spetion Exam Platform API")


@app.on_event("startup")
def on_startup() -> None:
    try:
        ensure_bucket()
    except Exception:
        logger.warning("S3/MinIO bucket bilan bog'lanib bo'lmadi (dev muhitida oddiy holat)", exc_info=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(admin_exams.router)
app.include_router(admin_management.router)
app.include_router(results.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
