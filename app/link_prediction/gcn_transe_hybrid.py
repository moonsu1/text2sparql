"""
R-GCN + TransE Hybrid Model

GCN → R-GCN 변경 이유:
  - GCN은 모든 엣지를 동일하게 집계 (callee, place, occurredAt 구분 없음)
  - R-GCN은 관계 타입별로 별도 가중치 행렬 W_r 학습
  - KG는 heterogeneous graph → R-GCN이 구조적으로 더 적합
  - 수식: h_v = σ( Σ_r Σ_{u∈N_r(v)} 1/|N_r(v)| · W_r · h_u + W_0 · h_v )

TransE scoring: h + r ≈ t (관계를 벡터 공간에서 translation으로 모델링)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple


class KGLinkPredictor(nn.Module):
    """
    R-GCN + TransE Hybrid Model for Link Prediction

    - R-GCN: 관계 타입별 가중치로 context-aware 노드 임베딩 학습
    - TransE: 관계 임베딩을 translation 벡터로 학습
    - Scoring: ||h + r - t||_2 (낮을수록 트리플이 타당함)
    """

    def __init__(
        self,
        num_nodes: int,
        num_relations: int,
        hidden_dim: int = 128,
        num_gcn_layers: int = 3,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.num_nodes = num_nodes
        self.num_relations = num_relations
        self.hidden_dim = hidden_dim

        # 노드 초기 임베딩 (학습 가능)
        self.node_init = nn.Embedding(num_nodes, hidden_dim)

        # R-GCN 레이어 (lazy import으로 circular import 방지)
        # FastRGCNConv: 관계 수가 많을 때 메모리 효율적인 R-GCN 변형
        from torch_geometric.nn import FastRGCNConv

        self.gcn_layers = nn.ModuleList([
            FastRGCNConv(hidden_dim, hidden_dim, num_relations)
            for _ in range(num_gcn_layers)
        ])

        # 관계 임베딩 (TransE용)
        self.relation_embed = nn.Embedding(num_relations, hidden_dim)

        self.dropout = nn.Dropout(dropout)

        nn.init.xavier_uniform_(self.node_init.weight)
        nn.init.xavier_uniform_(self.relation_embed.weight)

    def forward(self, edge_index: torch.Tensor, edge_type: torch.Tensor) -> torch.Tensor:
        """
        R-GCN forward: 관계 타입을 반영한 노드 임베딩 계산

        Args:
            edge_index: [2, num_edges] — source/target 인덱스
            edge_type:  [num_edges]   — 각 엣지의 관계 인덱스

        Returns:
            node_embeddings: [num_nodes, hidden_dim]
        """
        x = self.node_init.weight

        for i, rgcn_layer in enumerate(self.gcn_layers):
            x = rgcn_layer(x, edge_index, edge_type)
            if i < len(self.gcn_layers) - 1:
                x = F.relu(x)
                x = self.dropout(x)

        return x

    def score_triple(
        self,
        head_idx: torch.Tensor,
        rel_idx: torch.Tensor,
        tail_idx: torch.Tensor,
        node_embeddings: torch.Tensor,
    ) -> torch.Tensor:
        """
        TransE scoring: h + r ≈ t → score = -||h + r - t||_2

        Returns:
            scores: [batch_size] — 높을수록 타당한 트리플
        """
        h = node_embeddings[head_idx]
        r = self.relation_embed(rel_idx)
        t = node_embeddings[tail_idx]
        return -torch.norm(h + r - t, p=2, dim=-1)

    def predict_tails(
        self,
        head_idx: int,
        rel_idx: int,
        node_embeddings: torch.Tensor,
        top_k: int = 5,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        (head, relation, ?) 예측: top-K tail 후보 반환

        원리: h + r 의 예측 벡터와 모든 노드 임베딩의 L2 거리 계산
              거리가 가장 작은 노드 = 가장 가능성 높은 tail

        Args:
            head_idx: head 노드 인덱스
            rel_idx:  relation 인덱스
            node_embeddings: [num_nodes, hidden_dim]
            top_k: 반환할 후보 수

        Returns:
            top_k_indices: [top_k] — tail 인덱스
            top_k_scores:  [top_k] — score (높을수록 좋음)
        """
        h = node_embeddings[head_idx]
        r = self.relation_embed(torch.tensor([rel_idx], device=h.device))

        # h + r = 예측된 tail 임베딩
        predicted_t = h + r.squeeze(0)

        # 모든 노드와의 거리 계산
        distances = torch.norm(
            node_embeddings - predicted_t.unsqueeze(0),
            p=2,
            dim=1,
        )

        top_k_distances, top_k_indices = torch.topk(
            distances,
            k=min(top_k, self.num_nodes),
            largest=False,  # 가장 짧은 거리 선택
        )

        return top_k_indices, -top_k_distances  # score = -distance
