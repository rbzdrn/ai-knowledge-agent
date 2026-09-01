#!/usr/bin/env python3
"""Start the AI Knowledge Base Agent server."""

import sys
import os
from pathlib import Path

# Add backend to path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

if __name__ == "__main__":
    print("Starting AI Knowledge Base Agent...")
    print(f"API: http://localhost:8000")
    print(f"UI:  http://localhost:8000")
    print(f"Docs: http://localhost:8000/docs")
    print()

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
