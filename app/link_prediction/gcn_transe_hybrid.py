"""
GCN + TransE Hybrid Model
Graph structure learning (GCN) + Relation translation (TransE)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv
from typing import Tuple


class KGLinkPredictor(nn.Module):
    """
    GCN + TransE Hybrid Model for Link Prediction
    
    - GCN: Learn context-aware node embeddings from graph structure
    - TransE: Learn relation embeddings as translation vectors
    - Scoring: h + r ≈ t (TransE style)
    """
    
    def __init__(
        self,
        num_nodes: int,
        num_relations: int,
        hidden_dim: int = 128,
        num_gcn_layers: int = 3,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.num_nodes = num_nodes
        self.num_relations = num_relations
        self.hidden_dim = hidden_dim
        
        # Node initial embeddings (learnable)
        self.node_init = nn.Embedding(num_nodes, hidden_dim)
        
        # GCN layers
        self.gcn_layers = nn.ModuleList([
            GCNConv(hidden_dim, hidden_dim) for _ in range(num_gcn_layers)
        ])
        
        # Relation embeddings (TransE)
        self.relation_embed = nn.Embedding(num_relations, hidden_dim)
        
        # Dropout
        self.dropout = nn.Dropout(dropout)
        
        # Initialize embeddings
        nn.init.xavier_uniform_(self.node_init.weight)
        nn.init.xavier_uniform_(self.relation_embed.weight)
    
    def forward(self, edge_index):
        """
        GCN forward: compute context-aware node embeddings
        
        Args:
            edge_index: [2, num_edges] Tensor
        
        Returns:
            node_embeddings: [num_nodes, hidden_dim] Tensor
        """
        x = self.node_init.weight
        
        for i, gcn_layer in enumerate(self.gcn_layers):
            x = gcn_layer(x, edge_index)
            if i < len(self.gcn_layers) - 1:
                x = F.relu(x)
                x = self.dropout(x)
        
        return x
    
    def score_triple(
        self,
        head_idx: torch.Tensor,
        rel_idx: torch.Tensor,
        tail_idx: torch.Tensor,
        node_embeddings: torch.Tensor
    ) -> torch.Tensor:
        """
        TransE scoring: h + r ≈ t
        
        Args:
            head_idx: [batch_size] or scalar
            rel_idx: [batch_size] or scalar
            tail_idx: [batch_size] or scalar
            node_embeddings: [num_nodes, hidden_dim]
        
        Returns:
            scores: [batch_size] or scalar (negative L2 distance)
        """
        h = node_embeddings[head_idx]
        r = self.relation_embed(rel_idx)
        t = node_embeddings[tail_idx]
        
        # L2 distance: ||h + r - t||
        score = -torch.norm(h + r - t, p=2, dim=-1)
        
        return score
    
    def predict_tails(
        self,
        head_idx: int,
        rel_idx: int,
        node_embeddings: torch.Tensor,
        top_k: int = 5
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict top-K tail candidates for (head, relation, ?)
        
        Args:
            head_idx: head node index
            rel_idx: relation index
            node_embeddings: [num_nodes, hidden_dim]
            top_k: number of candidates
        
        Returns:
            top_k_indices: [top_k] Tensor (predicted tail indices)
            top_k_scores: [top_k] Tensor (confidence scores)
        """
        h = node_embeddings[head_idx]
        r = self.relation_embed(torch.tensor([rel_idx], device=h.device))
        
        # Predicted tail embedding
        predicted_t = h + r.squeeze(0)
        
        # Distance to all nodes
        distances = torch.norm(
            node_embeddings - predicted_t.unsqueeze(0),
            p=2,
            dim=1
        )
        
        # Top-K smallest distances (most similar)
        top_k_distances, top_k_indices = torch.topk(
            distances,
            k=min(top_k, self.num_nodes),
            largest=False
        )
        
        # Convert distances to confidence scores (higher is better)
        top_k_scores = -top_k_distances
        
        return top_k_indices, top_k_scores

