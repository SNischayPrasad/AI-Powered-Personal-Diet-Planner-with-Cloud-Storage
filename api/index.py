"""Vercel serverless entry point (deployment approach A, "all on Vercel").

Vercel serves the React build as static files and routes /api/* here (see vercel.json). The
function's filesystem is read-only, so set DATABASE_URL (Supabase / Neon) and
STORAGE_PROVIDER=s3 in the Vercel project settings; see docs/15-cloud-deployment.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root

from backend.app import app  # noqa: E402

__all__ = ["app"]
