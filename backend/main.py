"""
FastAPI Main Application
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import router
from backend.openai_compat import router as openai_router
from backend.test_ui import add_test_ui_route


async def _warmup_ollama():
    """백엔드 시작 시 Ollama 모델을 GPU에 미리 로드."""
    import httpx
    import sys

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").replace(
        "localhost", "host.docker.internal"
    )
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b-q8_0")

    print(f"[Warmup] Loading model: {model}", flush=True)
    sys.stdout.flush()
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": "hi", "stream": False},
            )
            if resp.status_code == 200:
                print(f"[Warmup] Model loaded OK: {model}", flush=True)
            else:
                print(f"[Warmup] Warning: status={resp.status_code} body={resp.text[:100]}", flush=True)
    except Exception as e:
        print(f"[Warmup] Failed (ignored): {e}", flush=True)
    sys.stdout.flush()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _warmup_ollama()
    yield


# Create FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="RDF Knowledge Graph API",
    description="LangGraph-based QA system with link prediction",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)
app.include_router(openai_router)

# Add test UI
add_test_ui_route(app)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RDF Knowledge Graph API",
        "version": "0.1.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Disabled for stability
    )
