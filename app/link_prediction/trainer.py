"""
Training Pipeline for R-GCN + TransE Hybrid Model

edge_type을 R-GCN forward에 전달하도록 업데이트됨.
"""

import torch
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from typing import List, Tuple
import random

from app.link_prediction.gcn_transe_hybrid import KGLinkPredictor
from app.link_prediction.negative_sampling import batch_negative_sampling


class LinkPredictionTrainer:
    """Trainer for R-GCN + TransE Hybrid model"""

    def __init__(
        self,
        model: KGLinkPredictor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        learning_rate: float = 0.01,
        margin: float = 1.0,
        device: str = "cpu"
    ):
        self.model = model.to(device)
        self.edge_index = edge_index.to(device)
        self.edge_type = edge_type.to(device)   # R-GCN forward에 전달
        self.device = device
        self.margin = margin

        self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    def train_epoch(
        self,
        train_triples: List[Tuple[int, int, int]],
        batch_size: int = 64,
        num_negatives: int = 1
    ) -> float:
        """
        Train for one epoch.

        R-GCN forward에서 edge_type을 사용하여 관계별 다른 가중치로 집계.

        Args:
            train_triples: [(head, rel, tail), ...]
            batch_size: batch size
            num_negatives: negative samples per positive

        Returns:
            avg_loss: average loss for this epoch
        """
        self.model.train()

        random.shuffle(train_triples)

        heads = torch.tensor([t[0] for t in train_triples], dtype=torch.long)
        rels = torch.tensor([t[1] for t in train_triples], dtype=torch.long)
        tails = torch.tensor([t[2] for t in train_triples], dtype=torch.long)

        dataset = TensorDataset(heads, rels, tails)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        total_loss = 0.0
        num_batches = 0

        for batch_heads, batch_rels, batch_tails in dataloader:
            batch_heads = batch_heads.to(self.device)
            batch_rels = batch_rels.to(self.device)
            batch_tails = batch_tails.to(self.device)

            # R-GCN forward: edge_type 전달 → 관계별 가중치로 노드 임베딩 계산
            node_embeddings = self.model(self.edge_index, self.edge_type)

            # Positive scores
            pos_scores = self.model.score_triple(
                batch_heads, batch_rels, batch_tails, node_embeddings
            )

            # Negative sampling
            neg_heads, neg_rels, neg_tails = batch_negative_sampling(
                batch_heads, batch_rels, batch_tails,
                self.model.num_nodes, num_negatives
            )

            # Negative scores
            neg_scores = self.model.score_triple(
                neg_heads, neg_rels, neg_tails, node_embeddings
            )

            # Margin ranking loss: pos_score > neg_score + margin
            loss = torch.relu(self.margin - pos_scores + neg_scores).mean()

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()
            num_batches += 1

        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        return avg_loss

    def train(
        self,
        train_triples: List[Tuple[int, int, int]],
        num_epochs: int = 100,
        batch_size: int = 64,
        num_negatives: int = 1,
        verbose: bool = True
    ):
        """
        Full training loop.

        Args:
            train_triples: training triples
            num_epochs: number of epochs
            batch_size: batch size
            num_negatives: negative samples per positive
            verbose: print progress
        """
        for epoch in range(num_epochs):
            loss = self.train_epoch(train_triples, batch_size, num_negatives)

            if verbose and (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{num_epochs}, Loss: {loss:.4f}")

    def save_model(self, path: str):
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
        }, path)

    def load_model(self, path: str):
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
