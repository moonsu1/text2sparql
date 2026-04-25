"""
Negative Sampling for Link Prediction Training
"""

import random
from typing import List, Tuple, Set
import torch


def generate_negative_samples(
    positive_triples: List[Tuple[int, int, int]],
    num_nodes: int,
    num_negatives_per_positive: int = 1
) -> List[Tuple[int, int, int]]:
    """
    Negative sampling by corrupting tail entities
    
    Args:
        positive_triples: [(head, relation, tail), ...]
        num_nodes: total number of nodes
        num_negatives_per_positive: number of negative samples per positive
    
    Returns:
        negative_triples: [(head, relation, corrupted_tail), ...]
    """
    # Positive set for checking
    positive_set: Set[Tuple[int, int, int]] = set(positive_triples)
    
    negative_triples = []
    
    for h, r, t in positive_triples:
        for _ in range(num_negatives_per_positive):
            # Corrupt tail
            attempts = 0
            max_attempts = 50
            
            while attempts < max_attempts:
                corrupted_t = random.randint(0, num_nodes - 1)
                
                # Ensure not in positive set
                if (h, r, corrupted_t) not in positive_set:
                    negative_triples.append((h, r, corrupted_t))
                    break
                
                attempts += 1
            
            # If failed to find negative, use random anyway
            if attempts == max_attempts:
                corrupted_t = random.randint(0, num_nodes - 1)
                negative_triples.append((h, r, corrupted_t))
    
    return negative_triples


def batch_negative_sampling(
    batch_heads: torch.Tensor,
    batch_rels: torch.Tensor,
    batch_tails: torch.Tensor,
    num_nodes: int,
    num_negatives: int = 1
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Batch negative sampling (for faster training)
    
    Args:
        batch_heads: [batch_size] Tensor
        batch_rels: [batch_size] Tensor
        batch_tails: [batch_size] Tensor
        num_nodes: total nodes
        num_negatives: negatives per positive
    
    Returns:
        neg_heads, neg_rels, neg_tails
    """
    batch_size = batch_heads.size(0)
    
    # Repeat positive heads and relations
    neg_heads = batch_heads.repeat_interleave(num_negatives)
    neg_rels = batch_rels.repeat_interleave(num_negatives)
    
    # Generate random corrupted tails
    neg_tails = torch.randint(
        0, num_nodes,
        (batch_size * num_negatives,),
        device=batch_heads.device
    )
    
    return neg_heads, neg_rels, neg_tails
