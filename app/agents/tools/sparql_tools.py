"""
SPARQL generation and validation tools.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from app.agents.llm_client import call_llm
from app.config import ONTOLOGY_DIR
from app.prompts.text2sparql import (
    TEXT2SPARQL_SYSTEM,
    TEXT2SPARQL_USER_TEMPLATE,
    format_properties_for_prompt,
)


LOG = "http://example.org/smartphone-log#"


def generate_sparql(
    query: str,
    intent: str,
    entities_text: str,
    time_info: str,
    predicted_triples: Optional[List[tuple]] = None,
    prediction_confidence: Optional[List[float]] = None,
    prediction_evidence: Optional[List[Dict[str, Any]]] = None,
    target_relation: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Generate SPARQL (and optionally a Mermaid graph).

    Returns:
        (sparql_query, mermaid_graph)  — mermaid_graph is None when generated from predictions
    """
    if predicted_triples:
        sparql = _generate_sparql_from_predictions(
            predicted_triples=predicted_triples,
            prediction_confidence=prediction_confidence or [],
            prediction_evidence=prediction_evidence or [],
            target_relation=target_relation,
        )
        print(f"  [SPARQLTool] SPARQL generated from predictions ({len(sparql)} chars)")
        return sparql, None

    catalog_path = ONTOLOGY_DIR / "property_catalog.yaml"
    with open(catalog_path, "r", encoding="utf-8") as f:
        property_catalog = yaml.safe_load(f)

    properties_text = format_properties_for_prompt(list(property_catalog.values()))

    system_prompt = TEXT2SPARQL_SYSTEM.format(properties=properties_text)
    user_prompt = TEXT2SPARQL_USER_TEMPLATE.format(
        query=query,
        intent=intent or "unknown",
        time_info=time_info or "없음",
        entities=entities_text or "없음",
        additional_context="없음",
    )

    llm_result = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
    )

    sparql_query = _extract_sparql(llm_result)
    sparql_query = _fix_label_search(sparql_query)
    sparql_query = _fix_filter_in_optional(sparql_query)

    mermaid_graph = _extract_mermaid(llm_result)

    print(f"  [SPARQLTool] SPARQL generated ({len(sparql_query)} chars), mermaid={'yes' if mermaid_graph else 'no'}")
    return sparql_query, mermaid_graph


def _generate_sparql_from_predictions(
    predicted_triples: List[tuple],
    prediction_confidence: List[float],
    prediction_evidence: List[Dict[str, Any]],
    target_relation: Optional[str],
) -> str:
    rows = _prediction_rows(predicted_triples, prediction_confidence, prediction_evidence)
    relation = target_relation or _relation_label_from_uri(rows[0]["relation"])

    if relation == "visitedAfter":
        values = _values_block(rows, "?call", "?visit")
        return f"""{_prefixes()}

SELECT ?call ?calleeLabel ?callStartedAt ?visit ?visitTime ?placeLabel ?confidence ?evidence
WHERE {{
  VALUES (?call ?visit ?confidence ?evidence) {{
{values}
  }}
  ?call a log:CallEvent ;
        log:callee ?person ;
        log:startedAt ?callStartedAt .
  ?person rdfs:label ?calleeLabel .
  ?visit a log:VisitEvent ;
         log:visitedAt ?visitTime ;
         log:place ?place .
  ?place rdfs:label ?placeLabel .
}}
ORDER BY DESC(xsd:decimal(?confidence))
"""

    if relation == "metDuring":
        values = _values_block(rows, "?visit", "?person")
        return f"""{_prefixes()}

SELECT ?visit ?visitTime ?placeLabel ?person ?personLabel ?confidence ?evidence
WHERE {{
  VALUES (?visit ?person ?confidence ?evidence) {{
{values}
  }}
  ?visit a log:VisitEvent ;
         log:visitedAt ?visitTime ;
         log:place ?place .
  ?place rdfs:label ?placeLabel .
  ?person rdfs:label ?personLabel .
}}
ORDER BY DESC(xsd:decimal(?confidence))
"""

    if relation == "relatedEvent":
        values = _values_block(rows, "?content", "?visit")
        return f"""{_prefixes()}

SELECT ?content ?contentLabel ?capturedAt ?visit ?visitTime ?placeLabel ?confidence ?evidence
WHERE {{
  VALUES (?content ?visit ?confidence ?evidence) {{
{values}
  }}
  ?content a log:Content ;
           rdfs:label ?contentLabel ;
           log:capturedAt ?capturedAt ;
           log:capturedPlace ?place .
  ?visit a log:VisitEvent ;
         log:visitedAt ?visitTime ;
         log:place ?place .
  ?place rdfs:label ?placeLabel .
}}
ORDER BY DESC(xsd:decimal(?confidence))
"""

    if relation == "usedDuring":
        values = _values_block(rows, "?appEvent", "?calendar")
        return f"""{_prefixes()}

SELECT ?appEvent ?appLabel ?appTime ?calendar ?title ?startTime ?confidence ?evidence
WHERE {{
  VALUES (?appEvent ?calendar ?confidence ?evidence) {{
{values}
  }}
  ?appEvent a log:AppUsageEvent ;
            log:occurredAt ?appTime ;
            log:usedApp ?app .
  ?app rdfs:label ?appLabel .
  ?calendar a log:CalendarEvent ;
            log:title ?title ;
            log:startTime ?startTime .
}}
ORDER BY DESC(xsd:decimal(?confidence))
"""

    values = _values_block(rows, "?head", "?tail")
    return f"""{_prefixes()}

SELECT ?head ?tail ?confidence ?evidence
WHERE {{
  VALUES (?head ?tail ?confidence ?evidence) {{
{values}
  }}
}}
ORDER BY DESC(xsd:decimal(?confidence))
"""


def _prediction_rows(
    predicted_triples: List[tuple],
    prediction_confidence: List[float],
    prediction_evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
    evidence_by_triple = {
        (item.get("head"), item.get("relation"), item.get("tail")): item
        for item in prediction_evidence
        if isinstance(item, dict)
    }
    for index, triple in enumerate(predicted_triples):
        head, relation, tail = triple
        evidence = evidence_by_triple.get((head, relation, tail), {})
        confidence = evidence.get("confidence")
        if confidence is None and index < len(prediction_confidence):
            confidence = prediction_confidence[index]
        rows.append(
            {
                "head": head,
                "relation": relation,
                "tail": tail,
                "confidence": float(confidence if confidence is not None else 0.0),
                "evidence": evidence.get("evidence", "request-scoped predicted relation"),
            }
        )
    return rows


def _values_block(rows: List[Dict[str, Any]], head_var: str, tail_var: str) -> str:
    del head_var, tail_var
    lines = []
    for row in rows:
        confidence = f"{row['confidence']:.2f}"
        evidence = _sparql_literal(row["evidence"])
        lines.append(f"    (<{row['head']}> <{row['tail']}> \"{confidence}\" {evidence})")
    return "\n".join(lines)


def _prefixes() -> str:
    return f"""PREFIX log: <{LOG}>
PREFIX data: <http://example.org/data/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"""


def _sparql_literal(value: Any) -> str:
    text = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _relation_label_from_uri(uri: str) -> str:
    return str(uri or "").rstrip("/").rsplit("#", 1)[-1]


def _extract_sparql(llm_output: str) -> str:
    sparql_match = re.search(r"```sparql\s*(.*?)\s*```", llm_output, re.DOTALL)
    if sparql_match:
        return sparql_match.group(1).strip()

    prefix_match = re.search(r"(PREFIX.*)", llm_output, re.DOTALL)
    if prefix_match:
        return prefix_match.group(1).strip()

    return llm_output.strip()


def _extract_mermaid(llm_output: str) -> Optional[str]:
    """LLM 응답에서 ```mermaid 블록을 추출 후 후처리. 없으면 None."""
    mermaid_match = re.search(r"```mermaid\s*(.*?)\s*```", llm_output, re.DOTALL)
    if mermaid_match:
        content = mermaid_match.group(1).strip()
        if content:
            return _fix_mermaid(content)
    return None


# 엣지 레이블 영→한 매핑
_EDGE_LABEL_KO: dict[str, str] = {
    "callee": "수신자",
    "caller": "발신자",
    "startedAt": "통화시각",
    "visitedAt": "방문시각",
    "place": "장소",
    "placeType": "장소유형",
    "app": "앱",
    "usedAt": "사용시각",
    "takenAt": "촬영시각",
    "content": "콘텐츠",
    "attendee": "참석자",
    "location": "위치",
    "durationSeconds": "통화시간",
    "linkedTo": "연결",
    "visitedAfter": "통화후방문",
    "afterCall": "통화후방문",
    "temporalOrder": "시간순서",
    "type": "유형",
    "label": "이름",
}

# 노드 레이블 키워드 → Mermaid 클래스명
_NODE_TYPE_CLASS: list[tuple[str, str]] = [
    ("CallEvent",     "clsCall"),
    ("VisitEvent",    "clsVisit"),
    ("AppUsageEvent", "clsApp"),
    ("CalendarEvent", "clsCal"),
    ("Person",        "clsPerson"),
    ("User",          "clsPerson"),
    ("Cafe",          "clsPlace"),
    ("Restaurant",    "clsPlace"),
    ("Office",        "clsPlace"),
    ("Home",          "clsPlace"),
    ("Place",         "clsPlace"),
    ("App",           "clsAppNode"),
    ("Content",       "clsContent"),
    ("datetime",      "clsLiteral"),
    ("duration",      "clsLiteral"),
]

_CLASS_STYLES: dict[str, str] = {
    "clsCall":    "fill:#D6E8FA,stroke:#7AAED6,stroke-width:1px,color:#2C4A6E",
    "clsVisit":   "fill:#D4EDDA,stroke:#7EC898,stroke-width:1px,color:#1E4A2E",
    "clsApp":     "fill:#FFF3CD,stroke:#F0C060,stroke-width:1px,color:#5A3E00",
    "clsCal":     "fill:#E8D5F5,stroke:#B78FD6,stroke-width:1px,color:#4A2070",
    "clsPerson":  "fill:#FAD7D7,stroke:#E89090,stroke-width:1px,color:#6E1F1F",
    "clsPlace":   "fill:#C8F0EA,stroke:#70C8B8,stroke-width:1px,color:#1A4A40",
    "clsAppNode": "fill:#FDE8C8,stroke:#E0A860,stroke-width:1px,color:#5A3000",
    "clsContent": "fill:#FAD0E4,stroke:#E890B8,stroke-width:1px,color:#6E1840",
    "clsLiteral": "fill:#F0F0F0,stroke:#C0C0C0,stroke-width:1px,color:#555555",
}


def _fix_mermaid(mermaid: str) -> str:
    """
    Mermaid 후처리:
    1. \\n → 공백, 큰따옴표 내 줄바꿈 → 공백
    2. (( )) 원형 노드 → [ ] 직사각형
    3. call* 노드 ID → ev0, ev1... rename  (CALLBACKNAME 파싱 오류 방지)
    4. 엣지 레이블 영→한 번역
    5. 노드 타입별 색상 classDef 추가
    6. 엣지 레이블 배경 색상 init 추가
    """
    # ── 1. 줄바꿈 정리 ──────────────────────────────────────────────
    mermaid = mermaid.replace("\\n", " ")

    def flatten_label(m: re.Match) -> str:
        return m.group(0).replace("\n", " ")
    mermaid = re.sub(r'"[^"]*"', flatten_label, mermaid)

    # ── 2. (( )) → [ ] ─────────────────────────────────────────────
    mermaid = re.sub(r'\(\("([^"]*)"\)\)', r'["\1"]', mermaid)
    mermaid = re.sub(r"\(\(([^)]*)\)\)", r"[\1]", mermaid)

    # ── 3. call* 노드 ID rename ──────────────────────────────────────
    # 엣지 레이블 |...|을 먼저 보호 (call* 치환 대상에서 제외)
    edge_placeholders: list[str] = []

    def protect_edge(m: re.Match) -> str:
        edge_placeholders.append(m.group(0))
        return f"__EL{len(edge_placeholders) - 1}__"

    mermaid = re.sub(r'\|[^|\n]*\|', protect_edge, mermaid)

    call_id_map: dict[str, str] = {}
    ev_counter = [0]

    def rename_call_id(m: re.Match) -> str:
        orig = m.group(0)
        if orig not in call_id_map:
            call_id_map[orig] = f"ev{ev_counter[0]}"
            ev_counter[0] += 1
        return call_id_map[orig]

    mermaid = re.sub(r'\bcall\w*', rename_call_id, mermaid)

    # 엣지 레이블 복원
    for i, lbl in enumerate(edge_placeholders):
        mermaid = mermaid.replace(f"__EL{i}__", lbl)

    # ── 4. 엣지 레이블 영→한 번역 ────────────────────────────────────
    def translate_edge(m: re.Match) -> str:
        inner = m.group(1).strip().strip('"')
        ko = _EDGE_LABEL_KO.get(inner, inner)
        return f'|"{ko}"|'

    mermaid = re.sub(r'\|"?([A-Za-z]\w*)"?\|', translate_edge, mermaid)

    # ── 5. 노드 타입별 색상 classDef ─────────────────────────────────
    node_class: dict[str, str] = {}
    for match in re.finditer(r'(\w+)\["([^"]+)"\]', mermaid):
        node_id = match.group(1)
        label = match.group(2)
        for keyword, cls in _NODE_TYPE_CLASS:
            if keyword.lower() in label.lower():
                node_class[node_id] = cls
                break

    style_lines: list[str] = []
    used_classes = set(node_class.values())
    for cls, style in _CLASS_STYLES.items():
        if cls in used_classes:
            style_lines.append(f"  classDef {cls} {style}")

    class_groups: dict[str, list[str]] = {}
    for nid, cls in node_class.items():
        class_groups.setdefault(cls, []).append(nid)
    for cls, nodes in class_groups.items():
        style_lines.append(f"  class {','.join(nodes)} {cls}")

    if style_lines:
        mermaid = mermaid.rstrip() + "\n" + "\n".join(style_lines)

    # ── 6. 엣지 레이블 → 중간 pill 노드로 변환 ─────────────────────────
    mermaid = _reify_edge_labels(mermaid)

    # ── 7. 엣지 레이블 배경 흰색 init ────────────────────────────────
    init_line = '%%{init: {"themeVariables": {"edgeLabelBackground": "#ffffff"}}}%%'
    if not mermaid.startswith("%%"):
        mermaid = init_line + "\n" + mermaid

    return mermaid


def _reify_edge_labels(mermaid: str) -> str:
    """
    |label| 엣지 레이블을 중간 pill 노드로 변환해서 선과 겹치지 않게 함.

    Before:  A -->|"수신자"| B
    After:   A --> _r0(["수신자"]) --> B

    Before:  A -.->|"통화후방문"| B
    After:   A -.-> _r0(["통화후방문"]) -.-> B
    """
    # Node ref: word optionally followed by ["..."]  e.g.  ev1  or  ev1["CallEvent"]
    NODE = r'(\w+(?:\["[^"]*"\])?)'
    LABEL = r'\|"?([^"|]+)"?\|'
    solid_re = re.compile(rf'^\s*{NODE}\s*(-->){LABEL}{NODE}\s*$')
    dash_re  = re.compile(rf'^\s*{NODE}\s*(-\.->){LABEL}{NODE}\s*$')

    lines = mermaid.split('\n')
    result: list[str] = []
    rel_nodes: list[str] = []
    counter = [0]

    for line in lines:
        matched = False
        for pattern in (solid_re, dash_re):
            m = pattern.match(line)
            if m:
                src, arrow, label, dst = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
                rid = f'_r{counter[0]}'
                counter[0] += 1
                rel_nodes.append(rid)
                result.append(f'  {src} {arrow} {rid}(["{label}"]) {arrow} {dst}')
                matched = True
                break
        if not matched:
            result.append(line)

    if rel_nodes:
        node_list = ','.join(rel_nodes)
        result.append(f'  classDef clsRel fill:#F5F5F5,stroke:#BBBBBB,stroke-width:1px,color:#555555')
        result.append(f'  class {node_list} clsRel')

    return '\n'.join(result)


def _fix_filter_in_optional(sparql: str) -> str:
    """
    OPTIONAL 블록 안에 FILTER가 있으면 해당 OPTIONAL 전체를 필수 패턴으로 변환합니다.

    Qwen 등 소형 모델이 자주 저지르는 패턴:
        OPTIONAL {
            ?x prop ?y .
            FILTER(?y > ?z)   ← FILTER가 있으면 이 블록은 필수 조건이어야 함
        }

    수정 결과 (OPTIONAL 제거 → 필수 패턴):
        ?x prop ?y .
        FILTER(?y > ?z)

    FILTER가 없는 OPTIONAL은 그대로 유지합니다.
    """
    filter_re = re.compile(r'FILTER\s*\(', re.IGNORECASE)
    optional_re = re.compile(r'OPTIONAL\s*\{([^{}]*)\}', re.DOTALL | re.IGNORECASE)
    fixed = False

    def replace_optional(m: re.Match) -> str:
        nonlocal fixed
        inner = m.group(1)
        if filter_re.search(inner):
            # FILTER가 있는 OPTIONAL → OPTIONAL 래퍼 제거, 내용만 남김
            fixed = True
            return inner.strip()
        return m.group(0)

    result = optional_re.sub(replace_optional, sparql)

    if fixed:
        print("  [SPARQLTool] FILTER-in-OPTIONAL 패턴 감지 → OPTIONAL 제거, 필수 패턴으로 변환 완료")

    return result


def _fix_label_search(sparql: str) -> str:
    """Convert exact rdfs:label literal patterns into CONTAINS filters."""
    pattern = r'(\?\w+)\s+rdfs:label\s+"([^"]+)"\s*\.?'

    matches = list(re.finditer(pattern, sparql))
    for match in reversed(matches):
        var = match.group(1)
        literal = match.group(2)
        name_var = f"{var}Name"
        start, end = match.span()
        replacement = f'{var} rdfs:label {name_var} .\n  FILTER(CONTAINS({name_var}, "{literal}"))'
        sparql = sparql[:start] + replacement + sparql[end:]

    return sparql


def verify_sparql_syntax(sparql: str) -> Dict[str, Any]:
    """Lightweight SPARQL syntax sanity check."""
    if not sparql or not sparql.strip():
        return {"is_valid": False, "error": "empty SPARQL query"}

    sparql_upper = sparql.upper()
    if "SELECT" not in sparql_upper and "ASK" not in sparql_upper and "CONSTRUCT" not in sparql_upper:
        return {"is_valid": False, "error": "missing SELECT/ASK/CONSTRUCT"}

    if "WHERE" not in sparql_upper:
        return {"is_valid": False, "error": "missing WHERE"}

    open_count = sparql.count("{")
    close_count = sparql.count("}")
    if open_count != close_count:
        return {
            "is_valid": False,
            "error": f"brace mismatch: {open_count} open, {close_count} close",
        }

    return {"is_valid": True, "error": None}
