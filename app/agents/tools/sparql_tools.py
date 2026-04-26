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
) -> str:
    """
    Generate SPARQL. When request-scoped predictions exist, bind the predicted
    URIs with VALUES and query only observed properties from Fuseki.
    """
    if predicted_triples:
        sparql = _generate_sparql_from_predictions(
            predicted_triples=predicted_triples,
            prediction_confidence=prediction_confidence or [],
            prediction_evidence=prediction_evidence or [],
            target_relation=target_relation,
        )
        print(f"  [SPARQLTool] SPARQL generated from predictions ({len(sparql)} chars)")
        return sparql

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

    sparql_result = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
    )

    sparql_query = _extract_sparql(sparql_result)
    sparql_query = _fix_label_search(sparql_query)

    print(f"  [SPARQLTool] SPARQL generated ({len(sparql_query)} chars)")
    return sparql_query


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
