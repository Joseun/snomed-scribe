from fastapi import FastAPI

from app.db import Base, engine
from app.routers import metrics, notes, suggestions

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ClinCode")

app.include_router(notes.router)
app.include_router(suggestions.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
