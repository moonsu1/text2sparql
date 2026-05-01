"""
R-GCN + TransE 모델 싱글톤 매니저

사용 흐름:
  1. 서버 시작 → ensure_ready() 호출 (백그라운드 학습 or 저장된 모델 로드)
  2. LP 트리거 시 → predict(head_uri, relation_name, top_k) 호출
  3. 결과: [(tail_uri, confidence 0~1), ...]

학습 데이터:
  - Fuseki에서 URI↔URI 트리플 수집 (관측 데이터)
  - weak_supervision.json에서 high-confidence rule-based 쌍 병합 (학습 신호 강화)
  - Fuseki KG는 절대 수정하지 않음

모델 저장: data/models/kg_link_predictor.pt + kg_graph_meta.pt
"""

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
from rdflib import Graph, URIRef

from app.config import DATA_DIR, FUSEKI_DATASET, FUSEKI_URL
from app.link_prediction.gcn_transe_hybrid import KGLinkPredictor
from app.link_prediction.graph_builder import RDFGraphBuilder
from app.link_prediction.predictor import LinkPredictor
from app.link_prediction.trainer import LinkPredictionTrainer

MODEL_PATH = DATA_DIR / "models" / "kg_link_predictor.pt"
META_PATH = DATA_DIR / "models" / "kg_graph_meta.pt"
WEAK_SUPERVISION_PATH = DATA_DIR / "models" / "weak_supervision.json"

LOG_PREFIX = "http://example.org/smartphone-log#"
DATA_PREFIX = "http://example.org/data/"

RELATION_URIS: Dict[str, str] = {
    "visitedAfter": f"{LOG_PREFIX}visitedAfter",
    "metDuring": f"{LOG_PREFIX}metDuring",
    "relatedEvent": f"{LOG_PREFIX}relatedEvent",
    "usedDuring": f"{LOG_PREFIX}usedDuring",
}


class KGModelManager:
    """Singleton: R-GCN+TransE 학습·로드·추론 관리"""

    _instance: Optional["KGModelManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "KGModelManager":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.graph_builder: Optional[RDFGraphBuilder] = None
        self.model: Optional[KGLinkPredictor] = None
        self.predictor: Optional[LinkPredictor] = None
        self.is_ready = False
        self._train_lock = threading.Lock()
        self._edge_type: Optional[torch.Tensor] = None  # 학습/추론용 edge_type 캐싱
        print("[KGModel] Manager 초기화 완료 (아직 학습 전)")

    # ── 외부 API ───────────────────────────────────────────────────────────

    def ensure_ready(self, force_retrain: bool = False) -> bool:
        """모델 준비. 저장된 파일 있으면 로드, 없으면 학습. True=성공."""
        if self.is_ready and not force_retrain:
            return True

        with self._train_lock:
            if self.is_ready and not force_retrain:
                return True

            if not force_retrain and MODEL_PATH.exists() and META_PATH.exists():
                try:
                    self._load_from_disk()
                    return self.is_ready
                except Exception as e:
                    print(f"[KGModel] 로드 실패 ({e}), 재학습합니다.")

            try:
                self._train_from_fuseki()
            except Exception as e:
                print(f"[KGModel] 학습 실패: {e}")
                import traceback
                traceback.print_exc()

        return self.is_ready

    def predict(
        self,
        head_uri: str,
        relation_name: str,
        top_k: int = 5,
        node_type_filter: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        (head, relation, ?) 예측.
        Returns [(tail_uri, confidence 0~1), ...]
        confidence는 softmax 정규화된 값.
        """
        if not self.is_ready or self._edge_type is None:
            return []

        relation_uri = RELATION_URIS.get(relation_name)
        if relation_uri is None:
            return []

        head_idx = self.graph_builder.node_to_idx.get(head_uri)
        rel_idx = self.graph_builder.rel_to_idx.get(relation_uri)

        if head_idx is None:
            return []

        if rel_idx is None:
            # 해당 관계가 훈련 데이터에 없으면 여분 슬롯으로 추론
            print(f"  [KGModel] '{relation_name}' 관계가 학습 데이터에 없음 → 구조 기반 추론")
            rel_idx = self._get_or_create_relation_idx(relation_uri)
            if rel_idx is None:
                return []

        raw_preds = self.predictor.predict_missing_tails(head_idx, rel_idx, top_k * 4)

        # URI 변환 + 타입 필터
        candidates = []
        for tail_idx, raw_score in raw_preds:
            tail_uri = self.graph_builder.idx_to_node.get(tail_idx, "")
            if not tail_uri:
                continue
            if node_type_filter and node_type_filter.lower() not in tail_uri.lower():
                continue
            candidates.append((tail_uri, raw_score))

        if not candidates:
            return []

        # Softmax 정규화 → [0, 1]
        scores_t = torch.tensor([s for _, s in candidates], dtype=torch.float)
        norm = torch.softmax(scores_t, dim=0)
        return [(uri, norm[i].item()) for i, (uri, _) in enumerate(candidates)][:top_k]

    def relation_idx(self, relation_name: str) -> Optional[int]:
        if not self.graph_builder:
            return None
        uri = RELATION_URIS.get(relation_name)
        return self.graph_builder.rel_to_idx.get(uri) if uri else None

    # ── 내부 메서드 ────────────────────────────────────────────────────────

    def _fetch_rdf_from_fuseki(self) -> Graph:
        """Fuseki에서 URI↔URI 트리플을 rdflib Graph로 가져옴."""
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor

        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        sparql = """
        SELECT ?s ?p ?o WHERE {
          ?s ?p ?o .
          FILTER(isIRI(?s) && isIRI(?o))
        }
        """
        rows = executor.execute_query(sparql)
        g = Graph()
        for row in rows:
            g.add((URIRef(row["s"]), URIRef(row["p"]), URIRef(row["o"])))
        print(f"[KGModel] Fuseki에서 {len(g)}개 트리플 수집")
        return g

    def _merge_weak_supervision(self, g: Graph) -> Graph:
        """
        Weak supervision 트리플을 rdflib Graph에 병합.
        Fuseki KG는 건드리지 않고 모델 학습용으로만 사용.
        """
        from app.link_prediction.weak_supervision import (
            generate_weak_supervision,
            load_weak_supervision,
        )

        # 아직 파일이 없으면 생성
        if not WEAK_SUPERVISION_PATH.exists():
            print("[KGModel] Weak supervision 파일 없음 → 새로 생성합니다")
            generate_weak_supervision(WEAK_SUPERVISION_PATH)

        weak_triples = load_weak_supervision(WEAK_SUPERVISION_PATH)
        before = len(g)
        for h, r, t in weak_triples:
            g.add((URIRef(h), URIRef(r), URIRef(t)))

        added = len(g) - before
        print(f"[KGModel] Weak supervision 병합: +{added}개 트리플 (총 {len(g)}개)")
        return g

    def _train_from_fuseki(self) -> None:
        # 1. Fuseki 관측 트리플 수집
        g = self._fetch_rdf_from_fuseki()

        # 2. Weak supervision 병합 (로컬 파일, Fuseki 수정 없음)
        g = self._merge_weak_supervision(g)

        if len(g) == 0:
            print("[KGModel] 트리플 없음 — 학습 건너뜀")
            return

        # 3. PyG 그래프 구성
        self.graph_builder = RDFGraphBuilder()
        pyg = self.graph_builder.build_from_rdf(g)
        n_nodes = pyg.num_nodes
        n_rels = len(self.graph_builder.rel_to_idx)

        print(
            f"[KGModel] 그래프 구성: {n_nodes} 노드 / "
            f"{pyg.edge_index.size(1)} 엣지 / {n_rels} 관계"
        )

        # edge_type 캐싱 (predictor에서 재사용)
        self._edge_type = pyg.edge_type

        # 4. R-GCN 모델 초기화 (sparse relation 슬롯 미리 확보)
        # hidden_dim 128: 표현력 향상 (64→128)
        # num_gcn_layers 3: 2-hop 이웃까지 집계
        self.model = KGLinkPredictor(
            num_nodes=n_nodes,
            num_relations=n_rels + len(RELATION_URIS),
            hidden_dim=128,
            num_gcn_layers=3,
        )

        # 5. 학습
        # num_negatives 10: TransE는 다수 네거티브가 핵심 (1→10)
        # num_epochs 300: 충분한 학습 (50→300)
        # learning_rate 0.005: 안정적 수렴
        trainer = LinkPredictionTrainer(
            model=self.model,
            edge_index=pyg.edge_index,
            edge_type=pyg.edge_type,
            learning_rate=0.005,
            margin=2.0,
        )
        triples = self.graph_builder.get_triples(pyg)
        print(f"[KGModel] 학습 시작: {len(triples)} triples, 300 epochs, negatives=10")
        trainer.train(triples, num_epochs=300, num_negatives=10, verbose=True)

        # 6. 추론기 초기화 (edge_type 전달)
        self.predictor = LinkPredictor(
            model=self.model,
            edge_index=pyg.edge_index,
            edge_type=pyg.edge_type,
        )

        self._save_to_disk(pyg)
        self.is_ready = True
        print("[KGModel] 학습 완료 ✓")

    def _save_to_disk(self, pyg: Any) -> None:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), MODEL_PATH)
        torch.save(
            {
                "node_to_idx": self.graph_builder.node_to_idx,
                "idx_to_node": self.graph_builder.idx_to_node,
                "rel_to_idx": self.graph_builder.rel_to_idx,
                "idx_to_rel": self.graph_builder.idx_to_rel,
                "edge_index": pyg.edge_index,
                "edge_type": pyg.edge_type,
                "num_nodes": pyg.num_nodes,
                "num_relations": self.model.num_relations,
                "hidden_dim": self.model.hidden_dim,
                "num_gcn_layers": len(self.model.gcn_layers),
            },
            META_PATH,
        )
        print(f"[KGModel] 모델 저장: {MODEL_PATH}")

    def _load_from_disk(self) -> None:
        meta: Dict[str, Any] = torch.load(META_PATH, weights_only=False)

        self.graph_builder = RDFGraphBuilder()
        self.graph_builder.node_to_idx = meta["node_to_idx"]
        self.graph_builder.idx_to_node = meta["idx_to_node"]
        self.graph_builder.rel_to_idx = meta["rel_to_idx"]
        self.graph_builder.idx_to_rel = meta["idx_to_rel"]

        edge_index: torch.Tensor = meta["edge_index"]
        edge_type: torch.Tensor = meta.get("edge_type", torch.zeros(edge_index.size(1), dtype=torch.long))
        num_nodes: int = meta["num_nodes"]
        # 저장 시 num_relations (sparse 슬롯 포함)를 그대로 사용 → shape 불일치 방지
        n_rels_observed = len(self.graph_builder.rel_to_idx)
        num_relations: int = meta.get("num_relations", n_rels_observed + len(RELATION_URIS))

        self._edge_type = edge_type

        hidden_dim: int = meta.get("hidden_dim", 128)
        num_gcn_layers: int = meta.get("num_gcn_layers", 3)
        self.model = KGLinkPredictor(
            num_nodes=num_nodes,
            num_relations=num_relations,
            hidden_dim=hidden_dim,
            num_gcn_layers=num_gcn_layers,
        )
        self.model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))

        self.predictor = LinkPredictor(
            model=self.model,
            edge_index=edge_index,
            edge_type=edge_type,
        )
        self.is_ready = True
        print(f"[KGModel] 로드 완료: {num_nodes} 노드, {n_rels_observed} 관계 (모델 슬롯 {num_relations}) ✓")

    def _get_or_create_relation_idx(self, relation_uri: str) -> Optional[int]:
        """
        훈련에 없던 희박 관계에 대해 모델의 여분 슬롯을 사용.
        학습 시 num_relations에 여분을 확보해뒀으므로 안전하게 접근 가능.
        """
        if not self.graph_builder:
            return None
        if relation_uri in self.graph_builder.rel_to_idx:
            return self.graph_builder.rel_to_idx[relation_uri]

        new_idx = len(self.graph_builder.rel_to_idx)
        max_idx = self.model.num_relations - 1
        if new_idx > max_idx:
            print(f"[KGModel] 관계 슬롯 부족 ({new_idx} > {max_idx})")
            return None

        self.graph_builder.rel_to_idx[relation_uri] = new_idx
        self.graph_builder.idx_to_rel[new_idx] = relation_uri
        return new_idx


# 전역 싱글톤
_manager = KGModelManager()


def get_model_manager() -> KGModelManager:
    return _manager
