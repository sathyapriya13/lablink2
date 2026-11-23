"""Vercel FastAPI entry point. Cloud Run uses backend/app/main.py directly."""

from backend.app.main import app as lablink_app

app = lablink_app
