from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, projects
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Open Publisher Web - AI tweet creation workbench",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(projects.router, prefix="/api")


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs"}
