"""
Link Prediction Pipeline
Sparse detection → Prediction → Augmentation
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import torch
from rdflib import Graph, URIRef, Namespace

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.link_prediction.graph_builder import RDFGraphBuilder
from app.link_prediction.gcn_transe_hybrid import KGLinkPredictor
from app.link_prediction.trainer import LinkPredictionTrainer
from app.link_prediction.predictor import LinkPredictor
from app.config import RDF_OUTPUT_DIR, DATA_DIR


LOG = Namespace("http://example.org/smartphone-log#")
DATA = Namespace("http://example.org/data/")


class LinkPredictionPipeline:
    """End-to-end Link Prediction Pipeline"""
    
    def __init__(
        self,
        rdf_graph: Graph,
        hidden_dim: int = 128,
        num_gcn_layers: int = 3,
        device: str = "cpu"
    ):
        self.rdf_graph = rdf_graph
        self.device = device
        
        # Build PyG graph
        print("[Link Prediction] Building graph from RDF...")
        self.graph_builder = RDFGraphBuilder()
        self.pyg_data = self.graph_builder.build_from_rdf(rdf_graph)
        
        print(f"  Nodes: {self.pyg_data.num_nodes}")
        print(f"  Edges: {self.pyg_data.edge_index.size(1)}")
        print(f"  Relations: {len(self.graph_builder.rel_to_idx)}")
        
        # Initialize model
        self.model = KGLinkPredictor(
            num_nodes=self.pyg_data.num_nodes,
            num_relations=len(self.graph_builder.rel_to_idx),
            hidden_dim=hidden_dim,
            num_gcn_layers=num_gcn_layers
        )
        
        self.trainer = None
        self.predictor = None
        self.is_trained = False
    
    def train(
        self,
        num_epochs: int = 50,
        batch_size: int = 64,
        learning_rate: float = 0.01,
        verbose: bool = True
    ):
        """Train the link prediction model"""
        print(f"\n[Link Prediction] Training for {num_epochs} epochs...")
        
        # Get training triples
        train_triples = self.graph_builder.get_triples(self.pyg_data)
        
        # Initialize trainer
        self.trainer = LinkPredictionTrainer(
            model=self.model,
            edge_index=self.pyg_data.edge_index,
            learning_rate=learning_rate,
            device=self.device
        )
        
        # Train
        self.trainer.train(
            train_triples=train_triples,
            num_epochs=num_epochs,
            batch_size=batch_size,
            verbose=verbose
        )
        
        # Initialize predictor
        self.predictor = LinkPredictor(
            model=self.model,
            edge_index=self.pyg_data.edge_index,
            device=self.device
        )
        
        self.is_trained = True
        print("[Link Prediction] Training complete!")
    
    def detect_sparse(
        self,
        entity_uri: str,
        relation_uris: List[str]
    ) -> Dict[str, bool]:
        """
        Detect if entity has sparse relations
        
        Args:
            entity_uri: URI of entity to check
            relation_uris: List of relation URIs to check
        
        Returns:
            {relation_uri: is_sparse, ...}
        """
        sparse_results = {}
        
        for rel_uri in relation_uris:
            # Query RDF for existing triples
            query = f"""
            SELECT (COUNT(?o) AS ?count)
            WHERE {{
                <{entity_uri}> <{rel_uri}> ?o .
            }}
            """
            
            results = self.rdf_graph.query(query)
            count = 0
            for row in results:
                count = int(row['count'])
            
            # Sparse if count < 1
            sparse_results[rel_uri] = (count < 1)
        
        return sparse_results
    
    def predict_missing_links(
        self,
        head_uri: str,
        relation_uri: str,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Predict missing tail for (head, relation, ?)
        
        Args:
            head_uri: head entity URI
            relation_uri: relation URI
            top_k: number of predictions
        
        Returns:
            [(tail_uri, confidence), ...]
        """
        if not self.is_trained:
            print("[WARNING] Model not trained. Call train() first.")
            return []
        
        # Get indices
        head_idx = self.graph_builder.node_to_idx.get(head_uri)
        rel_idx = self.graph_builder.rel_to_idx.get(relation_uri)
        
        if head_idx is None:
            print(f"[WARNING] Head entity {head_uri} not found in graph")
            return []
        
        if rel_idx is None:
            print(f"[WARNING] Relation {relation_uri} not found in graph")
            return []
        
        # Predict
        predictions = self.predictor.predict_missing_tails(
            head_idx, rel_idx, top_k
        )
        
        # Convert indices to URIs
        results = []
        for tail_idx, confidence in predictions:
            tail_uri = self.graph_builder.node_uri(tail_idx)
            results.append((tail_uri, confidence))
        
        return results
    
    def augment_graph(
        self,
        predicted_triples: List[Tuple[str, str, str, float]]
    ) -> Graph:
        """
        Create augmented RDF graph with predicted triples
        
        Args:
            predicted_triples: [(head_uri, rel_uri, tail_uri, confidence), ...]
        
        Returns:
            augmented_graph: new Graph with original + predicted triples
        """
        augmented = Graph()
        
        # Copy original triples
        for s, p, o in self.rdf_graph:
            augmented.add((s, p, o))
        
        # Add predicted triples
        for head_uri, rel_uri, tail_uri, confidence in predicted_triples:
            head = URIRef(head_uri)
            rel = URIRef(rel_uri)
            tail = URIRef(tail_uri)
            augmented.add((head, rel, tail))
        
        print(f"[Link Prediction] Augmented graph: {len(self.rdf_graph)} → {len(augmented)} triples")
        
        return augmented
    
    def save_model(self, path: str):
        """Save trained model"""
        if self.trainer:
            self.trainer.save_model(path)
            print(f"[Link Prediction] Model saved to {path}")
    
    def load_model(self, path: str):
        """Load trained model"""
        if self.trainer is None:
            # Initialize trainer first
            train_triples = self.graph_builder.get_triples(self.pyg_data)
            self.trainer = LinkPredictionTrainer(
                model=self.model,
                edge_index=self.pyg_data.edge_index,
                device=self.device
            )
        
        self.trainer.load_model(path)
        
        # Initialize predictor
        self.predictor = LinkPredictor(
            model=self.model,
            edge_index=self.pyg_data.edge_index,
            device=self.device
        )
        
        self.is_trained = True
        print(f"[Link Prediction] Model loaded from {path}")


def main():
    """Test pipeline"""
    from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
    from app.config import FUSEKI_URL, FUSEKI_DATASET
    
    print("=" * 70)
    print("Link Prediction Pipeline Test")
    print("=" * 70)
    
    # Load RDF (Fuseki)
    executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
    rdf_file = RDF_OUTPUT_DIR / "generated_data.ttl"
    executor.ensure_data_loaded(rdf_file)
    
    # Initialize pipeline
    pipeline = LinkPredictionPipeline(
        rdf_graph=executor.graph,
        hidden_dim=64,
        num_gcn_layers=2
    )
    
    # Train
    pipeline.train(num_epochs=30, verbose=True)
    
    # Test prediction
    print("\n" + "=" * 70)
    print("Test: Predict missing links")
    print("=" * 70)
    
    # Example: predict visitedAfter for call_003
    head_uri = "http://example.org/data/call_003"
    relation_uri = "http://example.org/smartphone-log#visitedAfter"
    
    predictions = pipeline.predict_missing_links(head_uri, relation_uri, top_k=3)
    
    print(f"\nPredictions for ({head_uri}, {relation_uri}, ?):")
    for tail_uri, confidence in predictions:
        print(f"  - {tail_uri}: {confidence:.4f}")
    
    # Save model
    model_path = DATA_DIR / "models" / "link_predictor.pt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline.save_model(str(model_path))


if __name__ == "__main__":
    main()
