"""
Link Predictor (Inference)

edge_type을 R-GCN forward에 전달하도록 업데이트됨.
노드 임베딩을 미리 계산해 캐싱하고 추론 시 재사용.
"""

import torch
from typing import List, Optional, Tuple

from app.link_prediction.gcn_transe_hybrid import KGLinkPredictor


class LinkPredictor:
    """Inference wrapper for trained R-GCN + TransE KGLinkPredictor"""

    def __init__(
        self,
        model: KGLinkPredictor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        device: str = "cpu"
    ):
        self.model = model.to(device)
        self.edge_index = edge_index.to(device)
        self.edge_type = edge_type.to(device)  # R-GCN forward에 전달
        self.device = device

        # 노드 임베딩 사전 계산 (추론 시 재사용)
        self.model.eval()
        with torch.no_grad():
            self.node_embeddings = self.model(self.edge_index, self.edge_type)

    def predict_missing_tails(
        self,
        head_idx: int,
        rel_idx: int,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Predict missing tail for (head, relation, ?)

        Args:
            head_idx: head node index
            rel_idx: relation index
            top_k: number of predictions

        Returns:
            [(tail_idx, score), ...]  score 높을수록 좋음
        """
        self.model.eval()
        with torch.no_grad():
            top_k_indices, top_k_scores = self.model.predict_tails(
                head_idx, rel_idx, self.node_embeddings, top_k
            )

        return [
            (idx.item(), score.item())
            for idx, score in zip(top_k_indices, top_k_scores)
        ]

    def score_triple(
        self,
        head_idx: int,
        rel_idx: int,
        tail_idx: int
    ) -> float:
        """
        Score a single triple (head, relation, tail).

        Returns:
            score: confidence (higher is better)
        """
        self.model.eval()
        with torch.no_grad():
            score = self.model.score_triple(
                torch.tensor([head_idx], device=self.device),
                torch.tensor([rel_idx], device=self.device),
                torch.tensor([tail_idx], device=self.device),
                self.node_embeddings
            )
        return score.item()
