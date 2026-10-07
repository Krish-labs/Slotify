from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    academic_term,
    assignments,
    auth,
    batches,
    classes,
    faculty,
    health,
    leave,
    load,
    notifications,
    reports,
    resources,
    sections,
    subjects,
    substitutions,
    templates,
    timetable,
    users,
)
from app.core.config import settings
from app.core.exceptions import SchedulAIException, schedulai_exception_handler

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="SchedulAI - Intelligent Academic Timetable Management",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(SchedulAIException, cast(Any, schedulai_exception_handler))

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(academic_term.router, prefix="/api/v1", tags=["academic-terms"])
app.include_router(faculty.router, prefix="/api/v1", tags=["faculty"])
app.include_router(load.router, prefix="/api/v1", tags=["load"])
app.include_router(classes.router, prefix="/api/v1", tags=["classes"])
app.include_router(sections.router, prefix="/api/v1", tags=["sections"])
app.include_router(batches.router, prefix="/api/v1", tags=["batches"])
app.include_router(subjects.router, prefix="/api/v1", tags=["subjects"])
app.include_router(resources.router, prefix="/api/v1", tags=["resources"])
app.include_router(templates.router, prefix="/api/v1", tags=["templates"])
app.include_router(timetable.router, prefix="/api/v1", tags=["timetable"])
app.include_router(assignments.router, prefix="/api/v1", tags=["assignments"])
app.include_router(substitutions.router, prefix="/api/v1", tags=["substitutions"])
app.include_router(leave.router, prefix="/api/v1", tags=["leave"])
app.include_router(notifications.router, prefix="/api/v1", tags=["notifications"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
