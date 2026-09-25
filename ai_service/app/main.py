from fastapi import FastAPI

from .routers import chat, embeddings, health, interview, resume_analysis

app = FastAPI(
    title="Interview Assistant AI Service",
    description=(
        "Internal AI-service layer (Module 8): the only component in this "
        "system that calls Gemini. Django (auth, resumes, RAG orchestration, "
        "history) calls this over HTTP; this service has no database, no "
        "user accounts, and no business logic of its own."
    ),
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(embeddings.router)
app.include_router(resume_analysis.router)
app.include_router(interview.router)
