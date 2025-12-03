"""Vercel serverless function entry point."""
from src.app import app

# Export ASGI app for Vercel
# Vercel will use this as the handler
handler = app

