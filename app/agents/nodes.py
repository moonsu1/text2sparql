"""
LangGraph Workflow Nodes
각 노드의 구현
"""

import sys
from pathlib import Path
from typing import Dict, Any
import yaml
import re
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.agents.state import AgentState
from app.agents.llm_client import call_llm
from app.prompts.text2sparql import (
    TEXT2SPARQL_SYSTEM,
    TEXT2SPARQL_USER_TEMPLATE,
    format_properties_for_prompt
)
from app.prompts.answer_generation import (
    ANSWER_GENERATION_SYSTEM,
    ANSWER_GENERATION_USER_TEMPLATE,
    format_results_for_prompt,
    format_link_prediction_for_prompt
)
from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
from app.config import RDF_OUTPUT_DIR, ONTOLOGY_DIR, CONTACTS, FUSEKI_URL, FUSEKI_DATASET

# Import link prediction
from app.link_prediction.pipeline import LinkPredictionPipeline

# Global executor (한 번만 로드)
_executor = None
_link_prediction_pipeline = None

def get_executor():
    """SPARQL executor 싱글톤 (Fuseki)"""
    global _executor
    if _executor is None:
        _executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        rdf_file = RDF_OUTPUT_DIR / "generated_data.ttl"
        try:
            _executor.ensure_data_loaded(rdf_file)
        except Exception as e:
            print(f"[ERROR] Fuseki 데이터 로드 실패: {e}")
            # Fallback: 연결 없이 계속 진행 (쿼리 시 에러 발생)
    return _executor


def get_link_prediction_pipeline():
    """Link prediction pipeline 싱글톤"""
    global _link_prediction_pipeline
    if _link_prediction_pipeline is None:
        executor = get_executor()
        _link_prediction_pipeline = LinkPredictionPipeline(
            rdf_graph=executor.graph,
            hidden_dim=64,
            num_gcn_layers=2
        )
        # 빠른 학습 (5 epochs만)
        print("[Link Prediction] Quick training (5 epochs)...")
        _link_prediction_pipeline.train(num_epochs=5, verbose=False)
    return _link_prediction_pipeline


def query_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Query Analysis
    LLM으로 사용자 질의 분석
    """
    print("\n[NODE] Query Analysis")
    
    query = state["query"]
    
    # LLM으로 intent, entities, time 추출
    analysis_prompt = f"""다음 질문을 분석하세요:

질문: "{query}"

다음 정보를 JSON 형식으로 추출하세요:
1. intent: 질문의 의도 (recent_calls, most_used_app, visited_places, call_after_cafe, meeting_location, photos_at_place 중 하나)
2. time_constraint: 시간 제약 (어제, 최근, 지난주 등)
3. person_mention: 언급된 사람 이름
4. place_type: 언급된 장소 유형

JSON 형식으로만 답하세요:
{{
  "intent": "...",
  "time_constraint": "...",
  "person_mention": "...",
  "place_type": "..."
}}"""
    
    result = call_llm(
        system_prompt="당신은 질의 분석 전문가입니다.",
        user_prompt=analysis_prompt,
        temperature=0.1
    )
    
    # JSON 파싱 시도
    try:
        import json
        # JSON 추출 (```json ... ``` 형식 처리)
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group(1))
        else:
            # 직접 JSON 파싱 시도
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
            else:
                analysis = {}
    except:
        analysis = {}
    
    intent = analysis.get("intent")
    person_mention = analysis.get("person_mention")
    
    # 한글 이름 → 영어 이름 매핑
    name_mapping = {
        "김철수": "Kim Chul",
        "최대한": "Choi Dae",
        "이영희": "Lee Young",
        "박지민": "Park Ji",
        "정수현": "Jung Su"
    }
    
    # 한글 이름이면 영어로 변환 (부분 매칭)
    if person_mention:
        for kor_name, eng_partial in name_mapping.items():
            if kor_name in person_mention:
                person_mention = eng_partial
                print(f"  [Name Mapping] {kor_name} → {eng_partial}")
                break
    
    entities = {
        "person": person_mention,
        "place_type": analysis.get("place_type")
    }
    
    # 시간 제약 처리
    time_constraint = None
    time_word = analysis.get("time_constraint", "")
    if time_word:
        time_map = {"어제": -1, "그제": -2, "최근": -7, "지난주": -7}
        days_ago = time_map.get(time_word, -7)
        target_date = datetime.now() + timedelta(days=days_ago)
        time_constraint = {
            "word": time_word,
            "date": target_date.date().isoformat(),
            "start_datetime": target_date.replace(hour=0, minute=0).isoformat()
        }
    
    print(f"  Intent: {intent}")
    print(f"  Entities: {entities}")
    
    return {
        "intent": intent,
        "entities": entities,
        "time_constraint": time_constraint,
        "workflow_path": ["query_analysis"]
    }


def sparse_detection_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Sparse Detection
    관련 triple이 부족한지 판단
    """
    print("\n[NODE] Sparse Detection")
    
    # 간단한 휴리스틱: person이 언급되었는데 관련 event가 3개 미만이면 sparse
    executor = get_executor()
    
    person_name = state["entities"].get("person")
    is_sparse = False
    sparse_score = 1.0
    
    if person_name:
        # Person과 관련된 triple 개수 확인
        check_query = f"""
        PREFIX log: <http://example.org/smartphone-log#>
        PREFIX data: <http://example.org/data/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(?event) AS ?count)
        WHERE {{
            ?person rdfs:label "{person_name}" .
            ?event ?p ?person .
        }}
        """
        
        results = executor.execute_query(check_query)
        count = int(results[0].get("count", "0")) if results else 0
        
        threshold = int(os.getenv("SPARSE_THRESHOLD", "3"))
        is_sparse = count < threshold
        sparse_score = count / threshold
        
        print(f"  Related triples: {count}")
        print(f"  Is sparse: {is_sparse}")
    else:
        print("  No person mentioned, not sparse")
    
    return {
        "is_sparse": is_sparse,
        "sparse_score": sparse_score,
        "workflow_path": ["sparse_detection"]
    }


def link_prediction_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2.5: Link Prediction
    Missing link 예측
    """
    print("\n[NODE] Link Prediction")
    
    # Get pipeline
    try:
        pipeline = get_link_prediction_pipeline()
    except Exception as e:
        print(f"  [ERROR] Failed to initialize pipeline: {e}")
        return {
            "workflow_path": ["link_prediction"]
        }
    
    # 예측할 관계 후보 (간단히)
    predicted_triples = []
    confidences = []
    
    # Example: 통화 후 방문 예측
    person_name = state["entities"].get("person")
    if person_name and state.get("is_sparse", False):
        # Find call event for this person
        executor = get_executor()
        query = f"""
        PREFIX log: <http://example.org/smartphone-log#>
        PREFIX data: <http://example.org/data/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?call
        WHERE {{
            ?call a log:CallEvent .
            ?call log:calledPerson ?person .
            ?person rdfs:label "{person_name}" .
        }}
        LIMIT 1
        """
        
        results = executor.execute_query(query)
        
        if results:
            call_uri = results[0].get("call")
            rel_uri = "http://example.org/smartphone-log#visitedAfter"
            
            # Predict
            predictions = pipeline.predict_missing_links(
                head_uri=call_uri,
                relation_uri=rel_uri,
                top_k=3
            )
            
            for tail_uri, confidence in predictions:
                predicted_triples.append((call_uri, rel_uri, tail_uri))
                confidences.append(confidence)
            
            print(f"  Predicted {len(predictions)} triples")
    
    return {
        "predicted_triples": predicted_triples,
        "prediction_confidence": confidences,
        "workflow_path": ["link_prediction"]
    }


def text2sparql_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Text2SPARQL
    LLM으로 SPARQL 생성
    """
    print("\n[NODE] Text2SPARQL (LLM)")
    
    # Property catalog 로드
    catalog_path = ONTOLOGY_DIR / "property_catalog.yaml"
    with open(catalog_path, "r", encoding="utf-8") as f:
        property_catalog = yaml.safe_load(f)
    
    # 관련 properties만 선택 (간단히 모두 포함)
    properties_text = format_properties_for_prompt(list(property_catalog.values()))
    
    # 시간 정보 포맷
    time_info = "없음"
    if state.get("time_constraint"):
        tc = state["time_constraint"]
        time_info = f"{tc['word']} ({tc['date']} 이후)"
    
    # 엔티티 정보 포맷
    entities_text = ", ".join([f"{k}: {v}" for k, v in state["entities"].items() if v])
    if not entities_text:
        entities_text = "없음"
    
    # Additional context (link prediction 결과 포함)
    additional_context = ""
    if state.get("predicted_triples"):
        additional_context = "예측된 관계:\n"
        for triple in state["predicted_triples"]:
            additional_context += f"  - {triple}\n"
    
    # LLM 호출
    system_prompt = TEXT2SPARQL_SYSTEM.format(properties=properties_text)
    user_prompt = TEXT2SPARQL_USER_TEMPLATE.format(
        query=state["query"],
        intent=state.get("intent", "unknown"),
        time_info=time_info,
        entities=entities_text,
        additional_context=additional_context or "없음"
    )
    
    sparql_result = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1
    )
    
    # SPARQL 추출
    sparql_match = re.search(r'```sparql\s*(.*?)\s*```', sparql_result, re.DOTALL)
    if sparql_match:
        sparql_query = sparql_match.group(1).strip()
    else:
        # PREFIX로 시작하는 부분 찾기
        prefix_match = re.search(r'(PREFIX.*)', sparql_result, re.DOTALL)
        if prefix_match:
            sparql_query = prefix_match.group(1).strip()
        else:
            sparql_query = sparql_result.strip()
    
    # ⭐ 후처리: rdfs:label "literal" 패턴을 FILTER(CONTAINS())로 변환
    def fix_label_search(sparql: str) -> str:
        # 패턴: ?var rdfs:label "text" (공백, 점 여부 유연하게)
        pattern = r'(\?\w+)\s+rdfs:label\s+"([^"]+)"\s*\.?'
        
        matches = list(re.finditer(pattern, sparql))
        if matches:
            print(f"  [SPARQL Fix] Found {len(matches)} rdfs:label patterns to fix")
            for match in reversed(matches):  # 뒤에서부터 치환 (인덱스 유지)
                var = match.group(1)
                literal = match.group(2)
                name_var = f"{var}Name"
                
                # 원본 패턴 제거하고 FILTER 패턴으로 교체
                start, end = match.span()
                replacement = f'{var} rdfs:label {name_var} .\n  FILTER(CONTAINS({name_var}, "{literal}"))'
                sparql = sparql[:start] + replacement + sparql[end:]
                print(f"  [SPARQL Fix] {var} rdfs:label \"{literal}\" → CONTAINS")
        
        return sparql
    
    sparql_query = fix_label_search(sparql_query)
    
    print(f"  Generated SPARQL ({len(sparql_query)} chars)")
    
    return {
        "sparql_query": sparql_query,
        "workflow_path": ["text2sparql"]
    }


def execute_sparql_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 4: Execute SPARQL
    SPARQL 쿼리 실행
    """
    print("\n[NODE] Execute SPARQL")
    
    if not state.get("sparql_query"):
        return {
            "error": "SPARQL 쿼리가 생성되지 않았습니다",
            "workflow_path": ["execute_sparql"]
        }
    
    executor = get_executor()
    
    start_time = time.time()
    results = executor.execute_query(state["sparql_query"])
    execution_time = (time.time() - start_time) * 1000
    
    print(f"  Results: {len(results)}개")
    print(f"  Execution time: {execution_time:.2f}ms")
    
    return {
        "sparql_results": results,
        "execution_time_ms": execution_time,
        "workflow_path": ["execute_sparql"]
    }


def answer_generation_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 5: Answer Generation
    LLM으로 자연어 답변 생성
    """
    print("\n[NODE] Answer Generation (LLM)")
    
    # 결과 포맷팅
    results_text = format_results_for_prompt(state.get("sparql_results", []))
    
    # Link prediction 정보
    link_pred_info = format_link_prediction_for_prompt(
        state.get("predicted_triples", []),
        state.get("prediction_confidence", [])
    )
    
    # LLM 호출
    user_prompt = ANSWER_GENERATION_USER_TEMPLATE.format(
        query=state["query"],
        sparql_query=state.get("sparql_query", "없음"),
        results=results_text,
        link_prediction_info=link_pred_info
    )
    
    answer = call_llm(
        system_prompt=ANSWER_GENERATION_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.5
    )
    
    # Sources 추출 (event IDs)
    sources = []
    for result in state.get("sparql_results", []):
        for key, value in result.items():
            if "data/" in str(value):
                event_id = str(value).split("/")[-1]
                if event_id not in sources:
                    sources.append(event_id)
    
    print(f"  Answer generated ({len(answer)} chars)")
    
    return {
        "answer": answer,
        "sources": sources,
        "workflow_path": ["answer_generation"]
    }


# Import time 추가
import time
import os
