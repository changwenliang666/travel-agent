from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import admin, auth, conversations, health, preferences
from backend.db.session import SessionLocal, init_db
from backend.services.auth import seed_admin

app = FastAPI(title="travel-assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(preferences.router)
app.include_router(conversations.router)
app.include_router(admin.router)
app.include_router(health.router)


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        seed_admin(db)
    finally:
        db.close()
