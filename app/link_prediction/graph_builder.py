"""
RDF Graph → PyTorch Geometric Data 변환
"""

from typing import Dict, Tuple, List
import torch
from rdflib import Graph


class RDFGraphBuilder:
    """RDF Graph를 PyTorch Geometric Data로 변환"""
    
    def __init__(self):
        self.node_to_idx: Dict[str, int] = {}
        self.idx_to_node: Dict[int, str] = {}
        self.rel_to_idx: Dict[str, int] = {}
        self.idx_to_rel: Dict[int, str] = {}
    
    def build_from_rdf(self, rdf_graph: Graph):  # -> torch_geometric.data.Data
        """
        RDF Graph를 PyG Data로 변환
        
        Returns:
            PyG Data with:
            - edge_index: [2, num_edges] Tensor (source, target)
            - edge_type: [num_edges] Tensor (relation IDs)
            - num_nodes: total node count
        """
        edge_list = []
        edge_types = []
        
        # RDF triples 순회
        for s, p, o in rdf_graph:
            s_str = str(s)
            p_str = str(p)
            o_str = str(o)
            
            # Literal은 노드로 취급하지 않음 (관계만 추출)
            if o_str.startswith("http://") or o_str.startswith("file://"):
                # Subject 노드 인덱싱
                if s_str not in self.node_to_idx:
                    idx = len(self.node_to_idx)
                    self.node_to_idx[s_str] = idx
                    self.idx_to_node[idx] = s_str
                
                # Object 노드 인덱싱
                if o_str not in self.node_to_idx:
                    idx = len(self.node_to_idx)
                    self.node_to_idx[o_str] = idx
                    self.idx_to_node[idx] = o_str
                
                # Relation 인덱싱
                if p_str not in self.rel_to_idx:
                    self.rel_to_idx[p_str] = len(self.rel_to_idx)
                    self.idx_to_rel[len(self.idx_to_rel)] = p_str
                
                # Edge 추가
                src_idx = self.node_to_idx[s_str]
                dst_idx = self.node_to_idx[o_str]
                rel_idx = self.rel_to_idx[p_str]
                
                edge_list.append([src_idx, dst_idx])
                edge_types.append(rel_idx)
        
        # PyG Data 생성 (lazy import으로 circular import 방지)
        from torch_geometric.data import Data

        if not edge_list:
            return Data(
                edge_index=torch.zeros((2, 0), dtype=torch.long),
                edge_type=torch.zeros(0, dtype=torch.long),
                num_nodes=0,
            )

        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        edge_type = torch.tensor(edge_types, dtype=torch.long)

        return Data(
            edge_index=edge_index,
            edge_type=edge_type,
            num_nodes=len(self.node_to_idx),
        )
    
    def get_triples(self, data) -> List[Tuple[int, int, int]]:
        """PyG Data에서 (head, relation, tail) triples 추출"""
        triples = []
        for i in range(data.edge_index.size(1)):
            head = data.edge_index[0, i].item()
            tail = data.edge_index[1, i].item()
            rel = data.edge_type[i].item()
            triples.append((head, rel, tail))
        return triples
    
    def node_uri(self, idx: int) -> str:
        """Node index → URI"""
        return self.idx_to_node.get(idx, "")
    
    def rel_uri(self, idx: int) -> str:
        """Relation index → URI"""
        return self.idx_to_rel.get(idx, "")
