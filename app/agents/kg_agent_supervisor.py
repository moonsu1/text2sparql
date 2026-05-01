"""
KG Agent - Supervisor Pattern
Gemini 2.5 Flash에 최적화된 동적 워크플로우

구조:
  supervisor → stage → supervisor → stage → ... → answer

Supervisor(rule-based)가 매 단계마다 상황을 보고 다음 stage 결정 + reasoning 생성
각 stage는 focused 함수만 실행 (Flash LLM 부담 최소화)
"""

import sys
from pathlib import Path
from typing import Dict, Any, Iterator, List, Optional

sys.path.append(str(Path(__file__).parent.parent.parent))

from langgraph.graph import StateGraph, END

from app.agents.llm_client import call_llm_stream
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_decide, format_reasoning_for_display, MAX_TOTAL_ITERATIONS
from app.agents.stages import (
    query_analysis_stage,
    entity_resolution_stage,
    sparql_generation_stage,
    execution_stage,
    link_prediction_stage,
    answer_generation_stage,
    build_answer_generation_prompt,
    collect_answer_sources,
)


class KGAgentSupervisor:
    """
    Supervisor Pattern KG Agent
    
    - Supervisor: rule-based로 다음 stage 즉시 결정 (빠름, 안정적)
    - 각 Stage: focused 도구만 사용
    - Reasoning: supervisor 판단 근거가 스트리밍 출력에 포함됨
    """
    
    def __init__(self):
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
    
    def _build_workflow(self) -> StateGraph:
        """Supervisor 패턴 워크플로우 구축"""
        
        workflow = StateGraph(AgentState)
        
        # ── Supervisor Node ──────────────────────────────
        def supervisor_node(state: AgentState) -> Dict[str, Any]:
            """
            상태를 보고 다음 stage 결정 + reasoning 생성
            """
            # 무한루프 방지
            iteration = len(state.get("workflow_path", []))
            if iteration >= MAX_TOTAL_ITERATIONS * 2:
                print(f"  [Supervisor] 최대 반복 횟수 초과 ({iteration}회)")
                return {
                    "current_stage": "END",
                    "supervisor_reasoning_log": ["최대 반복 횟수를 초과했습니다. 작업을 종료합니다."],
                }
            
            next_stage, reasoning = supervisor_decide(state)
            
            # Reasoning 번호 매기기 (현재까지 몇 번째 supervisor 판단인지)
            reasoning_count = len(state.get("supervisor_reasoning_log", [])) + 1
            formatted_reasoning = format_reasoning_for_display(reasoning, reasoning_count)
            
            print(f"\n[SUPERVISOR] → {next_stage}")
            print(f"  Reasoning: {reasoning[:80]}{'...' if len(reasoning) > 80 else ''}")
            
            return {
                "current_stage": next_stage,
                "supervisor_reasoning_log": [formatted_reasoning],
                "workflow_path": ["supervisor"],
            }
        
        # ── Node 등록 ────────────────────────────────────
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("entity_resolution", entity_resolution_stage)
        workflow.add_node("sparql_generation", sparql_generation_stage)
        workflow.add_node("execution", execution_stage)
        workflow.add_node("link_prediction", link_prediction_stage)
        workflow.add_node("answer", answer_generation_stage)
        
        # ── Entry Point ──────────────────────────────────
        workflow.set_entry_point("supervisor")
        
        # ── Supervisor → Stage Routing ───────────────────
        def route_from_supervisor(state: AgentState) -> str:
            stage = state.get("current_stage", "END")
            if stage not in {"entity_resolution", "sparql_generation", "execution",
                             "link_prediction", "answer", "END"}:
                return "END"
            return stage
        
        workflow.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            {
                "entity_resolution": "entity_resolution",
                "sparql_generation": "sparql_generation",
                "execution": "execution",
                "link_prediction": "link_prediction",
                "answer": "answer",
                "END": END,
            }
        )
        
        # ── Stage → Supervisor (모든 stage는 supervisor로 복귀) ──
        for stage_name in ["entity_resolution", "sparql_generation", "execution", "link_prediction"]:
            workflow.add_edge(stage_name, "supervisor")
        
        # ── Answer → END ─────────────────────────────────
        workflow.add_edge("answer", END)
        
        return workflow
    
    def _build_initial_state(
        self,
        query: str,
        use_link_prediction: bool,
        initial_result: Dict[str, Any],
        conversation_history: Optional[str] = None,
    ) -> Dict[str, Any]:
        """질의 분석 결과를 LangGraph 초기 state로 변환"""
        # query_analysis_stage가 target_relation으로 LP 필요성을 판단한 경우 우선 적용
        effective_link_prediction = (
            use_link_prediction or initial_result.get("use_link_prediction", False)
        )

        return {
            "query": query,
            "session_id": None,
            "use_link_prediction": effective_link_prediction,

            # query_analysis 결과 병합
            "intent": initial_result.get("intent"),
            "target_relation": initial_result.get("target_relation"),
            "entities": initial_result.get("entities", {}),
            "time_constraint": initial_result.get("time_constraint"),

            # Supervisor 관련
            "current_stage": None,
            "supervisor_reasoning_log": [],
            "resolved_entities": {},
            "result_verification": None,
            "link_prediction_done": False,
            "sparql_retry_count": 0,

            # Multi-hop LP
            "lp_chain": initial_result.get("lp_chain"),
            "lp_hop_index": initial_result.get("lp_hop_index", 0),
            "lp_intermediate_node": initial_result.get("lp_intermediate_node"),
            "lp_llm_reason": None,

            # Conversation Context
            "conversation_history": conversation_history,

            # 나머지 초기화
            "is_sparse": False,
            "missing_relations": [],
            "sparse_score": 1.0,
            "predicted_triples": [],
            "prediction_confidence": [],
            "prediction_evidence": [],
            "sparql_query": None,
            "mermaid_graph": None,
            "relevant_properties": [],
            "sparql_results": None,
            "execution_time_ms": 0.0,
            "answer": None,
            "sources": [],
            "error": None,
            "retry_count": 0,
            "workflow_path": ["query_analysis"],
            "intermediate_results": {},
        }

    def _build_result(self, query: str, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """최종 state를 API 응답용 dict로 정리"""
        return {
            "query": query,
            "answer": final_state.get("answer") or "답변을 생성할 수 없습니다.",
            "sparql_query": final_state.get("sparql_query"),
            "sparql_results": final_state.get("sparql_results") or [],
            "execution_time_ms": final_state.get("execution_time_ms", 0),
            "sources": final_state.get("sources", []),
            "workflow_path": final_state.get("workflow_path", []),
            "supervisor_reasoning_log": final_state.get("supervisor_reasoning_log", []),
            "is_sparse": final_state.get("is_sparse", False),
            "predicted_triples": final_state.get("predicted_triples", []),
            "prediction_confidence": final_state.get("prediction_confidence", []),
            "prediction_evidence": final_state.get("prediction_evidence", []),
            "lp_llm_reason": final_state.get("lp_llm_reason"),
            "result_verification": final_state.get("result_verification"),
            "error": final_state.get("error"),
        }

    @staticmethod
    def _compact_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """결과 payload에 남길 가벼운 이벤트 로그"""
        return {key: value for key, value in event.items() if key != "state"}

    def _emit_event(
        self,
        events: List[Dict[str, Any]],
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """이벤트를 기록하고 반환"""
        events.append(self._compact_event(event))
        return event

    @staticmethod
    def _merge_state_update(
        state: Dict[str, Any],
        update: Dict[str, Any],
    ) -> Dict[str, Any]:
        """LangGraph updates stream의 node update를 누적 state에 반영"""
        next_state = dict(state)
        additive_keys = {
            "supervisor_reasoning_log",
            "missing_relations",
            "predicted_triples",
            "prediction_confidence",
            "prediction_evidence",
            "relevant_properties",
            "sources",
            "workflow_path",
        }

        for key, value in update.items():
            if key in additive_keys and isinstance(value, list):
                current = next_state.get(key) or []
                next_state[key] = list(current) + value
            else:
                next_state[key] = value

        return next_state

    def _run_query_analysis(
        self,
        query: str,
        use_link_prediction: bool,
        conversation_history: Optional[str] = None,
    ) -> Dict[str, Any]:
        """첫 번째 고정 단계인 질의 분석 실행"""
        print("=" * 70)
        print(f"[KG Supervisor Agent] Query: {query[:80]}")
        print("=" * 70)

        # ── 질의 분석 (첫 번째 고정 단계) ──────────────────
        return query_analysis_stage({
            "query": query,
            "use_link_prediction": use_link_prediction,
            "conversation_history": conversation_history,
        })

    def stream_query_events(
        self,
        query: str,
        use_link_prediction: bool = False,
        conversation_history: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        LangGraph 실행 중 상태 변화를 이벤트로 스트리밍.

        OpenAI-compatible SSE endpoint가 supervisor 판단을 각 stage 직전에
        보여줄 수 있도록, 완성된 결과를 기다리지 않고 단계별 이벤트를 낸다.
        """
        execution_events: List[Dict[str, Any]] = []

        try:
            yield self._emit_event(
                execution_events,
                {"type": "stage_start", "stage": "query_analysis"},
            )

            initial_result = self._run_query_analysis(
                query, use_link_prediction, conversation_history
            )

            yield self._emit_event(
                execution_events,
                {
                    "type": "stage_complete",
                    "stage": "query_analysis",
                    "state": initial_result,
                },
            )

            initial_state = self._build_initial_state(
                query=query,
                use_link_prediction=use_link_prediction,
                initial_result=initial_result,
                conversation_history=conversation_history,
            )

            final_state: Dict[str, Any] = initial_state

            for node_updates in self.app.stream(initial_state, stream_mode="updates"):
                if not node_updates:
                    continue

                for node_name, update in node_updates.items():
                    if not update:
                        continue

                    final_state = self._merge_state_update(final_state, update)

                    if node_name == "supervisor":
                        reasoning_log = final_state.get("supervisor_reasoning_log", [])
                        reasoning = reasoning_log[-1] if reasoning_log else ""
                        next_stage = final_state.get("current_stage")

                        yield self._emit_event(
                            execution_events,
                            {
                                "type": "supervisor_decision",
                                "stage": "supervisor",
                                "next_stage": next_stage,
                                "reasoning": reasoning,
                                "state": final_state,
                            },
                        )

                        if next_stage and next_stage != "END":
                            yield self._emit_event(
                                execution_events,
                                {
                                    "type": "stage_start",
                                    "stage": next_stage,
                                    "state": final_state,
                                },
                            )

                            if next_stage == "answer":
                                system_prompt, user_prompt = build_answer_generation_prompt(final_state)
                                answer_parts: List[str] = []

                                for delta in call_llm_stream(
                                    system_prompt=system_prompt,
                                    user_prompt=user_prompt,
                                    temperature=0.5,
                                ):
                                    if not delta:
                                        continue
                                    answer_parts.append(delta)
                                    yield self._emit_event(
                                        execution_events,
                                        {
                                            "type": "answer_token",
                                            "stage": "answer",
                                            "delta": delta,
                                        },
                                    )

                                answer = "".join(answer_parts).strip()
                                answer_update = {
                                    "answer": answer or "답변을 생성하지 못했습니다.",
                                    "sources": collect_answer_sources(final_state.get("sparql_results") or []),
                                    "workflow_path": ["answer_generation"],
                                    "answer_streamed": True,
                                }
                                final_state = self._merge_state_update(final_state, answer_update)

                                yield self._emit_event(
                                    execution_events,
                                    {
                                        "type": "stage_complete",
                                        "stage": "answer",
                                        "state": final_state,
                                    },
                                )

                                result = self._build_result(query, final_state)
                                result["execution_events"] = list(execution_events)
                                yield self._emit_event(
                                    execution_events,
                                    {
                                        "type": "final",
                                        "stage": "END",
                                        "result": result,
                                        "state": final_state,
                                    },
                                )
                                return
                    else:
                        yield self._emit_event(
                            execution_events,
                            {
                                "type": "stage_complete",
                                "stage": node_name,
                                "state": final_state,
                            },
                        )

            result = self._build_result(query, final_state)
            result["execution_events"] = list(execution_events)
            yield self._emit_event(
                execution_events,
                {
                    "type": "final",
                    "stage": "END",
                    "result": result,
                    "state": final_state,
                },
            )

        except Exception as e:
            yield self._emit_event(
                execution_events,
                {
                    "type": "error",
                    "stage": "unknown",
                    "error": str(e),
                },
            )

    def query(
        self,
        query: str,
        use_link_prediction: bool = False,
        conversation_history: Optional[str] = None,
    ) -> Dict[str, Any]:
        """사용자 질의 실행"""
        initial_result = self._run_query_analysis(
            query, use_link_prediction, conversation_history
        )

        # ── 초기 State ──────────────────────────────────────
        initial_state = self._build_initial_state(
            query=query,
            use_link_prediction=use_link_prediction,
            initial_result=initial_result,
            conversation_history=conversation_history,
        )
        
        # ── Supervisor Workflow 실행 ──────────────────────
        final_state = self.app.invoke(initial_state)
        
        # ── 결과 정리 ────────────────────────────────────
        return self._build_result(query, final_state)


def main():
    """테스트"""
    print("=" * 70)
    print("KG Supervisor Agent - Test")
    print("=" * 70)
    
    agent = KGAgentSupervisor()
    
    test_queries = [
        "김철수랑 언제 통화했어?",
        "가장 자주 쓴 앱은?",
    ]
    
    for query in test_queries:
        result = agent.query(query)
        
        print(f"\n{'='*70}")
        print(f"질문: {query}")
        print(f"{'='*70}")
        print("\n[Supervisor Reasoning]")
        for r in result["supervisor_reasoning_log"]:
            print(f"  {r}")
        print(f"\n[Workflow] {' → '.join(result['workflow_path'])}")
        print(f"\n[SPARQL]\n{result.get('sparql_query', '없음')}")
        print(f"\n[결과] {len(result.get('sparql_results', []))}건")
        print(f"\n[답변]\n{result['answer']}")
        print("\n" + "-" * 70)


if __name__ == "__main__":
    main()
