"""
Agent State Definition
LangGraph workflow에서 사용하는 state 구조
"""

from typing import TypedDict, Optional, List, Dict, Any, Annotated
from operator import add


class AgentState(TypedDict):
    """LangGraph Agent State"""
    
    # Input
    query: str
    session_id: Optional[str]
    use_link_prediction: bool
    
    # Query Analysis
    intent: Optional[str]
    target_relation: Optional[str]
    entities: Dict[str, Any]
    time_constraint: Optional[Dict[str, Any]]
    
    # Supervisor Pattern
    current_stage: Optional[str]
    supervisor_reasoning_log: Annotated[List[str], add]
    resolved_entities: Dict[str, str]
    result_verification: Optional[Dict[str, Any]]
    link_prediction_done: bool
    sparql_retry_count: int
    
    # Sparse Detection
    is_sparse: bool
    missing_relations: Annotated[List[str], add]
    sparse_score: float
    
    # Link Prediction
    predicted_triples: Annotated[List[tuple], add]
    prediction_confidence: Annotated[List[float], add]
    prediction_evidence: Annotated[List[Dict[str, Any]], add]

    # Multi-hop LP
    lp_chain: Optional[str]          # 체인 식별자 (예: "relatedEvent+metDuring"), None이면 1-hop
    lp_hop_index: int                 # 현재 실행 중인 hop 번호 (0=1차, 1=2차)
    lp_intermediate_node: Optional[str]  # 1차 예측 tail URI → 2차 LP의 head

    # LLM Hybrid Verification
    lp_llm_reason: Optional[str]     # LLM이 최종 후보를 선택한 근거 텍스트

    # Conversation Context (multi-turn)
    conversation_history: Optional[str]  # 이전 대화 요약 (user+assistant 교환)
    
    # SPARQL Generation
    sparql_query: Optional[str]
    mermaid_graph: Optional[str]
    relevant_properties: Annotated[List[str], add]
    
    # Execution
    sparql_results: Optional[List[Dict[str, Any]]]
    execution_time_ms: float
    
    # Answer Generation
    answer: Optional[str]
    sources: Annotated[List[str], add]
    
    # Error Handling
    error: Optional[str]
    retry_count: int
    
    # Metadata
    workflow_path: Annotated[List[str], add]
    intermediate_results: Dict[str, Any]
