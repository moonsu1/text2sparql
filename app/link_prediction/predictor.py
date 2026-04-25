"""
Link Predictor (Inference)
"""

import torch
from typing import List, Tuple
from app.link_prediction.gcn_transe_hybrid import KGLinkPredictor


class LinkPredictor:
    """Inference wrapper for trained KGLinkPredictor"""
    
    def __init__(
        self,
        model: KGLinkPredictor,
        edge_index: torch.Tensor,
        device: str = "cpu"
    ):
        self.model = model.to(device)
        self.edge_index = edge_index.to(device)
        self.device = device
        
        # Precompute node embeddings
        self.model.eval()
        with torch.no_grad():
            self.node_embeddings = self.model(self.edge_index)
    
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
            [(tail_idx, confidence), ...]
        """
        self.model.eval()
        with torch.no_grad():
            top_k_indices, top_k_scores = self.model.predict_tails(
                head_idx, rel_idx, self.node_embeddings, top_k
            )
        
        results = [
            (idx.item(), score.item())
            for idx, score in zip(top_k_indices, top_k_scores)
        ]
        
        return results
    
    def score_triple(
        self,
        head_idx: int,
        rel_idx: int,
        tail_idx: int
    ) -> float:
        """
        Score a single triple
        
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
