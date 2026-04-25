"""
RDF Utilities
RDF triple 생성을 위한 유틸리티 함수들
"""

from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, XSD
from rdflib.namespace import PROV
from datetime import datetime
from typing import Optional, Union


# 네임스페이스 정의
LOG = Namespace("http://example.org/smartphone-log#")
DATA = Namespace("http://example.org/data/")


class RDFBuilder:
    """RDF Graph 빌더"""
    
    def __init__(self):
        self.graph = Graph()
        self._bind_namespaces()
    
    def _bind_namespaces(self):
        """네임스페이스 바인딩"""
        self.graph.bind("log", LOG)
        self.graph.bind("data", DATA)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)
        self.graph.bind("prov", PROV)
    
    def add_triple(self, subject: URIRef, predicate: URIRef, obj: Union[URIRef, Literal]):
        """Triple 추가"""
        self.graph.add((subject, predicate, obj))
        return self
    
    def add_type(self, subject: URIRef, rdf_type: URIRef):
        """rdf:type 추가"""
        self.graph.add((subject, RDF.type, rdf_type))
        return self
    
    def add_label(self, subject: URIRef, label: str, lang: str = "ko"):
        """rdfs:label 추가"""
        self.graph.add((subject, RDFS.label, Literal(label, lang=lang)))
        return self
    
    def add_datetime(self, subject: URIRef, predicate: URIRef, dt: Union[str, datetime]):
        """datetime 속성 추가"""
        if isinstance(dt, str):
            # ISO 8601 문자열을 파싱
            try:
                dt = datetime.fromisoformat(dt)
            except ValueError:
                # 이미 올바른 형식이면 그대로 사용
                pass
        
        if isinstance(dt, datetime):
            # datetime 객체를 xsd:dateTime Literal로 변환
            literal = Literal(dt.isoformat(), datatype=XSD.dateTime)
        else:
            # 문자열 그대로 사용
            literal = Literal(dt, datatype=XSD.dateTime)
        
        self.graph.add((subject, predicate, literal))
        return self
    
    def add_integer(self, subject: URIRef, predicate: URIRef, value: int):
        """integer 속성 추가"""
        self.graph.add((subject, predicate, Literal(value, datatype=XSD.integer)))
        return self
    
    def add_decimal(self, subject: URIRef, predicate: URIRef, value: float):
        """decimal 속성 추가"""
        self.graph.add((subject, predicate, Literal(value, datatype=XSD.decimal)))
        return self
    
    def add_string(self, subject: URIRef, predicate: URIRef, value: str):
        """string 속성 추가"""
        self.graph.add((subject, predicate, Literal(value, datatype=XSD.string)))
        return self
    
    def add_provenance(self, entity: URIRef, source_file: str, row_index: int):
        """Provenance 정보 추가
        
        entity가 어떤 원본 로그에서 왔는지 추적 가능하게 함
        """
        # RawLog 엔티티 생성
        raw_log_uri = DATA[f"rawlog_{entity.split('/')[-1]}"]
        
        # RawLog 정의
        self.graph.add((raw_log_uri, RDF.type, LOG.RawLog))
        self.graph.add((raw_log_uri, RDF.type, PROV.Entity))
        self.graph.add((raw_log_uri, LOG.sourceFile, Literal(source_file, datatype=XSD.string)))
        self.graph.add((raw_log_uri, LOG.rowIndex, Literal(row_index, datatype=XSD.integer)))
        
        # Entity → RawLog 연결
        self.graph.add((entity, PROV.wasDerivedFrom, raw_log_uri))
        
        return self
    
    def serialize(self, format: str = "turtle") -> str:
        """그래프를 문자열로 직렬화"""
        return self.graph.serialize(format=format)
    
    def save(self, filepath: str, format: str = "turtle"):
        """그래프를 파일로 저장"""
        self.graph.serialize(destination=filepath, format=format)
        return self
    
    def __len__(self):
        """그래프의 triple 수"""
        return len(self.graph)


def create_user_uri(user_id: str) -> URIRef:
    """User URI 생성"""
    return DATA[user_id]


def create_person_uri(person_name: str) -> URIRef:
    """Person URI 생성 (이름을 ID로 변환)"""
    # 공백을 제거하고 CamelCase로 변환
    person_id = person_name.replace(" ", "").replace("-", "")
    return DATA[person_id]


def create_place_uri(place_id: str) -> URIRef:
    """Place URI 생성"""
    return DATA[place_id]


def create_app_uri(package_name: str) -> URIRef:
    """App URI 생성"""
    # com.slack → slack
    app_id = package_name.split(".")[-1]
    return DATA[f"app_{app_id}"]


def create_event_uri(event_id: str) -> URIRef:
    """Event URI 생성"""
    return DATA[event_id]


def create_content_uri(content_id: str) -> URIRef:
    """Content URI 생성"""
    return DATA[content_id]


def get_place_type_class(place_type: str) -> URIRef:
    """Place type에 따른 클래스 반환"""
    type_map = {
        "home": LOG.Home,
        "office": LOG.Office,
        "cafe": LOG.Cafe,
        "restaurant": LOG.Restaurant,
        "station": LOG.Station
    }
    return type_map.get(place_type, LOG.Place)


def sanitize_id(text: str) -> str:
    """텍스트를 URI 친화적인 ID로 변환"""
    # 특수문자 제거, 공백을 언더스코어로
    return text.replace(" ", "_").replace("-", "_").lower()
