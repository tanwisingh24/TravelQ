"""
Vercel serverless entrypoint.

Vercel's Python runtime looks for a WSGI-compatible `app` object in this
file. It just re-exports the real Flask app from backend/app.py — all
routes, auth, and DB logic live there unchanged.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import app  # noqa: E402
