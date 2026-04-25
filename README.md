# RDF Knowledge Graph + LangGraph Agent + OpenWebUI

스마트폰 로그 데이터를 RDF Knowledge Graph로 변환하고, LangGraph 기반 Agent로 자연어 질의응답을 수행하는 시스템입니다. GCN + TransE Hybrid 모델을 활용한 Link Prediction으로 Sparse Data 문제를 해결합니다.

## 주요 기능

- **Event-Centric RDF Ontology**: 스마트폰 이벤트를 중심으로 설계된 온톨로지
- **LangGraph Agent**: State machine 기반 다단계 워크플로우
- **LLM Text2SPARQL**: Gemini를 활용한 자연어 → SPARQL 변환
- **Link Prediction**: GCN + TransE Hybrid로 누락된 관계 예측
- **FastAPI Backend**: RESTful API 서버
- **OpenWebUI 호환**: OpenAI API 호환 레이어

## 아키텍처

```
사용자 질의
  ↓
OpenWebUI / API
  ↓
LangGraph Agent
  ├─ Query Analysis (LLM)
  ├─ Sparse Detection
  ├─ Link Prediction (GCN + TransE)
  ├─ Text2SPARQL (LLM)
  ├─ SPARQL Execute
  └─ Answer Generation (LLM)
  ↓
자연어 답변
```

## 설치

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일 생성:

```
GEMINI_API_KEYS=your_key1,your_key2,your_key3
GEMINI_MODEL=gemini-2.0-flash-exp
LLM_TEMPERATURE=0.3
LLM_REQUEST_DELAY_SEC=5
SPARSE_THRESHOLD=3
```

## 빠른 시작

### 1. 데이터 생성

```bash
python test_pipeline.py
```

- `data/logs/` 아래 JSON 로그 생성
- `data/rdf/generated_data.ttl` RDF 파일 생성

### 2. FastAPI 서버 실행

```bash
python backend/main.py
```

서버 실행 후:
- API 문서: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 3. API 테스트

```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "최근 통화한 사람은 누구야?", "use_link_prediction": false}'

# OpenAI-compatible endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rdf-kg-agent",
    "messages": [{"role": "user", "content": "가장 자주 쓴 앱 뭐야?"}]
  }'
```

### 4. 통합 테스트

```bash
# 서버가 실행중인 상태에서
python tests/test_integration.py
```

## OpenWebUI 연동

OpenWebUI에서 Custom API로 연동:

1. OpenWebUI 설정 → Connections → OpenAI API
2. API Base URL: `http://localhost:8000/v1`
3. API Key: (임의값, 현재는 인증 없음)
4. Model: `rdf-kg-agent`

## 프로젝트 구조

```
cursor_text2sparql/
├── app/
│   ├── agents/               # LangGraph Agent
│   │   ├── kg_agent.py       # Main agent
│   │   ├── nodes.py          # Workflow nodes
│   │   ├── state.py          # Agent state
│   │   └── llm_client.py     # Gemini client
│   ├── prompts/              # LLM prompts
│   │   ├── text2sparql.py
│   │   └── answer_generation.py
│   ├── link_prediction/      # Link Prediction
│   │   ├── gcn_transe_hybrid.py
│   │   ├── graph_builder.py
│   │   ├── trainer.py
│   │   ├── predictor.py
│   │   └── pipeline.py
│   ├── step1_generate/       # Synthetic data generation
│   ├── step2_transform/      # RDF transformation
│   └── step3_load/          # SPARQL executor
├── backend/                  # FastAPI server
│   ├── main.py
│   ├── models.py
│   ├── routes.py
│   └── openai_compat.py     # OpenAI API compatibility
├── data/
│   ├── ontology/            # Ontology files
│   ├── logs/                # Generated JSON logs
│   ├── rdf/                 # Generated RDF data
│   └── sparse_scenarios/    # Sparse data test cases
├── docs/                    # Documentation
├── tests/                   # Integration tests
└── requirements.txt
```

## 데이터 온톨로지

### Core Classes

- `log:User`: 스마트폰 사용자
- `log:Person`: 연락처 사람들
- `log:Place`: 장소
- `log:App`: 애플리케이션
- `log:Content`: 사진/영상

### Event Classes

- `log:CallEvent`: 통화 이벤트
- `log:AppUsageEvent`: 앱 사용
- `log:CalendarEvent`: 일정
- `log:VisitEvent`: 장소 방문

### Key Properties

- `log:calledPerson`: 통화한 사람
- `log:usedApp`: 사용한 앱
- `log:visitedPlace`: 방문한 장소
- `log:startTime`: 시작 시간
- `prov:wasDerivedFrom`: 출처 (Provenance)

## LangGraph Workflow

### 1. Query Analysis
- LLM으로 사용자 질의 분석
- Intent, entities, time constraint 추출

### 2. Sparse Detection
- 관련 triple 개수 확인
- Threshold 이하면 sparse로 판단

### 3. Link Prediction (조건부)
- GCN + TransE Hybrid 모델
- Missing link 상위 K개 예측

### 4. Text2SPARQL
- LLM으로 SPARQL 생성
- Property catalog 참조

### 5. SPARQL Execute
- rdflib 기반 in-memory 실행

### 6. Answer Generation
- LLM으로 자연어 답변 생성
- Provenance 정보 포함

## Link Prediction

### GCN + TransE Hybrid

- **GCN**: Graph 구조 학습으로 context-aware node embeddings
- **TransE**: Relation을 translation vector로 명시적 학습
- **Scoring**: `h + r ≈ t` (L2 distance)

### Training

```python
from app.link_prediction.pipeline import LinkPredictionPipeline

pipeline = LinkPredictionPipeline(rdf_graph)
pipeline.train(num_epochs=50)
pipeline.save_model("model.pt")
```

### Inference

```python
predictions = pipeline.predict_missing_links(
    head_uri="http://example.org/data/call_003",
    relation_uri="http://example.org/smartphone-log#visitedAfter",
    top_k=5
)
```

## Sparse Data 시나리오

5종의 sparse data 시나리오 제공:

1. **call_sparse**: 통화 후 장소 missing
2. **app_sparse**: 앱 사용 시 일정 missing
3. **visit_sparse**: 방문 시 만난 사람 missing
4. **calendar_sparse**: 회의 참석자 missing
5. **content_sparse**: 사진 촬영 이벤트 missing

## API 엔드포인트

### Health Check
```
GET /health
```

### Chat
```
POST /api/v1/chat
{
  "query": "최근 통화한 사람은 누구야?",
  "use_link_prediction": true
}
```

### OpenAI-Compatible
```
POST /v1/chat/completions
{
  "model": "rdf-kg-agent",
  "messages": [{"role": "user", "content": "가장 자주 쓴 앱 뭐야?"}]
}
```

## 기술 스택

| 레이어 | 기술 | 용도 |
|--------|------|------|
| Agent Framework | LangGraph | State machine workflow |
| LLM | Gemini 2.5 Flash | Text2SPARQL, Answer generation |
| Link Prediction | GCN + TransE | Graph 구조 + Relation 학습 |
| Graph Library | PyTorch Geometric | GCN 구현 |
| Backend | FastAPI | REST API 서버 |
| Frontend | OpenWebUI | 채팅 UI |
| RDF Store | rdflib | In-memory SPARQL 실행 |

## 개발 참고

### LLM Rate Limit

Gemini Free Tier는 분당 5회 제한이 있습니다. `.env`에서 `LLM_REQUEST_DELAY_SEC`로 조절하세요.

### Link Prediction 학습

723개 triples로 학습 시 overfitting 주의. Dropout과 regularization이 적용되어 있습니다.

### Sparse Threshold

`.env`의 `SPARSE_THRESHOLD`로 조절 가능 (기본값: 3)

## 문서

- [Ontology Design](docs/ONTOLOGY_DESIGN.md)
- [Project Completion Report](docs/PROJECT_COMPLETION_REPORT.md)
- [Integration Plan](c:\Users\user\.cursor\plans\rdf_kg_langgraph_integration_a8e8f95e.plan.md)

## 라이선스

MIT

## 작성자

Built with Cursor AI
