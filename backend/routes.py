"""
API Routes
"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
import os

# 명시적으로 .env 로드
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent))

from backend.models import ChatRequest, ChatResponse, HealthResponse
from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
from app.config import RDF_OUTPUT_DIR, FUSEKI_URL, FUSEKI_DATASET

# Initialize global agent
_agent = None

# USE_SUPERVISOR_AGENT=true → KGAgentSupervisor 사용 (기본값: true)
USE_SUPERVISOR = os.getenv("USE_SUPERVISOR_AGENT", "true").lower() == "true"


def get_agent():
    """Get or create KG Agent (Fuseki 데이터 자동 로드 포함)"""
    global _agent
    if _agent is None:
        # 환경 변수 확인
        provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        api_keys = os.getenv("GEMINI_API_KEYS", "")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
        fuseki_url = os.getenv("FUSEKI_URL", FUSEKI_URL)
        print(f"[ROUTE] LLM_PROVIDER: {provider}", flush=True)
        if provider in ("ollama", "qwen", "local"):
            print(f"[ROUTE] OLLAMA_BASE_URL: {ollama_url}", flush=True)
            print(f"[ROUTE] OLLAMA_MODEL: {ollama_model}", flush=True)
        else:
            print(f"[ROUTE] GEMINI_MODEL: {model}", flush=True)
            print(f"[ROUTE] GEMINI_API_KEYS: {api_keys[:30] if api_keys else 'EMPTY'}...", flush=True)
        print(f"[ROUTE] FUSEKI_URL: {fuseki_url}", flush=True)
        print(f"[ROUTE] USE_SUPERVISOR_AGENT: {USE_SUPERVISOR}", flush=True)
        
        # Fuseki 데이터 자동 로드
        try:
            executor = FusekiSPARQLExecutor(fuseki_url, FUSEKI_DATASET)
            rdf_file = RDF_OUTPUT_DIR / "generated_data.ttl"
            executor.ensure_data_loaded(rdf_file)
            print("[ROUTE] Fuseki 데이터 준비 완료", flush=True)
        except Exception as e:
            print(f"[ROUTE ERROR] Fuseki 데이터 적재 실패: {e}", flush=True)
        
        # Agent 선택 (환경 변수로 결정)
        if USE_SUPERVISOR:
            from app.agents.kg_agent_supervisor import KGAgentSupervisor
            print("[ROUTE] KGAgentSupervisor (Supervisor 패턴) 사용", flush=True)
            _agent = KGAgentSupervisor()
        else:
            from app.agents.kg_agent import KGAgent
            print("[ROUTE] KGAgent (고정 Workflow) 사용", flush=True)
            _agent = KGAgent()
    
    return _agent


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint (Fuseki 연결 확인 포함)"""
    
    # Fuseki 연결 확인
    try:
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        if not executor.check_connection():
            return HealthResponse(
                status="error",
                version="0.1.0",
                rdf_triples=0,
                message="Fuseki 서버에 연결할 수 없습니다"
            )
        
        triple_count = executor.count_triples()
        
        return HealthResponse(
            status="ok",
            version="0.1.0",
            rdf_triples=triple_count,
            message=f"Fuseki 연결 성공 ({triple_count} triples)"
        )
    except Exception as e:
        return HealthResponse(
            status="error",
            version="0.1.0",
            rdf_triples=0,
            message=f"Health check 실패: {str(e)}"
        )


@router.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint
    Processes user query through LangGraph agent
    """
    
    try:
        print(f"[ROUTE] Received query: {request.query[:50]}", flush=True)  # DEBUG
        agent = get_agent()
        print(f"[ROUTE] Agent obtained: {agent}", flush=True)  # DEBUG
        
        # Execute query
        print("[ROUTE] Executing query...", flush=True)  # DEBUG
        result = agent.query(
            query=request.query,
            use_link_prediction=request.use_link_prediction
        )
        print(f"[ROUTE] Query result: answer={result.get('answer', '')[:50]}", flush=True)  # DEBUG
        
        return ChatResponse(
            answer=result["answer"],
            sparql_query=result.get("sparql_query"),
            sparql_results=result.get("sparql_results", []),
            execution_time_ms=result.get("execution_time_ms", 0),
            sources=result.get("sources", []),
            workflow_path=result.get("workflow_path", []),
            supervisor_reasoning_log=result.get("supervisor_reasoning_log", []),
            is_sparse=result.get("is_sparse", False),
            predicted_triples=result.get("predicted_triples", []),
            error=result.get("error")
        )
    
    except Exception as e:
        import traceback
        print(f"[ROUTE ERROR] Exception: {e}", flush=True)  # DEBUG
        print(f"[ROUTE ERROR] Traceback:\n{traceback.format_exc()}", flush=True)  # DEBUG
        raise HTTPException(status_code=500, detail=str(e))
