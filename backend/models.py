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


class LinkPredictRequest(BaseModel):
    """Link prediction request"""
    head_uri: str = Field(..., description="Head entity URI")
    relation: str = Field(..., description="Relation name to predict over")
    top_k: int = Field(3, description="Maximum number of candidates to return", ge=1, le=10)
    node_type_filter: Optional[str] = Field(None, description="Optional tail URI/type filter")


class LinkPredictionItem(BaseModel):
    """Single link prediction result"""
    tail_uri: str = Field(..., description="Predicted tail entity URI")
    confidence: float = Field(..., description="Relative softmax confidence among returned candidates")


class LinkPredictResponse(BaseModel):
    """Link prediction response"""
    head_uri: str = Field(..., description="Head entity URI")
    relation: str = Field(..., description="Relation name used for prediction")
    predictions: List[LinkPredictionItem] = Field(default_factory=list, description="Predicted tail candidates")
    model_ready: bool = Field(..., description="Whether the LP backend model is ready")
    node_type_filter: Optional[str] = Field(None, description="Applied tail filter")
    error: Optional[str] = Field(None, description="Error message if prediction failed")
