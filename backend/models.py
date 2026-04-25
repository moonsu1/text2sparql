"""
Request/Response Models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Chat request"""
    query: str = Field(..., description="User query")
    session_id: Optional[str] = Field(None, description="Session ID")
    use_link_prediction: bool = Field(False, description="Enable link prediction")


class ChatResponse(BaseModel):
    """Chat response"""
    answer: str = Field(..., description="Generated answer")
    sparql_query: Optional[str] = Field(None, description="Generated SPARQL")
    sparql_results: List[Dict[str, Any]] = Field(default_factory=list, description="SPARQL execution results")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    sources: List[str] = Field(default_factory=list, description="Source event IDs")
    workflow_path: List[str] = Field(default_factory=list, description="LangGraph workflow path")
    supervisor_reasoning_log: List[str] = Field(default_factory=list, description="Supervisor reasoning steps")
    is_sparse: bool = Field(False, description="Was sparse detection triggered")
    predicted_triples: List[Any] = Field(default_factory=list, description="Predicted triples")
    error: Optional[str] = Field(None, description="Error message if any")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    rdf_triples: int
    message: Optional[str] = None
