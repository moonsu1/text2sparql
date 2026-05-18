# 개인 스마트폰 KG 프로토타입 면접 보고서

이 문서는 현재 구현된 개인 스마트폰 로그 기반 Knowledge Graph(KG) 프로토타입을 면접에서 설명하기 쉽게 정리한 문서다. 앞부분은 내가 바로 말로 설명할 수 있는 쉬운 버전이고, 뒷부분은 리서처/엔지니어가 쓰는 언어로 다시 정리한 버전이다.

이 문서의 핵심 메시지는 간단하다.

- **현재 구현**: 스마트폰 로그를 이벤트 중심 RDF KG로 만들고, SPARQL로 질의하며, KG에 없는 관계는 request-scoped link prediction으로 보완한다.
- **차별점**: 단순 RAG가 아니라, **KG querying + sparse relation completion + LLM verification** 을 결합했다.
- **다음 단계**: Phone / Watch / TV까지 확장하려면 single-device KG에서 끝나지 않고, **cross-device entity alignment + schema alignment** 가 필요하다.

---

## Part I. 쉬운 버전

### 1. 왜 이 문제가 중요한가

스마트폰 안에는 통화, 캘린더, 사진, 앱 사용, 방문 기록 같은 정보가 다 따로 흩어져 있다. 사람 입장에서는 이 정보들이 사실 하나의 생활 맥락인데, 앱 단위로 분리되어 있으면 "김철수와 통화하고 나서 어디를 갔지?" 같은 질문에 답하기 어렵다.

내 프로젝트는 이 흩어진 로그를 **하나의 개인 Knowledge Graph** 로 통합하고, 그 위에서 자연어 질문을 처리하는 프로토타입이다. 그리고 데이터가 비어 있거나 관계가 명시적으로 저장되지 않은 경우에는, **링크 예측(link prediction)** 으로 빠진 관계를 메워서 답변하려고 한다.

삼성 맥락에서 이게 중요한 이유도 분명하다. 삼성은 2024년 7월 18일 Oxford Semantic Technologies를 인수하면서 **personal knowledge graph** 와 **on-device reasoning** 을 직접 언급했고, 2025년 1월 23일 Galaxy S25 발표에서는 **Personal Data Engine** 이 사용자 데이터를 온디바이스에서 분석해 personalized AI feature를 제공한다고 밝혔다. 즉, 개인 로그를 지식 구조로 연결하고 안전하게 활용하는 방향이 이미 실제 제품 전략과 연결되어 있다.

### 2. 이 시스템을 한 문장으로 설명하면

> 스마트폰 로그를 이벤트 중심 KG로 구조화하고, SPARQL로 먼저 질의한 뒤, KG에 없는 관계는 R-GCN + TransE로 예측하고 LLM이 시간·장소 문맥으로 검증해서 최종 답을 만드는 시스템이다.

### 3. 지금 시스템이 하는 일

쉬운 말로 풀면 아래 다섯 단계다.

1. **질문을 분석한다.**
   - 사람 이름, 장소명, 시간 힌트, 질문 의도를 뽑는다.
2. **엔티티를 찾는다.**
   - `"김철수"` 같은 이름은 KG에서 후보 엔티티를 찾는다.
   - `"투썸플레이스"` 같은 구체적 장소명은 KG의 place 엔티티로 매핑한다.
   - `"카페"` 같은 일반 범주는 엔티티 검색이 아니라 type filter로 처리한다.
3. **SPARQL로 먼저 답을 찾는다.**
   - KG에 이미 충분한 트리플이 있으면 여기서 끝난다.
4. **답이 비면 빠진 관계를 예측한다.**
   - `(photo, relatedEvent, ?)` 나 `(visit, metDuring, ?)` 같은 식으로 missing tail을 예측한다.
5. **LLM이 후보를 검증하고 답을 말로 정리한다.**
   - top-k 후보 중 시간, 장소, 질문 문맥에 가장 맞는 후보를 LLM이 고른다.

### 4. 1-hop 예시

질의:

> "김철수와 통화하고 나서 간 카페가 어디야?"

이 질의는 시스템 입장에서 이렇게 해석된다.

- 사람: `김철수`
- 장소 범주: `카페`
- 찾고 싶은 관계: `visitedAfter`

처리 흐름은 아래와 같다.

1. `query analysis` 단계에서 `"김철수"` 와 `"카페"` 를 추출한다.
2. `entity resolution` 단계에서 `"김철수"` 는 person 엔티티 후보로 매핑한다.
3. `"카페"` 는 고유명사가 아니므로 `"스타벅스 강남점"` 같은 specific place search를 하지 않고, **`log:Cafe` 또는 place type filter** 로 처리한다.
4. SPARQL이 기존 KG에서 `CallEvent -> VisitEvent` 연결을 찾는다.
5. 만약 결과가 없으면 `(call, visitedAfter, ?visit)` 에 대해 link prediction을 수행한다.
6. top-k 방문 후보 중에서 LLM이 시간 차이, 장소 타입, 질의 문맥을 보고 최종 후보를 고른다.
7. 선택된 URI를 `VALUES` 로 고정한 SPARQL을 다시 만들어 결과를 반환한다.

여기서 중요한 점은, 현재 시스템에서 `"카페"` 는 엔티티 자체가 아니라 **질의 조건** 이라는 점이다. 반면 `"투썸플레이스"` 나 `"스타벅스 역삼점"` 같은 표현은 엔티티 후보 검색 대상이 된다.

### 5. 2-hop 예시

질의:

> "4월 17일 투썸플레이스에서 찍은 사진이랑 연결된 방문에서 누구 만났어?"

이 질의는 2-hop 체인 질의다.

`Content -> VisitEvent -> Person`

즉:

- 사진이 어떤 방문 이벤트와 연결되는지 찾고
- 그 방문 이벤트에서 누구를 만났는지 다시 찾아야 한다.

처리 흐름은 아래와 같다.

1. **Query Analysis**
   - 질의를 보고 `relatedEvent + metDuring` 체인을 감지한다.
   - 날짜 힌트 `4월 17일`, 장소 힌트 `투썸플레이스`, 질문 의도 `누구를 만났는가` 를 뽑는다.

2. **Entity Resolution**
   - `투썸플레이스` 를 place 엔티티로 매핑한다.

3. **SPARQL 생성 + 실행**
   - 우선 `photo -> relatedEvent -> visit -> metDuring -> person` 구조를 직접 질의한다.
   - KG에 해당 관계가 없으면 결과는 0건이다.

4. **LP 1차 hop**
   - `(photo_001, relatedEvent, ?)` 를 예측한다.
   - R-GCN + TransE가 top-k 방문 후보를 만들고, LLM이 가장 질의 맥락에 맞는 `visit_002` 를 선택한다.
   - 이때 선택된 방문 이벤트가 **중간 노드** 가 된다.

5. **LP 2차 hop**
   - `(visit_002, metDuring, ?)` 를 다시 예측한다.
   - 동일하게 top-k person 후보를 만들고, LLM이 최종 인물을 선택한다.

6. **VALUES SPARQL 재생성**
   - 예측된 URI를 `VALUES` 로 고정해서 SPARQL을 다시 실행한다.

7. **답변 생성**
   - 최종 답변은 "정답" 이 아니라, **예측과 근거를 포함한 답변** 형태가 된다.
   - 예: `"Jung Su-jin을 만났을 가능성이 높습니다 (confidence 0.51)."`

이 예시가 보여주는 시스템의 강점은 명확하다. ToG나 RoG처럼 **기존 KG 안에 경로가 있어야만** reasoning이 가능한 구조와 달리, 내 시스템은 **중간 경로가 비어 있어도** LP로 경로를 먼저 보완할 수 있다.

### 6. 지금 구조의 장점과 한계

#### 장점

- **이벤트 중심 KG** 라서 시간 순서와 provenance를 설명하기 좋다.
- 자연어 질의를 바로 문서 검색으로 넘기지 않고, **명시적 graph query** 로 처리한다.
- KG가 희박해도 **missing relation prediction** 으로 sparse data 문제를 완화한다.
- 예측 결과를 바로 KG에 영구 저장하지 않고, **request-scoped inference** 로 다뤄서 보수적으로 운영할 수 있다.

#### 한계

- 지금은 single-device 프로토타입이라 Phone / Watch / TV 통합은 아직 구현되지 않았다.
- multi-hop 체인은 아직 ontology reasoning이 아니라 **rule / chain 정의** 에 많이 의존한다.
- 발표 자료에 적힌 `schema retrieval` 은 개념 설명에 가깝고, 실제 구현은 **entity-centric retrieval + property catalog prompt** 에 더 가깝다.
- LP confidence calibration은 아직 단순하고, fully learned reranking 시스템까지 가진 상태는 아니다.

### 7. 30초 소개 템플릿

> 제 프로젝트는 스마트폰의 통화, 방문, 사진, 일정, 앱 사용 로그를 이벤트 중심 RDF Knowledge Graph로 통합하고, 자연어 질문을 SPARQL로 질의하는 프로토타입입니다. 기존 KG에 관계가 없어서 답이 안 나오는 경우에는 R-GCN + TransE로 missing relation을 예측하고, LLM이 시간과 장소 문맥으로 후보를 다시 검증해서 최종 답변을 생성합니다. 그래서 단순 KG 질의가 아니라, sparse personal KG 환경에서 completion과 reasoning을 함께 다루는 구조라고 설명할 수 있습니다.

---

## Part II. 리서처/엔지니어 버전

### 8. 현재 프로토타입의 실제 구조

현재 런타임의 메인 경로는 아래와 같다.

- FastAPI entrypoint: [backend/main.py](../backend/main.py)
- agent selection: [backend/routes.py](../backend/routes.py)
- supervisor agent: [app/agents/kg_agent_supervisor.py](../app/agents/kg_agent_supervisor.py)
- stage orchestration: [app/agents/stages.py](../app/agents/stages.py)

현재 active path는 대략 다음과 같이 이해하면 된다.

1. `query_analysis_stage`
   - intent, time hint, person mention, place mention, place type, target relation을 추출한다.
   - multi-hop query는 `MULTIHOP_CHAINS` 에 정의된 체인을 감지한다.

2. `entity_resolution_stage`
   - person name은 KG label search로 후보를 찾고 정렬한다.
   - place는 `specific place mention` 과 `generic place type` 을 구분한다.
   - 예: `"투썸플레이스"` 는 KG entity lookup 대상이지만 `"카페"` 는 lookup이 아니라 type filter 대상이다.

3. `sparql_generation_stage`
   - 현재 구현은 **top-k schema retrieval** 전용 모듈이 따로 있는 구조는 아니다.
   - 실제로는 [data/ontology/property_catalog.yaml](../data/ontology/property_catalog.yaml) 전체를 prompt context로 넣고, 질의를 좁혀주는 역할은 `resolved entity + relation hint + time constraint` 가 담당한다.
   - 따라서 발표 자료의 `schema retrieval` 은 구현 상세라기보다, retrieval-first 설계 철학에 더 가깝다.

4. `execution_stage`
   - 먼저 Fuseki에서 직접 질의한다.

5. `link_prediction_stage`
   - 결과가 없거나 sparse relation completion이 필요하면 LP로 넘어간다.
   - 1-hop 또는 2-hop chain 모두 지원한다.

6. `answer_generation_stage`
   - SPARQL 결과와 prediction evidence를 바탕으로 답변을 생성한다.

#### 현재 구현과 레거시의 차이

이 저장소에는 두 세대의 구조가 공존한다.

- **현재 active runtime**
  - supervisor 기반 stage orchestration
  - request-scoped LP
  - OpenAI-compatible streaming endpoint

- **레거시 / 구세대 경로**
  - [app/step4_query/text2sparql_agent.py](../app/step4_query/text2sparql_agent.py)
  - [app/agents/nodes.py](../app/agents/nodes.py)
  - 과거 rule-based / older LangGraph-style 경로

면접에서는 이 점을 숨기기보다 이렇게 설명하는 편이 좋다.

> 현재 프로토타입은 supervisor 기반 stage pipeline이 main이고, 저장소에는 초기에 만든 rule-based Text2SPARQL 실험 경로가 함께 남아 있습니다. 그래서 단일 구조라기보다, rule-based baseline에서 LLM + supervisor + link prediction으로 발전해 온 흔적이 보이는 저장소입니다.

#### request-scoped prediction이라는 점

중요한 구현 포인트는, predicted triple을 Fuseki에 영구 write-back하지 않는다는 점이다.  
현재 시스템은 [app/agents/tools/link_prediction_tools.py](../app/agents/tools/link_prediction_tools.py) 에서 예측 결과를 만들고, [app/agents/tools/sparql_tools.py](../app/agents/tools/sparql_tools.py) 에서 그 URI를 `VALUES` 로 바인딩해 재질의한다.

즉:

- **KG storage layer** 와
- **request-time inferred context**

를 분리해서 운영한다.

이 보수적 구조는 면접에서 장점으로 말할 수 있다. 왜냐하면 개인 로그처럼 민감한 데이터에서는 model guess를 바로 truth layer에 섞지 않는 것이 합리적이기 때문이다.

### 9. 논문/산업 맥락: 지금 시스템과의 접점

#### 9.1 Think-on-Graph (ICLR 2024)

원문: [Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph](https://proceedings.iclr.cc/paper_files/paper/2024/hash/10a6bdcabbd5a3d36b760daa295f63c1-Abstract-Conference.html)

ToG가 푼 문제는 간단하다.  
LLM은 hallucination이 있고, KG를 한번에 프롬프트에 다 넣는 것은 비효율적이다. 그래서 LLM이 **agent처럼 KG를 직접 탐색** 하면서 필요한 경로만 찾게 하자는 것이다.

ToG의 핵심 구조:

- LLM ⊗ KG tight coupling
- LLM agent가 KG에서 entity / relation을 따라가며 beam search
- promising path를 확장하면서 reasoning

내 시스템과의 접점:

- 공통점:
  - retrieval과 reasoning을 분리하지 않고 밀접하게 연결한다.
  - multi-hop path를 단계적으로 탐색한다.
  - 최종 해석/선택에는 LLM이 관여한다.
- 차이점:
  - ToG는 **기존 KG 안의 path** 를 탐색한다.
  - 내 시스템은 **KG에 없는 path도 LP로 보완한 뒤** 탐색을 계속할 수 있다.

면접용 한 문장:

> ToG가 existing KG path를 LLM agent가 직접 탐색하는 구조라면, 제 시스템은 sparse personal KG에서 missing relation을 먼저 completion한 뒤 reasoning을 계속한다는 점이 다릅니다.

#### 9.2 Reasoning on Graphs (RoG, ICLR 2024)

원문: [Reasoning on Graphs: Faithful and Interpretable Large Language Model Reasoning](https://openreview.net/forum?id=ZGNWW7xZ6Q)

RoG는 hallucination을 줄이기 위해 **planning -> retrieval -> reasoning** 구조를 분리한다.

- planning: relation path 생성
- retrieval: 해당 path에 맞는 valid KG path 검색
- reasoning: path 기반으로 답변

내 시스템과의 접점:

- `query_analysis_stage` 가 relation chain을 감지하는 부분은 RoG의 planning과 닮아 있다.
- 직접 질의가 실패하면 `predict_sparse_relations()` 와 `predict_second_hop()` 이 request-scoped retrieval/completion 역할을 한다.
- LLM은 후보 검증과 answer generation에 관여한다.

중요한 차이:

- RoG는 **KG에 valid path가 존재한다는 가정** 이 더 강하다.
- 내 시스템은 path가 비어 있으면 **LP를 통해 chain을 보강** 한 뒤 reasoning한다.

#### 9.3 LLM-DA / Temporal KG Reasoning (NeurIPS 2024)

원문: [Large Language Models-guided Dynamic Adaptation for Temporal Knowledge Graph Reasoning](https://proceedings.neurips.cc/paper_files/paper/2024/hash/0fd17409385ab9304e5019c6a6eb327a-Abstract-Conference.html)

이 논문이 중요한 이유는, 스마트폰 로그 KG는 본질적으로 **Temporal KG** 이기 때문이다. 통화, 방문, 일정, 사진, 앱 사용은 모두 타임스탬프를 가진다.

LLM-DA가 강조하는 포인트:

- temporal logical rules의 중요성
- evolving knowledge에 대한 적응
- time-aware reasoning의 해석 가능성

내 시스템에서 시간은 실제로 다음 역할을 한다.

- 질의 해석 시 date hint / relative time을 만든다.
- rule-based fallback에서는 `_time_confidence()` 로 시간 차이에 따라 신뢰도를 조정한다.
- 예:
  - 통화 후 25분 뒤 방문 -> 높은 confidence
  - 통화 후 205분 뒤 방문 -> 거의 제외

즉, 내 시스템은 복잡한 TKG 모델은 아니지만, **시간 거리 자체를 relation confidence signal로 사용한다** 는 점에서 temporal KG reasoning의 핵심 아이디어를 이미 갖고 있다.

#### 9.4 Samsung Personal Data Engine / RDFox 맥락

산업적으로 가장 중요한 연결은 삼성이다.

- 2024년 7월 18일, 삼성은 Oxford Semantic Technologies 인수를 발표하면서 **knowledge graph technology**, **semantic reasoning**, **RDFox**, **personal knowledge graphs**, **on-device AI** 를 공식적으로 언급했다.  
  출처: [Samsung acquisition announcement](https://news.samsung.com/global/samsung-electronics-announces-acquisition-of-oxford-semantic-technologies-uk-based-knowledge-graph-startup)

- 2025년 1월 23일, Galaxy S25 발표에서는 **Personal Data Engine** 이 사용자 데이터를 **on-device** 에서 분석해 personalized AI feature를 제공한다고 밝혔다. 또한 현재는 Samsung native applications를 분석한다고 명시했다.  
  출처: [Galaxy S25 / Personal Data Engine announcement](https://news.samsung.com/global/samsung-galaxy-s25-series-sets-the-standard-of-ai-phone-as-a-true-ai-companion)

이 두 발표를 묶어서 보면, 삼성의 방향은 다음처럼 정리할 수 있다.

- 앱별로 흩어진 개인 데이터를 연결하고
- 온디바이스에서 reasoning 가능한 지식 구조를 만들고
- privacy를 유지한 채 personalized AI를 제공한다.

이 맥락에서 내 프로토타입의 의미는 분명하다.

- 나는 이미 **이벤트 중심 personal KG** 를 설계했고
- 그 위에서 **graph query + sparse completion + answer generation** 을 실험했으며
- 다음 단계로 **cross-device integration + ontology reasoning** 으로 확장할 수 있는 기반을 갖고 있다.

#### 9.5 GraphRAG는 왜 보조축인가

원문: [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130)

GraphRAG는 private corpus 전체를 그래프로 바꾸고 community summary를 활용해 global question에 답하는 구조다. 내 현재 시스템과 1:1로 대응되지는 않는다.

GraphRAG를 본문 메인에 두지 않는 이유:

- 내 시스템의 핵심은 document summarization이 아니라 **structured event KG query** 이다.
- 현재 데이터도 비정형 문서가 아니라 이미 구조화 가능한 app log 쪽에 가깝다.

하지만 future direction으로는 의미가 있다.

- 비정형 메모, 메시지, 웹 페이지, 앱 설명 텍스트를 KG에 흡수할 때
- GraphRAG식 graph index / community summary 전략은 유용할 수 있다.

따라서 GraphRAG는 **현재 구조 설명** 용이 아니라 **비정형 데이터 확장 방향** 의 근거로 짧게 연결하는 편이 적절하다.

### 10. Future Expansion: Cross-Device Entity & Schema Alignment

현재 시스템은 **single-device personal KG query/completion prototype** 이다.  
삼성 제품 관점에서 진짜 어려운 다음 단계는 **Phone / Watch / TV / Samsung native apps 전반의 cross-device integration** 이다.

여기서 중요한 건, 이 문제를 단순히 `"동일 사용자 식별"` 하나로 축소해서 보면 안 된다는 점이다. 실제 메인 문제는 아래처럼 정리된다.

> **Cross-device schema integration** 이 메인이고,  
> entity alignment, event matching, attribute normalization, relation consistency는 그걸 위한 하위 과제다.

#### 10.1 꼭 살릴 논문 1: ProLEA

원문: [Entity Profile Generation and Reasoning with LLMs for Entity Alignment](https://aclanthology.org/2025.findings-emnlp.1093/)

핵심 아이디어:

- embedding 기반 후보 생성
- entity property로 profile 생성
- LLM이 후보를 재평가

왜 필요한가:

- 지금 내 entity resolution 설명은 기본적으로 `label search + 일부 LLM 보강` 수준이다.
- cross-device 단계에서는 `"이 watch event와 이 phone event가 같은 사람/같은 맥락인가?"` 같은 애매한 정합 문제가 늘어난다.
- 이때 단순 string match보다 **entity profile + candidate reranking** 이 훨씬 자연스럽다.

내 구조와 접점:

- 현재도 `query analysis -> entity candidate -> LLM verification` 흐름이 있다.
- ProLEA는 이 흐름을 alignment 문제로 확장한 버전으로 이해하면 된다.

면접에서 이렇게 말하면 좋다.

> 지금 프로토타입에서는 entity candidate를 찾고 LLM이 질의 문맥에 맞는 후보를 고르는 흐름이 있는데, cross-device 확장 단계에서는 ProLEA처럼 entity profile을 구성해 candidate reranking을 더 체계화하는 방향이 필요하다고 봤습니다.

#### 10.2 꼭 살릴 논문 2: Group, Embed and Reason

원문: [Group, Embed and Reason: A Hybrid LLM and Embedding Framework for Semantic Attribute Alignment](https://aclanthology.org/2025.emnlp-industry.120/)

이 논문이 Phase 2에서 가장 중요한 이유는, cross-device 통합의 본질이 entity만이 아니라 **schema / attribute alignment** 이기 때문이다.

핵심 아이디어:

- instance data가 거의 없거나 없어도
- schema metadata만으로
- attribute grouping + embedding similarity + LLM reasoning을 조합해 alignment를 수행한다.

왜 삼성 맥락과 잘 맞는가:

- 실제 단말 데이터 통합은 privacy constraint가 크다.
- 모든 raw instance를 자유롭게 다 쓰기 어렵다.
- 앱마다 속성명과 구조가 다르다.
  - 예: `start_time`, `capturedAt`, `occurredAt`, `visitedAt`
  - 의미는 비슷하지만 스키마 표현은 다르다.

즉, 이 논문은 **Phase 2의 메인 문제** 인 `cross-device schema integration` 을 설명하는 데 가장 적합하다.

#### 10.3 꼭 살릴 논문 3: Beyond Entity Alignment

원문: [Beyond Entity Alignment: Towards Complete Knowledge Graph Alignment via Entity-Relation Synergy](https://arxiv.org/abs/2407.17745)

핵심 메시지는 단순하다.

> entity만 맞춘다고 KG alignment가 끝나지 않는다.  
> relation alignment와 consistency까지 같이 봐야 complete alignment에 가깝다.

왜 필요한가:

- cross-device에서 같은 사용자나 같은 이벤트를 맞췄다고 해도,
- 연결된 relation이 충돌하면 통합 KG는 일관성을 잃는다.

예:

- Phone에서는 `capturedAt` 과 `capturedPlace` 로 사진을 기록하고
- Watch에서는 다른 activity event와 location sampling이 연결될 수 있다.
- TV는 시청/추천/프로필 관계 중심일 수 있다.

이때 entity pair만 맞추는 것으로는 부족하고, **정렬 이후 relation graph가 coherent한지** 까지 봐야 한다.  
그래서 이 논문은 Phase 2의 마지막 bullet인 `통합 KG consistency / relation-level validation` 을 정당화하는 근거가 된다.

#### 10.4 짧게만 언급할 논문

##### EasyEA

원문: [EasyEA: Large Language Model is All You Need in Entity Alignment Between Knowledge Graphs](https://aclanthology.org/2025.findings-acl.1080/)

이 논문은 **training-free / seed-light baseline** 으로는 좋다.  
즉, Phase 2를 처음 시작할 때 "대규모 supervised seed pair 없이도 alignment를 시작할 수 있는가?"라는 질문에 대한 좋은 참고점이 된다.

하지만 이번 문서에서 메인으로 두지 않는 이유는 분명하다.

- ProLEA와 역할이 많이 겹치고
- 이번 확장 전략의 핵심은 `profile reasoning + schema alignment + relation consistency` 이기 때문이다.

따라서 EasyEA는 부록 또는 짧은 baseline 언급 정도로 제한하는 것이 좋다.

##### DAEA

원문: [DAEA: Enhancing Entity Alignment in Real-World Knowledge Graphs Through Multi-Source Domain Adaptation](https://aclanthology.org/2025.coling-main.393/)

DAEA가 유용한 지점은, benchmark EA와 real-world EA 사이의 차이를 강조한다는 점이다.

- synthetic benchmark에서는 잘 되던 방식이
- real-world, heterogeneous, incomplete, domain-specific KG에서는 성능이 크게 떨어진다.

이 메시지는 삼성처럼 실제 서비스 데이터를 다루는 환경과 잘 맞는다.  
다만 이번 보고서는 domain adaptation 모델 자체를 구현한 이야기가 아니므로, 메인으로 길게 다루면 중심이 흐려진다.

따라서 DAEA는 아래 문장을 뒷받침하는 정도로만 쓰는 것이 적절하다.

> 실제 서비스 데이터의 alignment는 benchmark EA보다 훨씬 이질적이고 noisy하기 때문에, schema / metadata / context-aware reasoning을 함께 보는 전략이 필요하다.

##### LLM-Align는 왜 이번 버전에서 제외하는가

원문: [LLM-Align: Utilizing Large Language Models for Entity Alignment in Knowledge Graphs](https://arxiv.org/abs/2412.04690)

LLM-Align 자체가 나쁜 논문이라는 뜻은 아니다.  
다만 이번 문서에서는 다음 이유로 제외하는 것이 낫다.

- EasyEA와 `LLM 중심 / seed-light` 포지션이 겹친다.
- 공식 conference / anthology 논문을 우선 쓰는 편이 면접 문서에서는 안정적이다.
- 문서의 메인 메시지를 더 선명하게 유지할 수 있다.

### 11. 온톨로지 / OWL / RDFox 전략

#### 11.1 현재 상태

현재 온톨로지는 [data/ontology/ontology.ttl](../data/ontology/ontology.ttl) 에 정의되어 있고, `owl:Class`, `owl:ObjectProperty`, `owl:DatatypeProperty` 로 모델링되어 있다. 즉, 이 프로젝트는 단순히 “그래프처럼 생긴 데이터”를 쓴 것이 아니라, **OWL 스키마를 가진 event-centric KG** 를 설계한 상태다.

이 파일은 Protege로 열어서 아래를 점검할 수 있다.

- class hierarchy
- object/datatype property
- domain / range
- inverse property
- ontology-level annotation

즉, 면접에서는 `Protege로 다룰 수 있는 OWL ontology 기반 KG 설계 경험` 이 있다고 말해도 무리가 없다.

#### 11.2 현재 한계

현재 multi-hop query 처리의 상당 부분은 ontology reasoner가 아니라 아래 구조에 의존한다.

- `MULTIHOP_CHAINS` 에 정의된 체인
- query pattern detection
- request-scoped link prediction
- SPARQL 재생성

예를 들면:

- `relatedEvent + metDuring`
- `visitedAfter + metDuring`

같은 체인이 코드 수준에 먼저 존재한다.

즉, **현재는 OWL schema가 있고, reasoning은 rule/chain driven** 이라고 보는 것이 가장 솔직하다.

#### 11.3 다음 단계 전략

다음 단계는 이 chain logic을 세 층으로 나눠 올리는 것이다.

1. **Schema / ontology layer**
   - class, property, domain/range, subproperty를 더 명확히 한다.

2. **Reasoning rule layer**
   - 구조적으로 표현 가능한 체인은 property chain 또는 rule로 승격한다.
   - 예를 들어 `Content -> relatedEvent -> VisitEvent` 와 `VisitEvent -> metDuring -> Person` 같은 구조는 ontology-aware reasoning 대상이 될 수 있다.

3. **Temporal / uncertainty layer**
   - 하지만 `"통화 후 3시간 이내 방문"` 같은 조건은 pure OWL property chain만으로는 표현하기 어렵다.
   - 이 부분은 RDFox rule, Datalog-style rule, 혹은 SPARQL temporal constraint가 필요하다.

즉, 현실적인 전략은 다음과 같다.

- **순수 구조적 관계**: OWL / rule로 승격
- **시간 간격, confidence, 예측성 관계**: RDFox rule + LP + query-time reasoning 유지

이렇게 설명하면, “2-hop rule을 OWL로 풀겠다”는 말을 과장 없이 더 구체화할 수 있다.

> 제가 해보고 싶은 것은 모든 규칙을 무리하게 OWL에 욱여넣는 게 아니라, 구조적인 chain은 ontology/rule engine 쪽으로 올리고, temporal uncertainty가 큰 부분은 RDFox rules와 link prediction을 함께 쓰는 hybrid reasoning 구조로 정리하는 것입니다.

### 12. LP + R-GCN + TransE 상세 원리

이 부분은 면접에서 가장 기술적으로 깊게 들어갈 수 있는 파트다.

#### 12.1 학습 데이터는 어디서 오는가

학습용 그래프는 크게 두 소스에서 온다.

1. **Fuseki에 적재된 관측 RDF triple**
2. **rule-based predictor가 만든 weak supervision triple**

[app/link_prediction/kg_model_manager.py](../app/link_prediction/kg_model_manager.py) 를 보면:

- 먼저 Fuseki에서 `IRI-IRI` triple만 수집한다.
- 그다음 `weak_supervision.json` 의 high-confidence weak positive를 병합한다.
- 단, 이 weak supervision은 **학습용 graph에만 들어가고**, 운영 KG를 수정하지는 않는다.

이 구분은 매우 중요하다.

- **truth store**: Fuseki
- **training graph augmentation**: weak supervision

#### 12.2 RDF -> PyG graph

[app/link_prediction/graph_builder.py](../app/link_prediction/graph_builder.py) 는 RDF graph를 PyTorch Geometric data로 변환한다.

- node: subject / object IRI
- edge: relation IRI
- `edge_index`: source-target
- `edge_type`: relation id

Literal은 node로 취급하지 않는다.  
즉, 현재 LP는 기본적으로 **entity-event graph 위의 relation completion** 을 다룬다.

#### 12.3 왜 GCN이 아니라 R-GCN인가

[app/link_prediction/gcn_transe_hybrid.py](../app/link_prediction/gcn_transe_hybrid.py) 에서 실제로는 `FastRGCNConv` 를 쓴다.

이유는 KG가 heterogeneous graph이기 때문이다.

- `callee`
- `place`
- `participant`
- `relatedEvent`

같은 relation을 모두 똑같이 aggregation하면 정보가 섞여 버린다.  
R-GCN은 relation type마다 다른 weight를 두고 message passing을 수행하므로, KG 구조에 더 자연스럽다.

쉽게 말하면:

- GCN: "이웃이면 대충 다 비슷하게 본다"
- R-GCN: "어떤 관계를 통해 연결된 이웃인지까지 구분해서 본다"

#### 12.4 TransE scoring은 어떻게 작동하는가

이 프로젝트의 triple score는 TransE 방식이다.

수식으로 쓰면:

`score(h, r, t) = - || e_h + e_r - e_t ||_2`

의미는 다음과 같다.

- head embedding `e_h`
- relation embedding `e_r`
- tail embedding `e_t`

가 있을 때,

- `e_h + e_r` 가
- `e_t` 와 가까우면
- 그 triple이 plausibly true 하다고 본다.

즉, relation을 “translation vector” 로 보는 방식이다.

#### 12.5 학습은 어떻게 시키는가

[app/link_prediction/trainer.py](../app/link_prediction/trainer.py) 에서는 margin ranking loss를 사용한다.

- positive triple score는 높게
- negative triple score는 낮게

되도록 학습한다.

loss는 개념적으로 아래와 같다.

`loss = max(0, margin - score_pos + score_neg)`

negative sampling은 [app/link_prediction/negative_sampling.py](../app/link_prediction/negative_sampling.py) 에서 수행한다.

- 현재 구현은 주로 **tail corruption**
- 즉 `(h, r, t)` 에서 `t` 를 랜덤한 다른 node로 바꾼 negative triple을 만든다.

#### 12.6 후보는 누가 만들어 주는가

이 질문은 면접에서 꼭 나올 수 있다.

정확한 답은 다음과 같다.

> 후보를 외부에서 따로 주는 것이 아니라, 이론상 후보 공간은 KG의 모든 node다.

실제 추론 시에는:

1. `head_uri`, `relation_name` 을 정한다.
2. model이 `predicted_t = h + r` 에 해당하는 predicted tail vector를 만든다.
3. **모든 node embedding** 과의 거리를 계산한다.
4. 거리 기준 top-k를 자른다.
5. 그 후 실사용 수준에서는 `node_type_filter` 와 Fuseki detail lookup으로 후보를 더 좁힌다.

예를 들어:

- `visitedAfter` 는 tail이 VisitEvent여야 하므로 visit 계열만 남기고
- `usedDuring` 는 calendar 계열만 남기고
- `metDuring` 는 person detail lookup이 되는 후보만 남긴다.

즉:

- **이론적 후보 공간**: 전체 node
- **서비스 후보 집합**: relation-specific filter를 통과한 top-k

라고 설명하면 정확하다.

#### 12.7 confidence는 어떻게 만드는가

여기서도 층이 두 개 있다.

1. **embedding model confidence**
   - raw score는 `-distance`
   - manager 단계에서 top candidate score들을 softmax 해 `[0, 1]` confidence처럼 사용

2. **rule-based fallback confidence**
   - `_time_confidence()` 같은 휴리스틱 함수 사용
   - 예: 시간 차이가 짧을수록 더 높은 confidence

즉, 현재 시스템의 confidence는 calibration된 probability라기보다:

- embedding ranking의 상대 confidence
- heuristic confidence

를 함께 쓰는 구조다.

이 부분은 한계이자 개선 포인트다.

#### 12.8 왜 LLM verification이 한 번 더 필요한가

R-GCN + TransE가 구조적으로 plausible한 후보를 잘 찾더라도, 질문 문맥을 완전히 이해하는 것은 아니다.

예:

- 날짜 힌트
- 특정 장소명
- “누구를 만났어?” 같은 질문 의도
- 사진/방문/통화 중 어떤 이벤트를 더 우선시해야 하는지

이런 것은 graph score만으로 충분하지 않을 수 있다.  
그래서 현재 시스템은 **model top-k -> Fuseki context enrichment -> LLM reranking** 구조를 사용한다.

이것을 연구자 표현으로 바꾸면:

> structure-aware candidate generation 뒤에 context-aware candidate reranking을 붙인 형태다.

### 13. 용어 변환표

| 쉬운 표현 | 리서처/엔지니어 표현 |
|---|---|
| 빠진 관계를 추정한다 | request-scoped KG completion |
| 질문에 맞는 엔티티부터 좁힌다 | entity-centric retrieval |
| 시간과 장소를 보고 후보를 다시 고른다 | context-aware candidate reranking |
| 그래프에 없는 경로를 임시로 만든다 | inferred multi-hop path construction |
| 앱 로그를 하나의 구조로 묶는다 | event-centric knowledge representation |
| 기기별 다른 필드를 맞춘다 | schema / attribute alignment |
| 관계까지 앞뒤가 맞는지 본다 | relation consistency / entity-relation co-alignment |
| 규칙 기반 예측 결과를 학습에 보조로 쓴다 | weak supervision for link prediction |

### 14. 면접 전략

#### 14.1 1분 설명 템플릿

> 저는 스마트폰 로그를 이벤트 중심 RDF Knowledge Graph로 구조화하고, 자연어 질문을 SPARQL로 처리하는 개인 KG 프로토타입을 만들었습니다. 핵심은 direct query만으로 답이 안 나오는 sparse 환경을 다루기 위해 request-scoped link prediction을 붙였다는 점입니다. 기존 KG에 없는 관계는 R-GCN + TransE로 top-k 후보를 만들고, LLM이 시간·장소 문맥으로 다시 검증해서 최종 답을 생성합니다. 그래서 제 시스템은 단순 Text2SPARQL이 아니라, sparse personal KG에서 completion과 reasoning을 결합한 구조라고 설명할 수 있습니다.

#### 14.2 3분 설명 템플릿

1. 문제 정의
   - 앱 로그가 통화/방문/사진/일정/앱 사용으로 분리되어 있어 cross-app reasoning이 어렵다.
2. 현재 구현
   - event-centric ontology
   - SPARQL query pipeline
   - sparse relation completion
   - request-scoped prediction + LLM verification
3. 차별점
   - ToG / RoG는 existing path retrieval에 강하지만, 나는 missing relation completion을 먼저 수행한다.
4. 한계
   - single-device prototype
   - chain logic 일부 rule-driven
   - calibration 고도화 필요
5. 다음 단계
   - cross-device schema integration
   - entity profile reranking
   - ontology reasoning + RDFox rules

#### 14.3 alignment 논문은 어떻게 말해야 하는가

이 부분은 특히 주의해야 한다.

잘못된 말:

> 저는 ProLEA 같은 entity alignment 구조를 이미 구현했습니다.

더 좋은 말:

> 현재 프로토타입은 single-device KG query/completion 구조이고, 다음 Phase 2로 Phone / Watch / TV 통합을 가정하면 ProLEA류의 profile-based reranking, Group-Embed-Reason류의 schema alignment, Beyond EA류의 relation consistency 검증이 필요하다고 판단했습니다.

즉, alignment 논문은 **현재 구현 자랑** 이 아니라 **향후 확장 전략의 근거** 로 말해야 한다.

---

## Appendix A. 코드 앵커

- 메인 런타임 entrypoint: [backend/main.py](../backend/main.py)
- route / agent selection: [backend/routes.py](../backend/routes.py)
- supervisor orchestration: [app/agents/kg_agent_supervisor.py](../app/agents/kg_agent_supervisor.py)
- stage pipeline: [app/agents/stages.py](../app/agents/stages.py)
- entity resolution utilities: [app/agents/tools/entity_tools.py](../app/agents/tools/entity_tools.py)
- request-scoped LP: [app/agents/tools/link_prediction_tools.py](../app/agents/tools/link_prediction_tools.py)
- SPARQL generation: [app/agents/tools/sparql_tools.py](../app/agents/tools/sparql_tools.py)
- LP model manager: [app/link_prediction/kg_model_manager.py](../app/link_prediction/kg_model_manager.py)
- R-GCN + TransE model: [app/link_prediction/gcn_transe_hybrid.py](../app/link_prediction/gcn_transe_hybrid.py)
- ontology schema: [data/ontology/ontology.ttl](../data/ontology/ontology.ttl)
- legacy rule-based Text2SPARQL: [app/step4_query/text2sparql_agent.py](../app/step4_query/text2sparql_agent.py)

## Appendix B. 참고 문헌 및 공식 자료

### 현재 구조와 직접 연결되는 축

- Think-on-Graph (ICLR 2024): [link](https://proceedings.iclr.cc/paper_files/paper/2024/hash/10a6bdcabbd5a3d36b760daa295f63c1-Abstract-Conference.html)
- Reasoning on Graphs (ICLR 2024): [link](https://openreview.net/forum?id=ZGNWW7xZ6Q)
- LLM-DA / Temporal KG Reasoning (NeurIPS 2024): [link](https://proceedings.neurips.cc/paper_files/paper/2024/hash/0fd17409385ab9304e5019c6a6eb327a-Abstract-Conference.html)
- GraphRAG (arXiv 2404.16130): [link](https://arxiv.org/abs/2404.16130)
- Samsung Oxford Semantic Technologies 인수 (2024-07-18): [link](https://news.samsung.com/global/samsung-electronics-announces-acquisition-of-oxford-semantic-technologies-uk-based-knowledge-graph-startup)
- Galaxy S25 Personal Data Engine 발표 (2025-01-23): [link](https://news.samsung.com/global/samsung-galaxy-s25-series-sets-the-standard-of-ai-phone-as-a-true-ai-companion)

### Phase 2 확장 전략용 alignment 논문

- ProLEA / Entity Profile Generation and Reasoning with LLMs for Entity Alignment (EMNLP Findings 2025): [link](https://aclanthology.org/2025.findings-emnlp.1093/)
- Group, Embed and Reason / Semantic Attribute Alignment (EMNLP Industry 2025): [link](https://aclanthology.org/2025.emnlp-industry.120/)
- Beyond Entity Alignment / Entity-Relation Synergy (arXiv 2024-07-25): [link](https://arxiv.org/abs/2407.17745)
- EasyEA (ACL Findings 2025): [link](https://aclanthology.org/2025.findings-acl.1080/)
- DAEA (COLING 2025): [link](https://aclanthology.org/2025.coling-main.393/)

---

## 마지막 정리

면접에서 이 프로젝트를 설명할 때 가장 중요한 포인트는 세 가지다.

1. **현재 구현을 정확히 말한다.**
   - event-centric KG
   - SPARQL querying
   - sparse relation completion
   - request-scoped inference

2. **차별점을 분명히 말한다.**
   - existing path retrieval만이 아니라, missing relation completion을 붙였다.

3. **다음 단계를 과장 없이 제시한다.**
   - cross-device integration
   - schema alignment
   - ontology reasoning + RDFox
   - profile-based reranking

이렇게 정리하면, 이 프로젝트는 단순한 toy demo가 아니라  
**개인 KG 질의 시스템의 프로토타입에서, 삼성식 personal data intelligence 방향으로 확장 가능한 구조** 로 설명할 수 있다.
