"""
FastAPI Main Application
"""

import sys
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

# Create FastAPI app
app = FastAPI(
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
