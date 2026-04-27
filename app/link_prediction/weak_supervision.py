"""
Weak Supervision 생성기

역할:
  - Rule-based predictor 함수를 "teacher"로 활용
  - confidence >= THRESHOLD인 고신뢰도 쌍만 weak positive로 선별
  - data/models/weak_supervision.json에 저장

왜 Fuseki가 아닌 로컬 파일에 저장하는가?
  - Fuseki = 실제 KG (희박한 상태) → 면접 시나리오 유지
  - 로컬 파일 = 모델 학습 전용 → KG와 분리됨을 명확히 설명 가능
  - "KG에는 없지만 rule-based로 뽑은 high-confidence 쌍을 weak positive로 활용"

사용 시점:
  kg_model_manager._train_from_fuseki() 학습 직전에 자동 호출됨
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

LOG_PREFIX = "http://example.org/smartphone-log#"
DATA_PREFIX = "http://example.org/data/"

CONFIDENCE_THRESHOLD = 0.80  # 이 이상만 weak positive로 사용

RELATION_URIS: Dict[str, str] = {
    "visitedAfter": f"{LOG_PREFIX}visitedAfter",
    "metDuring": f"{LOG_PREFIX}metDuring",
    "relatedEvent": f"{LOG_PREFIX}relatedEvent",
    "usedDuring": f"{LOG_PREFIX}usedDuring",
}


def generate_weak_supervision(output_path: Path) -> List[Dict[str, Any]]:
    """
    4개 희박 관계에 대해 rule-based predictor를 teacher로 사용하여
    high-confidence weak positive 트리플을 생성하고 JSON 파일로 저장.

    Returns:
        저장된 weak supervision 트리플 목록
    """
    try:
        from app.agents.tools.link_prediction_tools import (
            predict_visited_after,
            predict_met_during,
            predict_related_event,
            predict_used_during,
        )
    except ImportError as e:
        logger.warning(f"[WeakSup] rule-based predictor import 실패: {e}")
        return []

    # 각 관계별 빈 state로 전체 후보를 뽑아냄
    base_state: Dict[str, Any] = {
        "query": "",
        "entities": {},
        "resolved_entities": {},
        "target_relation": None,
    }

    registry = [
        ("visitedAfter", predict_visited_after),
        ("metDuring", predict_met_during),
        ("relatedEvent", predict_related_event),
        ("usedDuring", predict_used_during),
    ]

    weak_triples: List[Dict[str, Any]] = []

    for relation_name, predictor_fn in registry:
        state = {**base_state, "target_relation": relation_name}
        try:
            predictions = predictor_fn(state)
        except Exception as e:
            logger.warning(f"[WeakSup] {relation_name} 예측 실패: {e}")
            continue

        added = 0
        for pred in predictions:
            conf = pred.get("confidence", 0.0)
            if conf < CONFIDENCE_THRESHOLD:
                continue
            head = pred.get("head", "")
            tail = pred.get("tail", "")
            if not head or not tail:
                continue

            weak_triples.append({
                "head": head,
                "relation": RELATION_URIS[relation_name],
                "tail": tail,
                "relation_name": relation_name,
                "confidence": round(conf, 3),
                "evidence": pred.get("evidence", ""),
                "source": "weak_supervision",
            })
            added += 1

        logger.info(f"[WeakSup] {relation_name}: {added}개 high-conf 쌍 생성")

    # 파일 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(weak_triples, f, ensure_ascii=False, indent=2)

    total = len(weak_triples)
    logger.info(f"[WeakSup] 총 {total}개 트리플 저장: {output_path}")
    print(f"[WeakSup] Weak supervision 생성 완료: {total}건 → {output_path}")
    return weak_triples


def load_weak_supervision(path: Path) -> List[Tuple[str, str, str]]:
    """
    저장된 weak supervision JSON을 로드해 (head, relation, tail) 튜플 목록으로 반환.

    Args:
        path: weak_supervision.json 경로

    Returns:
        [(head_uri, relation_uri, tail_uri), ...]
    """
    if not path.exists():
        logger.info(f"[WeakSup] 파일 없음: {path}")
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"[WeakSup] 로드 실패: {e}")
        return []

    triples = []
    for item in data:
        h = item.get("head", "")
        r = item.get("relation", "")
        t = item.get("tail", "")
        if h and r and t:
            triples.append((h, r, t))

    logger.info(f"[WeakSup] {len(triples)}개 트리플 로드: {path}")
    return triples
