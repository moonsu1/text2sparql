"""
Request-scoped sparse relation completion tools.

This module does not write predicted triples back to Fuseki. It reads observed
events from Fuseki, scores likely missing relations, and returns predictions
with evidence so the next SPARQL query can bind the predicted URIs explicitly.
"""

import re
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from app.config import FUSEKI_URL, FUSEKI_DATASET


LOG = "http://example.org/smartphone-log#"
DATA = "http://example.org/data/"
CONFIDENCE_THRESHOLD = 0.65

RELATION_URIS = {
    "visitedAfter": f"{LOG}visitedAfter",
    "metDuring": f"{LOG}metDuring",
    "relatedEvent": f"{LOG}relatedEvent",
    "usedDuring": f"{LOG}usedDuring",
}

# 온톨로지가 허용하는 모든 2-hop 경로 정의
# "_rev" suffix = 역방향 탐색 (tail→head 방향으로 연결된 노드 탐색)
MULTIHOP_CHAINS: Dict[str, List[str]] = {
    # Content → VisitEvent → Person
    "relatedEvent+metDuring":        ["relatedEvent",        "metDuring"],
    # CallEvent → VisitEvent → Person
    "visitedAfter+metDuring":        ["visitedAfter",        "metDuring"],
    # CallEvent → VisitEvent ← Content  (2차: VisitEvent에 연결된 Content 역방향 탐색)
    "visitedAfter+relatedEvent_rev": ["visitedAfter",        "relatedEvent_rev"],
    # Content → VisitEvent ← CallEvent  (2차: VisitEvent를 head로 가진 CallEvent 역방향 탐색)
    "relatedEvent+visitedAfter_rev": ["relatedEvent",        "visitedAfter_rev"],
}


def predict_sparse_relations(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    희박 관계 예측. 순서:
      1. GCN+TransE 임베딩 모델 시도
      2. 예측 없으면 rule-based fallback
    """
    relation = state.get("target_relation") or infer_target_relation(state)

    # ── 1. 임베딩 모델 시도 ─────────────────────────────────────────────
    embed_predictions = _predict_with_embedding_model(state, relation)
    if embed_predictions:
        print(f"  [LP] 임베딩 모델 예측 {len(embed_predictions)}건 (relation={relation})")
        return {"target_relation": relation, "predictions": embed_predictions[:3]}

    # ── 2. Rule-based fallback ──────────────────────────────────────────
    print(f"  [LP] 임베딩 예측 없음 → rule-based fallback (relation={relation})")
    predictor = RELATION_COMPLETION_REGISTRY.get(relation)
    if not predictor:
        return {"target_relation": relation, "predictions": []}

    predictions = predictor(state)
    predictions = [
        p
        for p in sorted(
            predictions,
            key=lambda item: (item.get("confidence", 0.0), _prediction_rank_time(item)),
            reverse=True,
        )
        if p.get("confidence", 0.0) >= CONFIDENCE_THRESHOLD
    ]

    return {"target_relation": relation, "predictions": predictions[:3]}


# ── 임베딩 모델 예측 ────────────────────────────────────────────────────────

def _predict_with_embedding_model(
    state: Dict[str, Any], relation: Optional[str]
) -> List[Dict[str, Any]]:
    """
    GCN+TransE 모델로 (head, relation, ?) 예측.
    head 엔티티 목록은 Fuseki에서 조회.
    """
    if not relation:
        return []

    try:
        from app.link_prediction.kg_model_manager import get_model_manager
        mgr = get_model_manager()
        if not mgr.is_ready:
            print("  [LP-embed] 모델 미준비 → skip")
            return []
    except Exception as e:
        print(f"  [LP-embed] 모델 로드 실패: {e}")
        return []

    # 관계별 head 엔티티 조회 + 예측 수행
    if relation == "visitedAfter":
        return _embed_visited_after(state, mgr)
    if relation == "metDuring":
        return _embed_met_during(state, mgr)
    if relation == "relatedEvent":
        return _embed_related_event(state, mgr)
    if relation == "usedDuring":
        return _embed_used_during(state, mgr)

    return []


def _embed_visited_after(state: Dict[str, Any], mgr) -> List[Dict[str, Any]]:
    """CallEvent → (visitedAfter) → VisitEvent 임베딩 예측."""
    person_name = _person_search_name(state)
    person_filter = _contains_filter("?personLabel", person_name) if person_name else ""

    head_rows = _execute_select(f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?call ?callTime ?personLabel WHERE {{
          ?call a log:CallEvent ;
                log:callee ?person ;
                log:startedAt ?callTime .
          ?person rdfs:label ?personLabel .
          {person_filter}
        }}
    """)

    results = []
    for row in head_rows:
        call_uri = row.get("call", "")
        if not call_uri:
            continue

        preds = mgr.predict(call_uri, "visitedAfter", top_k=3, node_type_filter="visit")
        for tail_uri, confidence in preds:
            # tail의 실제 정보 조회
            detail = _fetch_visit_detail(tail_uri)
            if not detail:
                continue
            results.append(_build_evidence(
                row={"call": call_uri, "visit": tail_uri,
                     "callTime": row.get("callTime"), **detail},
                relation="visitedAfter",
                confidence=confidence,
                minutes=0,
                evidence=f"GCN+TransE 임베딩 예측 (신뢰도 {confidence:.2f})",
                head_key="call", tail_key="visit",
                head_label=row.get("personLabel"),
                tail_label=detail.get("placeLabel"),
                timestamps={"callTime": row.get("callTime"),
                            "visitTime": detail.get("visitTime")},
            ))

    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)


def _embed_met_during(state: Dict[str, Any], mgr) -> List[Dict[str, Any]]:
    """VisitEvent → (metDuring) → Person 임베딩 예측."""
    place_keyword = _place_keyword(state)
    place_filter = _contains_filter("?placeLabel", place_keyword) if place_keyword else ""

    head_rows = _execute_select(f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?visit ?visitTime ?placeLabel WHERE {{
          ?visit a log:VisitEvent ;
                 log:visitedAt ?visitTime ;
                 log:place ?place .
          ?place rdfs:label ?placeLabel .
          {place_filter}
        }}
    """)

    results = []
    for row in head_rows:
        visit_uri = row.get("visit", "")
        if not visit_uri:
            continue
        # node_type_filter=None: person URI에 "person" 문자열이 없으므로 필터 없이 예측
        # _fetch_person_detail이 비-person URI를 자동 스킵
        preds = mgr.predict(visit_uri, "metDuring", top_k=5, node_type_filter=None)
        for tail_uri, confidence in preds:
            detail = _fetch_person_detail(tail_uri)
            if not detail:
                continue
            results.append(_build_evidence(
                row={"visit": visit_uri, "person": tail_uri, **row, **detail},
                relation="metDuring",
                confidence=confidence,
                minutes=0,
                evidence=f"GCN+TransE 임베딩 예측 (신뢰도 {confidence:.2f})",
                head_key="visit", tail_key="person",
                head_label=row.get("placeLabel"),
                tail_label=detail.get("personLabel"),
                timestamps={"visitTime": row.get("visitTime")},
            ))
    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)


def _embed_related_event(state: Dict[str, Any], mgr) -> List[Dict[str, Any]]:
    """Content → (relatedEvent) → VisitEvent 임베딩 예측.

    state에서 장소명·날짜를 추출해 head entity를 좁힘으로써
    관련 없는 사진의 높은-confidence 예측이 최상위를 차지하는 문제를 방지.
    """
    place_keyword = _place_keyword(state)
    place_filter = _contains_filter("?placeLabel", place_keyword) if place_keyword else ""

    # 날짜 힌트 추출 (쿼리에 "4월 17일", "4/17" 등)
    date_filter = ""
    query_text = state.get("query", "")
    import re as _re
    date_match = _re.search(r"(\d{1,2})월\s*(\d{1,2})일", query_text)
    if date_match:
        m, d = date_match.group(1).zfill(2), date_match.group(2).zfill(2)
        date_str = f"2026-{m}-{d}"
        date_filter = f'FILTER(STRSTARTS(STR(?capturedAt), "{date_str}"))'

    head_rows = _execute_select(f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?content ?contentLabel ?capturedAt WHERE {{
          ?content a log:Content ;
                   rdfs:label ?contentLabel ;
                   log:capturedAt ?capturedAt .
          OPTIONAL {{ ?content log:capturedPlace ?cp . ?cp rdfs:label ?placeLabel . }}
          {place_filter}
          {date_filter}
        }}
    """)

    results = []
    for row in head_rows:
        content_uri = row.get("content", "")
        if not content_uri:
            continue
        preds = mgr.predict(content_uri, "relatedEvent", top_k=3, node_type_filter="visit")
        for tail_uri, confidence in preds:
            detail = _fetch_visit_detail(tail_uri)
            if not detail:
                continue
            results.append(_build_evidence(
                row={"content": content_uri, "visit": tail_uri, **row, **detail},
                relation="relatedEvent",
                confidence=confidence,
                minutes=0,
                evidence=f"GCN+TransE 임베딩 예측 (신뢰도 {confidence:.2f})",
                head_key="content", tail_key="visit",
                head_label=row.get("contentLabel"),
                tail_label=detail.get("placeLabel"),
                timestamps={"capturedAt": row.get("capturedAt"),
                            "visitTime": detail.get("visitTime")},
            ))
    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)


def _embed_used_during(state: Dict[str, Any], mgr) -> List[Dict[str, Any]]:
    """AppUsageEvent → (usedDuring) → CalendarEvent 임베딩 예측."""
    head_rows = _execute_select(f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?appEvent ?appTime ?appLabel WHERE {{
          ?appEvent a log:AppUsageEvent ;
                    log:occurredAt ?appTime ;
                    log:usedApp ?app .
          ?app rdfs:label ?appLabel .
        }}
    """)

    results = []
    for row in head_rows:
        app_uri = row.get("appEvent", "")
        if not app_uri:
            continue
        # calendar URI는 "cal_XXX" 패턴
        preds = mgr.predict(app_uri, "usedDuring", top_k=3, node_type_filter="cal_")
        for tail_uri, confidence in preds:
            detail = _fetch_calendar_detail(tail_uri)
            if not detail:
                continue
            results.append(_build_evidence(
                row={"appEvent": app_uri, "calendar": tail_uri, **row, **detail},
                relation="usedDuring",
                confidence=confidence,
                minutes=0,
                evidence=f"GCN+TransE 임베딩 예측 (신뢰도 {confidence:.2f})",
                head_key="appEvent", tail_key="calendar",
                head_label=row.get("appLabel"),
                tail_label=detail.get("title"),
                timestamps={"appTime": row.get("appTime"),
                            "startTime": detail.get("startTime")},
            ))
    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)


# ── Fuseki 상세 조회 헬퍼 ────────────────────────────────────────────────────

def _fetch_visit_detail(visit_uri: str) -> Optional[Dict[str, Any]]:
    rows = _execute_select(f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?visitTime ?placeLabel WHERE {{
          <{visit_uri}> log:visitedAt ?visitTime ;
                        log:place ?place .
          ?place rdfs:label ?placeLabel .
        }}
    """)
    return rows[0] if rows else None


def _fetch_person_detail(person_uri: str) -> Optional[Dict[str, Any]]:
    rows = _execute_select(f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?personLabel WHERE {{
          <{person_uri}> rdfs:label ?personLabel .
        }}
    """)
    return rows[0] if rows else None


def _fetch_calendar_detail(cal_uri: str) -> Optional[Dict[str, Any]]:
    rows = _execute_select(f"""
        PREFIX log: <{LOG}>
        SELECT ?title ?startTime WHERE {{
          <{cal_uri}> log:title ?title ;
                      log:startTime ?startTime .
        }}
    """)
    return rows[0] if rows else None


def infer_target_relation(state: Dict[str, Any]) -> Optional[str]:
    """
    Infer the completion relation (or multi-hop chain) from query wording.

    반환값:
    - 단일 관계: "visitedAfter", "metDuring", "relatedEvent", "usedDuring"
    - 2-hop 체인: MULTIHOP_CHAINS의 키 (예: "relatedEvent+metDuring")
    """
    query = (state.get("query") or "").lower()
    entities = state.get("entities") or {}

    # 이미 명시된 관계가 있으면 우선 사용
    explicit = state.get("target_relation")
    if explicit in RELATION_URIS or explicit in MULTIHOP_CHAINS:
        return explicit

    has_photo = any(word in query for word in ["사진", "photo", "찍은", "콘텐츠"])
    has_call_after = any(word in query for word in ["통화", "call"]) and any(
        word in query for word in ["후", "뒤", "나서", "after"]
    )
    has_who = any(word in query for word in ["누구", "만났", "만난", "met"])
    has_place = bool(entities.get("place_type") or entities.get("place_mention"))

    # ── 2-hop 패턴 감지 (1-hop보다 먼저 체크) ───────────────────────────
    # 사진 + 누구 → Content → VisitEvent → Person
    if has_photo and has_who:
        return "relatedEvent+metDuring"
    # 통화 후 + 누구 → CallEvent → VisitEvent → Person
    if has_call_after and has_who and has_place:
        return "visitedAfter+metDuring"
    # 통화 후 + 사진 → CallEvent → VisitEvent ← Content
    if has_call_after and has_photo:
        return "visitedAfter+relatedEvent_rev"
    # 사진 + 통화 (역방향) → Content → VisitEvent ← CallEvent
    if has_photo and any(word in query for word in ["통화", "call"]) and not has_call_after:
        return "relatedEvent+visitedAfter_rev"

    # ── 1-hop 패턴 ────────────────────────────────────────────────────────
    if has_photo:
        return "relatedEvent"
    if any(word in query for word in ["앱", "app", "notion", "slack", "gmail"]):
        return "usedDuring"
    if has_who and has_place:
        return "metDuring"
    if has_call_after:
        return "visitedAfter"

    return None


def predict_second_hop(
    state: Dict[str, Any],
    intermediate_uri: str,
    second_relation: str,
) -> List[Dict[str, Any]]:
    """
    2차 LP: intermediate_uri를 anchor로 고정해 second_relation을 예측.

    - 정방향 (second_relation in RELATION_URIS): intermediate_uri가 head
    - 역방향 (_rev suffix): intermediate_uri가 tail, 연결된 head를 탐색
    """
    is_reverse = second_relation.endswith("_rev")
    base_relation = second_relation.removesuffix("_rev")

    if base_relation not in RELATION_URIS:
        return []

    # ── 임베딩 모델 시도 ────────────────────────────────────────────────
    try:
        from app.link_prediction.kg_model_manager import get_model_manager
        mgr = get_model_manager()
        if mgr.is_ready:
            if base_relation == "metDuring" and not is_reverse:
                # person URI에 "person"이 없으므로 필터 없이 예측 후 _fetch_person_detail로 스킵
                preds = mgr.predict(intermediate_uri, "metDuring", top_k=5, node_type_filter=None)
                results = []
                for tail_uri, confidence in preds:
                    detail = _fetch_person_detail(tail_uri)
                    if not detail:
                        continue
                    results.append(_build_evidence(
                        row={"visit": intermediate_uri, "person": tail_uri, **detail},
                        relation="metDuring",
                        confidence=confidence,
                        minutes=0,
                        evidence=f"GCN+TransE 임베딩 2차 예측 (신뢰도 {confidence:.2f})",
                        head_key="visit",
                        tail_key="person",
                        head_label=_local_id(intermediate_uri),
                        tail_label=detail.get("personLabel"),
                        timestamps={},
                    ))
                if results:
                    print(f"  [LP-2hop] 임베딩 2차 예측 {len(results)}건 (relation={base_relation})")
                    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)

            elif base_relation == "relatedEvent" and is_reverse:
                # VisitEvent를 place 기준으로 Content 역방향 탐색
                # content(사진) URI는 "photo_XXX" 패턴
                preds = mgr.predict(intermediate_uri, "relatedEvent", top_k=3, node_type_filter="photo")
                results = []
                for content_uri, confidence in preds:
                    rows = _execute_select(f"""
                        PREFIX log: <{LOG}>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        SELECT ?contentLabel ?capturedAt WHERE {{
                          <{content_uri}> rdfs:label ?contentLabel ;
                                          log:capturedAt ?capturedAt .
                        }}
                    """)
                    if not rows:
                        continue
                    results.append(_build_evidence(
                        row={"content": content_uri, "visit": intermediate_uri, **rows[0]},
                        relation="relatedEvent",
                        confidence=confidence,
                        minutes=0,
                        evidence=f"GCN+TransE 임베딩 2차 예측 역방향 (신뢰도 {confidence:.2f})",
                        head_key="content",
                        tail_key="visit",
                        head_label=rows[0].get("contentLabel"),
                        tail_label=_local_id(intermediate_uri),
                        timestamps={"capturedAt": rows[0].get("capturedAt")},
                    ))
                if results:
                    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)

            elif base_relation == "visitedAfter" and is_reverse:
                # VisitEvent를 tail로 가진 CallEvent 역방향 탐색
                preds = mgr.predict(intermediate_uri, "visitedAfter", top_k=3, node_type_filter="call")
                results = []
                for call_uri, confidence in preds:
                    rows = _execute_select(f"""
                        PREFIX log: <{LOG}>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        SELECT ?callTime ?personLabel WHERE {{
                          <{call_uri}> log:startedAt ?callTime ;
                                       log:callee ?person .
                          ?person rdfs:label ?personLabel .
                        }}
                    """)
                    if not rows:
                        continue
                    results.append(_build_evidence(
                        row={"call": call_uri, "visit": intermediate_uri, **rows[0]},
                        relation="visitedAfter",
                        confidence=confidence,
                        minutes=0,
                        evidence=f"GCN+TransE 임베딩 2차 예측 역방향 (신뢰도 {confidence:.2f})",
                        head_key="call",
                        tail_key="visit",
                        head_label=rows[0].get("personLabel"),
                        tail_label=_local_id(intermediate_uri),
                        timestamps={"callTime": rows[0].get("callTime")},
                    ))
                if results:
                    return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)
    except Exception as e:
        print(f"  [LP-2hop] 임베딩 2차 예측 실패: {e}")

    # ── Rule-based fallback ───────────────────────────────────────────────
    return _rule_based_second_hop(state, intermediate_uri, base_relation, is_reverse)


def _rule_based_second_hop(
    state: Dict[str, Any],
    intermediate_uri: str,
    base_relation: str,
    is_reverse: bool,
) -> List[Dict[str, Any]]:
    """Rule-based 2차 hop 예측."""
    if base_relation == "metDuring" and not is_reverse:
        # VisitEvent → Person: 방문 시각에 가장 가까운 통화 상대
        visit_rows = _execute_select(f"""
            PREFIX log: <{LOG}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?visitTime ?placeLabel WHERE {{
              <{intermediate_uri}> log:visitedAt ?visitTime ;
                                   log:place ?place .
              ?place rdfs:label ?placeLabel .
            }}
        """)
        if not visit_rows:
            return []
        visit_time = _parse_datetime(visit_rows[0].get("visitTime"))
        if not visit_time:
            return []

        call_rows = _execute_select(f"""
            PREFIX log: <{LOG}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?call ?person ?personLabel ?callTime WHERE {{
              ?call a log:CallEvent ;
                    log:callee ?person ;
                    log:startedAt ?callTime .
              ?person rdfs:label ?personLabel .
            }}
        """)
        results = []
        for row in call_rows:
            call_time = _parse_datetime(row.get("callTime"))
            if not call_time:
                continue
            minutes = _minutes_between(call_time, visit_time)
            if minutes is None or minutes < 0 or minutes > 90:
                continue
            confidence = _time_confidence(minutes)
            results.append(_build_evidence(
                row={"visit": intermediate_uri, "person": row.get("person"), **row},
                relation="metDuring",
                confidence=min(confidence, 0.98),
                minutes=minutes,
                evidence=f"방문 {minutes}분 전 {row.get('personLabel', '?')}과 통화 기록",
                head_key="visit",
                tail_key="person",
                head_label=visit_rows[0].get("placeLabel"),
                tail_label=row.get("personLabel"),
                timestamps={"callTime": row.get("callTime"),
                            "visitTime": visit_rows[0].get("visitTime")},
            ))
        return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)[:3]

    if base_relation == "relatedEvent" and is_reverse:
        # VisitEvent ← Content: 같은 장소·시각대 사진 탐색
        visit_rows = _execute_select(f"""
            PREFIX log: <{LOG}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?visitTime ?placeLabel WHERE {{
              <{intermediate_uri}> log:visitedAt ?visitTime ;
                                   log:place ?place .
              ?place rdfs:label ?placeLabel .
            }}
        """)
        if not visit_rows:
            return []
        visit_time = _parse_datetime(visit_rows[0].get("visitTime"))
        if not visit_time:
            return []
        place_label = visit_rows[0].get("placeLabel", "")

        content_rows = _execute_select(f"""
            PREFIX log: <{LOG}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?content ?contentLabel ?capturedAt ?capturedPlace WHERE {{
              ?content a log:Content ;
                       rdfs:label ?contentLabel ;
                       log:capturedAt ?capturedAt ;
                       log:capturedPlace ?capturedPlace .
              ?capturedPlace rdfs:label ?cPlaceLabel .
              FILTER(CONTAINS(LCASE(STR(?cPlaceLabel)), LCASE("{place_label}")))
            }}
        """)
        results = []
        for row in content_rows:
            captured_at = _parse_datetime(row.get("capturedAt"))
            if not captured_at:
                continue
            minutes = abs(_minutes_between(visit_time, captured_at) or 0)
            if minutes > 60:
                continue
            confidence = 0.97 if minutes <= 10 else 0.85
            results.append(_build_evidence(
                row={"content": row.get("content"), "visit": intermediate_uri, **row},
                relation="relatedEvent",
                confidence=min(confidence, 0.98),
                minutes=minutes,
                evidence=f"사진 촬영 위치가 {place_label}이고 방문 시각과 {minutes}분 차이",
                head_key="content",
                tail_key="visit",
                head_label=row.get("contentLabel"),
                tail_label=visit_rows[0].get("placeLabel"),
                timestamps={"capturedAt": row.get("capturedAt"),
                            "visitTime": visit_rows[0].get("visitTime")},
            ))
        return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)[:3]

    if base_relation == "visitedAfter" and is_reverse:
        # VisitEvent ← CallEvent: 방문 직전 통화 탐색
        visit_rows = _execute_select(f"""
            PREFIX log: <{LOG}>
            SELECT ?visitTime WHERE {{
              <{intermediate_uri}> log:visitedAt ?visitTime .
            }}
        """)
        if not visit_rows:
            return []
        visit_time = _parse_datetime(visit_rows[0].get("visitTime"))
        if not visit_time:
            return []

        call_rows = _execute_select(f"""
            PREFIX log: <{LOG}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?call ?person ?personLabel ?callTime WHERE {{
              ?call a log:CallEvent ;
                    log:callee ?person ;
                    log:startedAt ?callTime .
              ?person rdfs:label ?personLabel .
            }}
        """)
        results = []
        for row in call_rows:
            call_time = _parse_datetime(row.get("callTime"))
            if not call_time:
                continue
            minutes = _minutes_between(call_time, visit_time)
            if minutes is None or minutes < 0 or minutes > 180:
                continue
            confidence = _time_confidence(minutes)
            results.append(_build_evidence(
                row={"call": row.get("call"), "visit": intermediate_uri, **row},
                relation="visitedAfter",
                confidence=min(confidence, 0.98),
                minutes=minutes,
                evidence=f"방문 {minutes}분 전 {row.get('personLabel', '?')}과 통화 기록 (역방향)",
                head_key="call",
                tail_key="visit",
                head_label=row.get("personLabel"),
                tail_label=_local_id(intermediate_uri),
                timestamps={"callTime": row.get("callTime"),
                            "visitTime": visit_rows[0].get("visitTime")},
            ))
        return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)[:3]

    return []


def fetch_candidate_context(
    predictions: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    각 예측 후보에 Fuseki 실제 데이터를 조회해 컨텍스트 텍스트를 추가.

    Returns:
        predictions 리스트에 "fuseki_context" 키가 추가된 사본
    """
    enriched = []
    for pred in predictions:
        parts = []

        tail_label = pred.get("tail_label")
        if tail_label:
            parts.append(f"대상: {tail_label}")

        ts = pred.get("timestamps") or {}
        for key, val in ts.items():
            if val:
                dt = _parse_datetime(val)
                if dt:
                    parts.append(f"{key}: {dt.strftime('%Y-%m-%d %H:%M')}")

        evidence_text = pred.get("evidence", "")
        if evidence_text:
            parts.append(f"근거: {evidence_text}")

        enriched.append({**pred, "fuseki_context": " | ".join(parts)})

    return enriched


def predict_visited_after(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Complete CallEvent --log:visitedAfter--> VisitEvent."""
    query_text = state.get("query") or ""
    person_name = _person_search_name(state)
    date_hint = _date_hint(query_text)
    place_keyword = _place_keyword(state)
    place_type = _place_type(state)

    person_filter = _contains_filter("?personLabel", person_name) if person_name else ""

    rows = _execute_select(
        f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?call ?person ?personLabel ?callTime ?visit ?visitTime ?place ?placeLabel ?placeType
        WHERE {{
          ?call a log:CallEvent ;
                log:callee ?person ;
                log:startedAt ?callTime .
          ?person rdfs:label ?personLabel .
          {person_filter}

          ?visit a log:VisitEvent ;
                 log:visitedAt ?visitTime ;
                 log:place ?place .
          ?place rdfs:label ?placeLabel .
          OPTIONAL {{ ?place log:placeType ?placeType . }}
        }}
        """
    )

    predictions = []
    for row in rows:
        call_time = _parse_datetime(row.get("callTime"))
        visit_time = _parse_datetime(row.get("visitTime"))
        if not call_time or not visit_time:
            continue
        if date_hint and call_time.date() != date_hint and visit_time.date() != date_hint:
            continue

        minutes = _minutes_between(call_time, visit_time)
        if minutes is None or minutes < 0 or minutes > 180:
            continue
        if not _place_matches(row, place_keyword, place_type):
            continue

        confidence = _time_confidence(minutes)
        if place_type and _normalize(row.get("placeType")) == _normalize(place_type):
            confidence += 0.03
        if place_keyword and place_keyword in _normalize(row.get("placeLabel")):
            confidence += 0.04

        evidence = _build_evidence(
            row=row,
            relation="visitedAfter",
            confidence=min(confidence, 0.98),
            minutes=minutes,
            evidence=f"통화 후 {minutes}분 뒤 같은 시간대의 {row.get('placeLabel', '장소')} 방문 기록",
            head_label=row.get("personLabel"),
            tail_label=row.get("placeLabel"),
            timestamps={
                "callTime": row.get("callTime"),
                "visitTime": row.get("visitTime"),
            },
        )
        predictions.append(evidence)

    return predictions


def predict_met_during(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Complete VisitEvent --log:metDuring--> Person."""
    query_text = state.get("query") or ""
    date_hint = _date_hint(query_text)
    place_keyword = _place_keyword(state) or ("스타벅스" if "스타벅스" in query_text else None)
    place_type = _place_type(state)

    rows = _execute_select(
        f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?visit ?visitTime ?place ?placeLabel ?placeType ?call ?callTime ?person ?personLabel
        WHERE {{
          ?visit a log:VisitEvent ;
                 log:visitedAt ?visitTime ;
                 log:place ?place .
          ?place rdfs:label ?placeLabel .
          OPTIONAL {{ ?place log:placeType ?placeType . }}

          ?call a log:CallEvent ;
                log:callee ?person ;
                log:startedAt ?callTime .
          ?person rdfs:label ?personLabel .
        }}
        """
    )

    predictions = []
    for row in rows:
        visit_time = _parse_datetime(row.get("visitTime"))
        call_time = _parse_datetime(row.get("callTime"))
        if not visit_time or not call_time:
            continue
        if date_hint and visit_time.date() != date_hint:
            continue
        if not _place_matches(row, place_keyword, place_type):
            continue

        minutes = _minutes_between(call_time, visit_time)
        if minutes is None or minutes < 0 or minutes > 90:
            continue

        confidence = _time_confidence(minutes)
        if place_keyword and place_keyword in _normalize(row.get("placeLabel")):
            confidence += 0.04

        evidence = _build_evidence(
            row=row,
            relation="metDuring",
            confidence=min(confidence, 0.98),
            minutes=minutes,
            evidence=f"방문 {minutes}분 전 {row.get('personLabel', '상대방')}님과 통화한 기록",
            head_key="visit",
            tail_key="person",
            head_label=row.get("placeLabel"),
            tail_label=row.get("personLabel"),
            timestamps={
                "callTime": row.get("callTime"),
                "visitTime": row.get("visitTime"),
            },
        )
        predictions.append(evidence)

    return predictions


def predict_related_event(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Complete Content --log:relatedEvent--> VisitEvent."""
    query_text = state.get("query") or ""
    date_hint = _date_hint(query_text)
    place_keyword = _place_keyword(state) or ("스타벅스" if "스타벅스" in query_text else None)
    place_type = _place_type(state)

    rows = _execute_select(
        f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?content ?contentLabel ?contentType ?capturedAt ?visit ?visitTime ?place ?placeLabel ?placeType
        WHERE {{
          ?content a log:Content ;
                   rdfs:label ?contentLabel ;
                   log:contentType ?contentType ;
                   log:capturedAt ?capturedAt ;
                   log:capturedPlace ?place .
          ?place rdfs:label ?placeLabel .
          OPTIONAL {{ ?place log:placeType ?placeType . }}

          ?visit a log:VisitEvent ;
                 log:visitedAt ?visitTime ;
                 log:place ?place .
        }}
        """
    )

    predictions = []
    for row in rows:
        captured_at = _parse_datetime(row.get("capturedAt"))
        visit_time = _parse_datetime(row.get("visitTime"))
        if not captured_at or not visit_time:
            continue
        if date_hint and captured_at.date() != date_hint:
            continue
        if not _place_matches(row, place_keyword, place_type):
            continue

        minutes = abs(_minutes_between(visit_time, captured_at) or 0)
        if minutes > 60:
            continue

        confidence = 0.95 if minutes <= 10 else 0.85
        if _normalize(row.get("contentType")) == "photo":
            confidence += 0.02
        if place_keyword and place_keyword in _normalize(row.get("placeLabel")):
            confidence += 0.03

        evidence = _build_evidence(
            row=row,
            relation="relatedEvent",
            confidence=min(confidence, 0.98),
            minutes=minutes,
            evidence=f"사진 촬영 장소가 {row.get('placeLabel', '방문 장소')}이고 방문 시각과 {minutes}분 차이",
            head_key="content",
            tail_key="visit",
            head_label=row.get("contentLabel"),
            tail_label=row.get("placeLabel"),
            timestamps={
                "capturedAt": row.get("capturedAt"),
                "visitTime": row.get("visitTime"),
            },
        )
        predictions.append(evidence)

    return predictions


def predict_used_during(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Complete AppUsageEvent --log:usedDuring--> CalendarEvent."""
    query_text = state.get("query") or ""
    date_hint = _date_hint(query_text)
    title_keyword = _event_title_keyword(state)

    title_filter = _contains_filter("?title", title_keyword) if title_keyword else ""

    rows = _execute_select(
        f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?appEvent ?appTime ?app ?appLabel ?calendar ?title ?startTime ?category
        WHERE {{
          ?appEvent a log:AppUsageEvent ;
                    log:occurredAt ?appTime ;
                    log:usedApp ?app .
          ?app rdfs:label ?appLabel .

          ?calendar a log:CalendarEvent ;
                    log:title ?title ;
                    log:startTime ?startTime .
          OPTIONAL {{ ?calendar log:category ?category . }}
          {title_filter}
        }}
        """
    )

    predictions = []
    for row in rows:
        app_time = _parse_datetime(row.get("appTime"))
        start_time = _parse_datetime(row.get("startTime"))
        if not app_time or not start_time:
            continue
        if date_hint and start_time.date() != date_hint:
            continue

        minutes = _minutes_between(app_time, start_time)
        if minutes is None or minutes < 0 or minutes > 180:
            continue

        app_label = row.get("appLabel", "")
        category = _normalize(row.get("category"))
        confidence = _time_confidence(minutes)
        if _normalize(app_label) in {"notion", "slack", "gmail"}:
            confidence += 0.08
        if category == "work":
            confidence += 0.04
        if title_keyword and title_keyword in _normalize(row.get("title")):
            confidence += 0.04

        evidence = _build_evidence(
            row=row,
            relation="usedDuring",
            confidence=min(confidence, 0.98),
            minutes=minutes,
            evidence=f"{row.get('title', '일정')} 시작 {minutes}분 전 {app_label} 사용 기록",
            head_key="appEvent",
            tail_key="calendar",
            head_label=app_label,
            tail_label=row.get("title"),
            timestamps={
                "appTime": row.get("appTime"),
                "startTime": row.get("startTime"),
            },
        )
        predictions.append(evidence)

    return predictions


def check_sparse_data(person_name: str) -> Dict[str, Any]:
    """Compatibility helper retained for older callers."""
    person_filter = _contains_filter("?label", person_name) if person_name else ""
    rows = _execute_select(
        f"""
        PREFIX log: <{LOG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?event WHERE {{
          ?person a log:Person ;
                  rdfs:label ?label .
          {person_filter}
          ?event ?p ?person .
        }}
        """
    )
    return {"is_sparse": len(rows) < 3, "relation_count": len(rows)}


def predict_missing_links_for_person(
    person_name: str,
    relation_type: str = RELATION_URIS["visitedAfter"],
) -> List[Tuple[str, str, float]]:
    """Compatibility wrapper for the old single-person API."""
    state = {
        "query": f"{person_name} call after visit",
        "target_relation": "visitedAfter",
        "entities": {"person": person_name, "place_type": "cafe"},
        "resolved_entities": {"person": {"label": person_name, "search_name": person_name}},
    }
    predictions = predict_visited_after(state)
    return [
        (prediction["head"], prediction["tail"], prediction["confidence"])
        for prediction in predictions
        if prediction["relation"] == relation_type
    ]


def _build_evidence(
    row: Dict[str, Any],
    relation: str,
    confidence: float,
    minutes: int,
    evidence: str,
    head_key: str = "call",
    tail_key: str = "visit",
    head_label: Optional[str] = None,
    tail_label: Optional[str] = None,
    timestamps: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    head = row.get(head_key, "")
    tail = row.get(tail_key, "")
    relation_uri = RELATION_URIS[relation]
    return {
        "head": head,
        "relation": relation_uri,
        "tail": tail,
        "head_id": _local_id(head),
        "tail_id": _local_id(tail),
        "relation_label": relation,
        "head_label": head_label or _local_id(head),
        "tail_label": tail_label or _local_id(tail),
        "confidence": round(confidence, 2),
        "delta_minutes": minutes,
        "evidence": evidence,
        "timestamps": timestamps or {},
    }


def _execute_select(sparql: str) -> List[Dict[str, Any]]:
    from app.step3_load.fuseki_executor import FusekiSPARQLExecutor

    executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
    return executor.execute_query(sparql)


def _person_search_name(state: Dict[str, Any]) -> Optional[str]:
    resolved = state.get("resolved_entities") or {}
    person = resolved.get("person")
    if isinstance(person, dict):
        return _clean_person_name(person.get("search_name") or person.get("label"))

    entities = state.get("entities") or {}
    return _clean_person_name(entities.get("person"))


def _place_type(state: Dict[str, Any]) -> Optional[str]:
    query = _normalize(state.get("query"))
    entities = state.get("entities") or {}
    raw = entities.get("place_type")
    if raw:
        raw_norm = _normalize(raw)
        if raw_norm in {"cafe", "카페"}:
            return "cafe"
        if raw_norm in {"restaurant", "식당", "음식점"}:
            return "restaurant"
        if raw_norm in {"office", "회사", "오피스"}:
            return "office"
    if "카페" in query or "cafe" in query:
        return "cafe"
    return None


def _place_keyword(state: Dict[str, Any]) -> Optional[str]:
    query = _normalize(state.get("query"))
    entities = state.get("entities") or {}
    for key in ("place_mention", "place_type"):
        value = entities.get(key)
        if value and _normalize(value) not in {"카페", "cafe", "식당", "restaurant", "회사", "office"}:
            return _normalize(value)

    for keyword in ["스타벅스", "투썸", "샐러디", "맥도날드", "강남", "역삼"]:
        if keyword in query:
            return _normalize(keyword)
    return None


def _event_title_keyword(state: Dict[str, Any]) -> Optional[str]:
    query = state.get("query") or ""
    entities = state.get("entities") or {}
    if entities.get("event_title"):
        return _normalize(entities["event_title"])

    known_titles = ["디자인 리뷰", "제품 기획 회의", "전체 회의", "1:1 미팅"]
    for title in known_titles:
        if title in query:
            return _normalize(title)

    if "디자인" in query and "리뷰" in query:
        return "디자인 리뷰"
    return None


def _clean_person_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    english = re.search(r"[A-Za-z][A-Za-z\s.-]*", text)
    if english:
        return english.group(0).strip()
    return text


def _date_hint(query: str) -> Optional[date]:
    if not query:
        return None

    iso_match = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", query)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return date(year, month, day)

    korean_match = re.search(r"(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일", query)
    if korean_match:
        year = int(korean_match.group(1) or 2026)
        month = int(korean_match.group(2))
        day = int(korean_match.group(3))
        return date(year, month, day)

    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if "^^" in text:
        text = text.split("^^", 1)[0].strip('"')
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def _minutes_between(start: datetime, end: datetime) -> Optional[int]:
    if not start or not end:
        return None
    return round((end - start).total_seconds() / 60)


def _time_confidence(minutes: int) -> float:
    if minutes <= 10:
        return 0.95
    if minutes <= 30:
        return 0.90
    if minutes <= 90:
        return 0.78
    if minutes <= 180:
        return 0.68
    return 0.0


def _prediction_rank_time(prediction: Dict[str, Any]) -> float:
    timestamps = prediction.get("timestamps") or {}
    parsed = [_parse_datetime(value) for value in timestamps.values()]
    parsed = [value for value in parsed if value]
    if not parsed:
        return 0.0
    return max(value.timestamp() for value in parsed)


def _place_matches(
    row: Dict[str, Any],
    place_keyword: Optional[str],
    place_type: Optional[str],
) -> bool:
    label = _normalize(row.get("placeLabel"))
    row_type = _normalize(row.get("placeType"))

    if place_keyword and place_keyword not in label:
        return False
    if place_type and row_type and _normalize(place_type) != row_type:
        return False
    return True


def _contains_filter(variable: str, value: Optional[str]) -> str:
    if not value:
        return ""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'FILTER(CONTAINS(LCASE(STR({variable})), LCASE("{escaped}")))'


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _local_id(uri: str) -> str:
    if not uri:
        return ""
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


RELATION_COMPLETION_REGISTRY: Dict[str, Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = {
    "visitedAfter": predict_visited_after,
    "metDuring": predict_met_during,
    "relatedEvent": predict_related_event,
    "usedDuring": predict_used_during,
}
