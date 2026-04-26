"""
KG Agent - LangGraph Workflow
RDF Knowledge Graph 기반 QA Agent
"""

import sys
from pathlib import Path
from typing import Literal, Dict

sys.path.append(str(Path(__file__).parent.parent.parent))

from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import (
    query_analysis_node,
    sparse_detection_node,
    link_prediction_node,
    text2sparql_node,
    execute_sparql_node,
    answer_generation_node
)


class KGAgent:
    """Knowledge Graph Agent with LangGraph"""
    
    def __init__(self):
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
    
    def _build_workflow(self) -> StateGraph:
        """LangGraph workflow 구축"""
        
        # StateGraph 생성
        workflow = StateGraph(AgentState)
        
        # Nodes 추가
        workflow.add_node("query_analysis", query_analysis_node)
        workflow.add_node("sparse_detection", sparse_detection_node)
        workflow.add_node("link_prediction", link_prediction_node)
        workflow.add_node("text2sparql", text2sparql_node)
        workflow.add_node("execute_sparql", execute_sparql_node)
        workflow.add_node("answer_generation", answer_generation_node)
        
        # Entry point
        workflow.set_entry_point("query_analysis")
        
        # Edges
        workflow.add_edge("query_analysis", "sparse_detection")
        
        # Conditional edge: sparse data 판단
        def should_use_link_prediction(state: AgentState) -> Literal["text2sparql", "link_prediction"]:
            if state.get("use_link_prediction", False) and state.get("is_sparse", False):
                return "link_prediction"
            return "text2sparql"
        
        workflow.add_conditional_edges(
            "sparse_detection",
            should_use_link_prediction,
            {
                "text2sparql": "text2sparql",
                "link_prediction": "link_prediction"
            }
        )
        
        workflow.add_edge("link_prediction", "text2sparql")
        workflow.add_edge("text2sparql", "execute_sparql")
        workflow.add_edge("execute_sparql", "answer_generation")
        workflow.add_edge("answer_generation", END)
        
        return workflow
    
    def query(self, query: str, use_link_prediction: bool = False) -> Dict:
        """사용자 질의 실행"""
        
        print("=" * 70)
        print(f"[KG Agent] Query: {query}")
        print("=" * 70)
        
        # 초기 state
        initial_state = {
            "query": query,
            "session_id": None,
            "use_link_prediction": use_link_prediction,
            "intent": None,
            "target_relation": None,
            "entities": {},
            "time_constraint": None,
            "is_sparse": False,
            "missing_relations": [],
            "sparse_score": 1.0,
            "predicted_triples": [],
            "prediction_confidence": [],
            "prediction_evidence": [],
            "sparql_query": None,
            "relevant_properties": [],
            "sparql_results": [],
            "execution_time_ms": 0.0,
            "answer": None,
            "sources": [],
            "error": None,
            "retry_count": 0,
            "workflow_path": [],
            "intermediate_results": {}
        }
        
        # Workflow 실행
        final_state = self.app.invoke(initial_state)
        
        # 결과 정리
        result = {
            "query": query,
            "answer": final_state.get("answer", "답변 생성 실패"),
            "sparql_query": final_state.get("sparql_query"),
            "execution_time_ms": final_state.get("execution_time_ms", 0),
            "sources": final_state.get("sources", []),
            "workflow_path": final_state.get("workflow_path", []),
            "is_sparse": final_state.get("is_sparse", False),
            "predicted_triples": final_state.get("predicted_triples", []),
            "prediction_confidence": final_state.get("prediction_confidence", []),
            "prediction_evidence": final_state.get("prediction_evidence", []),
            "error": final_state.get("error")
        }
        
        return result


def main():
    """테스트"""
    print("=" * 70)
    print("KG Agent with LangGraph - Test")
    print("=" * 70)
    
    agent = KGAgent()
    
    # 테스트 질의
    test_queries = [
        "최근 통화한 사람은 누구야?",
        "가장 자주 쓴 앱 뭐야?",
    ]
    
    for query in test_queries:
        result = agent.query(query)
        
        print(f"\n{'='*70}")
        print(f"질문: {query}")
        print(f"{'='*70}")
        print(f"\n[답변]\n{result['answer']}")
        print(f"\n[메타정보]")
        print(f"  Workflow: {' → '.join(result['workflow_path'])}")
        print(f"  Execution time: {result['execution_time_ms']:.2f}ms")
        print(f"  Sources: {result['sources']}")
        print("\n" + "-" * 70)


if __name__ == "__main__":
    main()
