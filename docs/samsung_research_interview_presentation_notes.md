# 삼성리서치 면접 발표 및 백업 노트

## 사용 방법

이 문서는 같은 포트폴리오를 두 번 발표해야 하는 상황을 기준으로 만들었다.

- 1차 동료/파트장 면접: 기술 검증 중심. 구현 구조, 트레이드오프, GNN/RDF/SPARQL 답변을 준비한다.
- 2차 임원 면접: 기여 가치 중심. 왜 삼성리서치에 맞는지, 입사 후 어떤 문제를 풀 수 있는지를 선명하게 말한다.
- 발표 시간은 20분이지만 실제 스크립트는 15-18분 기준으로 잡는다. 나머지는 화면 전환, 시연, 질문 유도에 쓴다.
- 백업 노트는 발표 때 다 읽지 않는다. 질문이 들어왔을 때 30초 답변으로 먼저 말하고, 더 물으면 90초 설명으로 들어간다.

면접 전체의 핵심 메시지는 다음 한 문장이다.

> 저는 온톨로지 기반 Knowledge Graph와 Multi-agent 시스템을 실제 제조 도메인에서 설계하고 운영해본 엔지니어이고, 이 경험을 바탕으로 삼성의 온디바이스 개인화 KG를 schema-first RDF, Text2SPARQL, sparse relation completion 구조로 발전시키는 데 기여하고 싶습니다.

---

# 1. 1차 동료/파트장용 발표 스크립트

## 발표 전략

1차는 기술 검증 성격이 강하다. 그래서 페이지 4-6의 실무 KG/Agent 경험과 페이지 9-13의 GNN, RDF, SPARQL, prototype 구조를 충분히 설명한다. 다만 모든 원리를 본 발표에서 풀지는 말고, 질문을 받을 수 있는 여지를 남긴다.

권장 시간 배분:

- Pages 1-3: 2분
- Pages 4-6: 5분
- Pages 7-8: 2분
- Pages 9-10: 4분
- Pages 11-15: 5분
- Pages 16-17: 1분
- 시연/전환 여유: 1-2분

## Page 1. Opening

안녕하세요. 온톨로지 기반 Knowledge Graph와 Multi-agent architecture를 중심으로 일해온 김문수입니다.  
저는 제조 도메인에서 KG, Text2SQL, Agent 시스템을 실제 서비스까지 가져간 경험이 있고, 최근에는 이 경험을 개인화 KG와 온디바이스 AI 시나리오로 확장하는 프로토타입을 만들어보았습니다. 발표 시작하겠습니다.

여기서 말하는 온톨로지 기반 KG는 단순히 그래프 DB를 썼다는 뜻이 아닙니다. 데이터의 class, property, domain, range 같은 의미 구조를 먼저 정의하고, 그 위에서 LLM agent가 필요한 관계 경로를 탐색하도록 만든 구조를 의미합니다.

## Page 2. Core Strengths

저의 강점은 크게 세 가지입니다.

첫 번째는 Knowledge Graph와 Ontology 설계 경험입니다. Neo4j, SPARQL, Ontop, RDF/OWL, Triple Store를 모두 실전에서 써봤고, 각각의 장단점을 프로젝트 안에서 직접 겪었습니다.

두 번째는 Multi-agent 시스템 경험입니다. 단순 RAG가 아니라 router, supervisor, planning, schema retrieval, query generation, human-in-the-loop까지 포함한 agent pipeline을 설계하고 운영했습니다.

세 번째는 GNN과 KG completion 경험입니다. 제조 변수 관계 그래프에서 GraphSAGE, GCN 기반 link prediction을 적용했고, 최근에는 Android RDF KG에서 R-GCN + TransE 기반 sparse relation completion 프로토타입을 구현했습니다.

마지막으로 저는 과제 제안을 통해 약 60억 규모의 수주에 기여했고, 12,000명 대상 AI agent 서비스를 운영한 경험이 있습니다. 기술을 실험에서 끝내지 않고 실제 서비스와 조직 성과로 연결해본 점이 제 강점입니다.

## Page 3. Technical Skills

이 페이지는 발표용이라기보다 이력 요약에 가깝습니다.  
핵심만 말씀드리면, 저는 Knowledge Graph, Ontology, Agent architecture, ML/DL을 함께 다루는 엔지니어입니다.

특히 삼성리서치와 연결되는 부분은 RDF/OWL, SPARQL, Triple Store, KG embedding, link prediction, 그리고 KG + LLM integration입니다. 뒤에서 실제 프로젝트와 프로토타입을 통해 어떻게 연결되는지 설명드리겠습니다.

## Page 4. Ontology Multi-Agent Project

제가 현재 몸담고 있는 프로젝트는 데이터 온톨로지와 Multi-agent를 결합한 제조 데이터 탐색 시스템입니다.

이 프로젝트를 시작하게 된 배경은 LG Display 제조 특화 agent를 진행하면서 느낀 한계 때문입니다. 제조 데이터는 설비, 공정, 품질, 지표, 이력 데이터가 서로 복잡하게 연결되어 있는데, 기존에는 파편화된 레거시 데이터와 SQL 중심 접근 때문에 LLM이 정확히 이해하기 어려웠습니다.

문제는 세 가지였습니다.

첫 번째, 파편화된 레거시 데이터 때문에 AI가 읽을 수 있는 의미 구조가 부족했습니다.  
두 번째, 관계가 복잡해지면 단순 SQL만으로는 다차원 관계를 탐색하기 어려웠습니다.  
세 번째, 쿼리 구조가 경직되어 있어 사용자의 자연어 질의를 유연하게 따라가기 어려웠습니다.

이를 해결하기 위해 원천 데이터를 온톨로지 schema의 entity와 relation으로 구조화했고, multi-agent가 KG 위에서 최적 경로를 탐색하도록 만들었습니다. 또한 SPARQL과 Cypher를 모두 사용해보면서 어느 구조가 LLM query generation에 더 적합한지 비교했습니다.

Neo4j를 썼던 가장 큰 이유는 LLM이 SPARQL보다 Cypher를 더 안정적으로 생성했기 때문입니다. 물론 RDF/OWL의 의미론적 장점은 크지만, 당시 고객 환경에서는 정확한 질의 생성과 빠른 시각화가 중요했기 때문에 Neo4j/Cypher가 더 실용적이었습니다.

## Page 5. Circular Supervisor Architecture

다음은 이 구조를 더 발전시킨 내용입니다.

초기에는 supervisor가 정해진 LangGraph node를 순서대로 선택하는 구조였습니다. 하지만 단방향 pipeline으로 만들다 보니, 사용자가 원하지 않는 action도 무조건 실행되는 문제가 있었습니다.

예를 들어 사용자가 "Q150 GLASS와 연관 있는 설비를 알려주고, 그중 가장 많이 거친 설비를 알려줘. 그래프는 출력하지 마"라고 질문하면, graph visualization node는 건너뛰어야 합니다. 그래서 supervisor가 매 step마다 전체 맥락을 보고 다음 action을 능동적으로 결정하는 circular architecture로 전환했습니다.

또 하나의 큰 변화는 저장소 구조였습니다. 처음에는 graph DB에 모든 데이터를 올리는 방향을 고민했지만, 고객 데이터가 하루 10억 건 이상으로 커지면서 graph DB를 전체 저장소로 쓰는 것은 비현실적이었습니다. 그래서 대량 데이터는 RDB에 두고, agent는 ontology graph structure와 schema를 사용해서 필요한 query path를 찾도록 바꾸었습니다.

이 과정에서 Elasticsearch value search를 통해 사용자가 언급한 값과 연결된 entity를 찾고, 그 entity 주변의 N-hop 관계를 확장해서 잠재적으로 연관된 테이블까지 추출하는 구조를 만들었습니다. 중간에는 human-in-the-loop을 넣어 승인, 수정, 중단이 가능하도록 했습니다.

## Page 6. SPARQL, Cypher, SQL 전환 여정

제가 강조하고 싶은 점은 SPARQL, Cypher, SQL을 모두 실제 프로젝트에서 써봤다는 점입니다.

첫 번째 접근은 Protege로 ontology를 만들고 Ontop mapping을 통해 SPARQL을 SQL로 변환하는 virtual KG 방식이었습니다. 기존 RDB를 유지하면서 의미론적 질의를 할 수 있다는 장점이 있지만, 복잡한 SPARQL이 SQL로 변환될 때 성능과 디버깅이 어려운 문제가 있었습니다.

두 번째는 Jena Fuseki에 RDF triple을 적재하고 SPARQL을 생성하는 방식이었습니다. RDF/OWL과 가장 잘 맞지만, LLM이 SPARQL을 안정적으로 생성하는 데는 난이도가 있었습니다.

세 번째는 Neo4j와 Cypher를 사용하는 방식이었습니다. LLM query generation과 graph visualization에는 강점이 있었지만, 대량 레거시 트랜잭션 전체를 graph DB에 넣는 것은 비용과 운영 측면에서 부담이 있었습니다.

마지막으로 현재 프로젝트에서는 RDB를 core storage로 두고 ontology graph는 schema와 path reasoning layer로 활용하는 구조를 사용했습니다.

삼성리서치 관점에서는 Android 로그, 앱 이벤트, 캘린더, 사진, 위치처럼 event 단위 데이터가 많기 때문에 RDF triple store와 SPARQL이 적합하다고 봅니다. 특히 RDFox 같은 RDF 기반 reasoning engine을 활용하면 on-device KG와 semantic reasoning을 연결하기 좋다고 생각합니다.

## Page 7. Hi-D Search

여기부터는 KG보다는 agent와 검색 시스템 경험입니다.  
저는 PM/PL 역할로 약 1년 3개월 동안 제조 특화 agent 프로젝트를 진행했습니다.

목표는 LG Display 사용자가 지표 데이터, 진행 이력, FAQ, 일반 문의를 자연어로 질의하면 정확히 답변하는 것이었습니다. 당시에는 LangChain 품질이 지금보다 안정적이지 않았고, LLM 성능도 제한적이어서 agent pipeline을 대부분 직접 설계했습니다.

구조는 7단계였습니다. 질의 재구성, 대화 맥락 판단, 도메인 라우팅, 핵심 정보 추출, 누락 정보 검증, SQL 생성, 답변 생성 순서입니다.

이 프로젝트는 사업부 best practice로 선정되었고, 12,000명 대상으로 오픈되어 현재까지 운영 중입니다. PI 검수 기준으로 약 95% 정확도를 달성했습니다.

## Page 8. BM25 + LLM Reranking

이 페이지는 추천 질의 로직과 삼성 개인화 연결점입니다.

저는 사용자별 추천 질의를 2-stage ranking으로 만들었습니다. 1차는 BM25 기반 후보 추출입니다. 기본 BM25 점수에 사용자의 의도 도메인, 시간 감쇠, 자주 등장한 토큰 가중치를 곱해 개인화했습니다.

예를 들어 사용자가 최근 지표 질의를 많이 했다면 지표 도메인 질문에 가중치를 주고, 최근에 물어본 질문일수록 time decay로 더 높은 점수를 주는 방식입니다.

2차에서는 LLM이 후보 리스트를 다시 보고 문맥에 맞는 추천 질의를 재정렬했습니다.

삼성 개인화와 연결하면, 사용자가 빅스비나 온디바이스 agent를 호출했을 때 시간, 장소, 빈도, 과거 패턴을 기반으로 선제적 추천을 만들 수 있습니다. 예를 들어 출근 중에는 교통 알림, 지인 생일 근처에는 메시지/캘린더/사진을 연결한 카드 제안, 방문 장소 이후에는 리뷰나 기록 회상 추천을 할 수 있습니다.

## Page 9. GNN Link Prediction - Manufacturing

이 페이지는 제가 GNN을 사용한 첫 번째 경험입니다.

LG Energy Solution 프로젝트에서 목표는 특정 Y 변수에 대해 유의한 X 변수를 ranking하는 것이었습니다. 저는 이를 두 가지 방식으로 풀었습니다. 하나는 AutoML 기반 중요 변수 추출이고, 다른 하나는 변수 간 관계를 graph로 만들고 link prediction 관점에서 유의 관계를 ranking하는 방식이었습니다.

먼저 사용자가 Y와 X 후보 변수를 선택하면 상관계수를 계산하고, 특정 threshold 이상이면 edge가 있다고 정의했습니다. 이 threshold는 현업과 논의해서 정했습니다.

초기에는 Pearson 상관계수와 GraphSAGE를 사용했지만 성능 한계가 있었습니다. 이후 Spearman 상관계수를 적용해 비선형적인 단조 관계를 더 잘 포착했고, graph embedding 모델도 GCN 계열로 바꾸면서 AUC를 개선했습니다.

여기서 AUC를 본 이유는 link prediction 데이터가 본질적으로 불균형하기 때문입니다. 실제 연결된 노드 쌍보다 연결되지 않은 노드 쌍이 훨씬 많기 때문에 accuracy만 보면 대부분을 "연결 안 됨"으로 찍어도 높게 나올 수 있습니다. AUC는 positive edge가 negative edge보다 더 높은 점수를 받는지를 ranking 관점에서 평가하기 때문에 이 문제에 더 적합했습니다.

## Page 10. Android RDF KG - Hybrid Link Prediction

제가 GNN을 사용한 두 번째 경험은 Android RDF KG에 link prediction을 적용한 프로토타입입니다.

제가 삼성리서치에 입사한다면 Android 로그를 RDF로 만들고, 사용자의 자연어 회상 질의에 답변하는 personal KG agent를 만들고 싶습니다. 이걸 직접 프로토타입으로 만들어보면서 느낀 가장 큰 문제는 개인 KG가 매우 sparse하다는 점이었습니다.

예를 들어 "이 사진이 찍힌 장소 방문 때 누구를 만났어?"라는 질문이 들어오면, KG에는 사진, 방문, 사람, 통화 이벤트가 부분적으로만 연결되어 있을 수 있습니다. 단순 SPARQL은 triple이 없으면 결과가 0건입니다. 그래서 누락된 edge를 추론해주는 장치가 필요했습니다.

구조는 R-GCN + TransE + LLM verifier입니다.

R-GCN은 RDF predicate를 edge type으로 보고 relation-aware node embedding을 학습합니다. 예를 들어 `callee`, `place`, `capturedPlace`, `relatedEvent`, `metDuring`은 각각 다른 relation id로 들어가고, R-GCN은 relation마다 다른 message passing weight를 사용합니다.

그 위에서 TransE는 `(head, relation, tail)` triple이 얼마나 그럴듯한지 `h + r`이 `t`에 가까운지를 기준으로 점수화합니다. 즉 `(photo_001, relatedEvent, ?)` 같은 형태로 tail 후보를 ranking할 수 있습니다.

마지막으로 LLM verifier가 top-K 후보를 시간, 장소, 사용자 질의 문맥으로 검증합니다. embedding 모델은 구조적 유사성을 잘 보지만, "4월 17일 투썸플레이스" 같은 자연어 문맥까지 완전히 이해하는 것은 아니기 때문에 LLM 검증을 붙였습니다.

중요한 점은 예측한 triple을 운영 KG에 바로 저장하지 않는다는 것입니다. request scope에서만 후보로 사용하고, 선택된 URI를 `VALUES`로 고정해 SPARQL을 다시 생성합니다. 그래서 hallucinated edge가 KG에 영구 오염되는 것을 막았습니다.

현재 한계도 있습니다. 멀티홉 chain은 일부 시나리오를 rule로 감지하고 있고, confidence는 calibrated probability가 아니라 후보군 내 softmax 점수입니다. 앞으로는 OWL property chain이나 RDFox rule reasoning으로 일반화할 계획입니다.

## Page 11. On-device Personal Context Engine

이제 이 프로토타입을 삼성리서치에 어떻게 연결할 수 있는지 설명드리겠습니다.

제가 만들고 싶은 것은 스마트폰 안에서 사용자의 개인 맥락을 기억하고 자연어로 회상 검색하는 personal graph memory입니다.

일반 RAG는 문장 유사도 기반 검색에는 강하지만, "어제 김철수랑 통화하고 나서 들른 카페", "회의 끝나고 찍은 사진", "지난주 그 장소에서 만난 사람"처럼 시간, 장소, 사람, 이벤트가 얽힌 관계 추론에는 약합니다.

반면 RDF 기반 personal KG는 event를 중심으로 사람, 장소, 앱, 콘텐츠, 시간을 연결할 수 있기 때문에 N-hop 탐색과 근거 경로 제시가 자연스럽습니다. 사용자가 "왜 그렇게 답했어?"라고 물었을 때도 CallEvent, VisitEvent, PhotoEvent 같은 경로를 설명할 수 있습니다.

## Page 12. Schema-first Personal KG

이 페이지의 핵심은 event-centric RDF입니다.

기존 data-first 방식은 테이블 중심으로 데이터를 보고 SQL 변환을 우선합니다. 하지만 personal KG에서는 event를 1급 엔티티로 올리는 것이 중요합니다.

예를 들어 사용자가 김철수와 통화했다는 사실을 `user -> called -> KimChulSu`처럼 direct edge로만 만들면 언제 통화했는지, 얼마나 통화했는지, 그 직후 어디를 방문했는지, 어떤 원천 로그에서 왔는지 붙이기 어렵습니다.

그래서 `CallEvent`, `VisitEvent`, `AppUsageEvent`, `PhotoContent` 같은 event node를 중심에 두고, 여기에 user, person, place, app, time, provenance를 붙이는 방식이 더 적합합니다.

Android 환경의 장점은 API와 로그 구조가 비교적 고정되어 있다는 점입니다. CallLog, UsageEvents, Calendar Instances 같은 source schema를 중간 정규화 레이어로 만들고, 이를 RDF schema에 매핑하면 schema-first triple ingestion pipeline을 만들기 좋습니다.

## Page 13. Retrieval-first Text2SPARQL Agent

이 페이지는 agent flow입니다.

사용자 질의가 들어오면 먼저 intent, time expression, target type을 분석합니다. 그다음 문자열을 바로 URI로 매핑하지 않고 Elasticsearch나 on-device SQLite FTS5를 통해 candidate entity를 검색합니다.

예를 들어 "스타벅스"라는 표현은 브랜드일 수도 있고, 특정 매장일 수도 있고, 과거 방문 기록일 수도 있습니다. 그래서 candidate를 만들고, LLM이 문맥에 맞는 entity를 고른 뒤 seed entity를 구성합니다.

그다음 전체 schema를 모두 프롬프트에 넣는 것이 아니라, 선택된 entity와 관련된 class/property만 top-K로 가져오는 schema retrieval을 목표로 합니다. 현재 프로토타입에서는 이 부분이 완전히 구현된 것은 아니고, 회사 프로젝트에서 이미 구현했던 value search + N-hop schema expansion 방식을 이 personal KG 구조에 적용할 계획입니다.

확정된 schema와 entity를 기반으로 SPARQL을 생성하고 실행합니다. 결과가 나오면 바로 답변하고, 결과가 0건이면 link prediction stage로 넘어가 sparse relation을 보완합니다.

## Page 14. Scenario Demo

여기서는 세 가지 시나리오를 짧게 보여드리겠습니다.

첫 번째는 single-hop입니다. 예를 들어 "어제 김철수와 통화한 기록이 있어?"처럼 이미 KG에 존재하는 triple을 SPARQL로 바로 조회하는 케이스입니다.

두 번째는 1-hop link prediction입니다. 예를 들어 "김철수랑 통화하고 나서 어디 갔어?"라고 물었는데 `CallEvent -> visitedAfter -> VisitEvent` triple이 없으면, R-GCN+TransE가 visit 후보를 만들고 LLM이 시간/장소 맥락으로 검증합니다.

세 번째는 2-hop입니다. 예를 들어 "4월 17일 투썸플레이스에서 찍은 사진이랑 연결된 방문에서 누구 만났어?"라는 질문입니다. 이 경우 `photo -> relatedEvent -> visit -> metDuring -> person` 경로가 필요합니다. 현재 프로토타입에서는 이 chain을 감지해 1차 LP로 visit을 예측하고, 2차 LP로 person을 예측한 뒤, 최종적으로 `VALUES` SPARQL을 재생성합니다.

## Page 15. Technology Roadmap

입사 후 로드맵은 세 단계로 생각하고 있습니다.

Phase 1은 시스템 구축입니다. Event-centric RDF ontology를 설계하고, Android source schema를 RDF triple로 적재하는 pipeline을 만들고, retrieval-first Text2SPARQL agent와 기본 시나리오를 서비스화하는 단계입니다. 여기에 on-device 경량화와 hybrid link prediction prototype을 붙일 수 있습니다.

Phase 2는 데이터 통합입니다. Phone, Watch, TV처럼 서로 다른 device와 app schema를 하나의 personal KG로 통합하려면 entity alignment뿐 아니라 schema/attribute alignment가 핵심입니다. 여기서는 동일 사용자 식별, device별 schema 통합, relation consistency 검증이 필요합니다.

Phase 3은 고도화입니다. 반복 패턴 기반 선제 알림, context-aware recommendation, privacy-preserving on-device learning으로 확장할 수 있습니다.

제가 기여할 수 있는 지점은 KG schema 설계, Text2SPARQL agent, sparse KG completion, 그리고 실제 서비스형 agent 운영 경험입니다.

## Page 16. Background

마지막으로 제 배경입니다.

저는 LG CNS에서 Best CNSER 수상, 핵심인재 선정, 조기 책임 진급 대상자로 인정받았습니다. 이는 단순히 모델을 만드는 역량뿐 아니라, 과제를 제안하고, 고객과 논의하고, 팀을 리딩하고, 서비스를 운영하는 역량을 함께 검증받은 결과라고 생각합니다.

## Page 17. Closing

정리하겠습니다.

저는 온톨로지 기반 KG 설계, SPARQL/Cypher/SQL 전환 경험, Multi-agent 시스템 구현 및 운영, GNN 기반 link prediction 경험을 가지고 있습니다.  
삼성리서치에서 개인화 AI와 온디바이스 KG가 중요해지는 시점에, 저는 schema-first RDF personal KG와 LLM agent를 연결하는 실전형 연구 엔지니어로 기여하고 싶습니다.

감사합니다.

---

# 2. 2차 임원용 발표 스크립트

## 발표 전략

2차는 기술의 깊이를 모두 설명하기보다, "이 사람이 삼성리서치에서 어떤 문제를 책임지고 풀 수 있는가"를 보여주는 자리로 잡는다. 세부 원리는 질문이 들어오면 백업 노트로 답한다.

권장 시간 배분:

- 자기 포지셔닝: 2분
- 실전 프로젝트 성과: 5분
- 삼성리서치 기여 방향: 6분
- 로드맵과 마무리: 2분

## Opening

안녕하세요. 저는 Knowledge Graph, Ontology, Multi-agent 시스템을 실제 제조 도메인에서 설계하고 운영해온 김문수입니다.

저를 한 문장으로 말씀드리면, 복잡한 데이터를 AI가 이해할 수 있는 구조로 바꾸고, 그 위에서 agent가 안정적으로 추론하도록 만드는 엔지니어입니다.

오늘 발표에서는 제가 해온 실전 경험과, 이 경험을 삼성의 온디바이스 개인화 AI에 어떻게 연결할 수 있을지 말씀드리겠습니다.

## Core Strength

제 강점은 세 가지입니다.

첫 번째는 온톨로지와 KG 설계 경험입니다. 단순히 graph DB를 써본 것이 아니라, legacy data를 entity/relation schema로 구조화하고, query path를 설계하고, SPARQL/Cypher/SQL의 트레이드오프를 직접 겪었습니다.

두 번째는 agent 시스템을 실제 서비스로 운영한 경험입니다. 12,000명 대상 제조 특화 agent를 오픈했고, PI 검수 기준 95% 정확도를 달성했습니다.

세 번째는 연구 요소를 프로토타입으로 빠르게 검증하는 능력입니다. 제조 변수 관계 그래프에서 GNN을 적용했고, 최근에는 Android RDF KG에 R-GCN + TransE link prediction을 적용해 개인 KG sparse 문제를 풀어보았습니다.

## Project Experience

제조 도메인에서 가장 어려웠던 문제는 데이터가 많다는 것보다, 데이터 사이의 관계를 AI가 이해할 수 없다는 점이었습니다.

설비, 공정, 품질, 지표, 이력 데이터가 서로 분리되어 있으면 LLM은 많은 프롬프트와 few-shot에 의존하게 되고, 복잡한 관계 질의에서는 hallucination이 발생하기 쉽습니다.

그래서 저는 원천 데이터를 온톨로지 schema로 구조화하고, multi-agent가 KG 위에서 필요한 경로를 탐색하게 했습니다. 초기에는 Neo4j/Cypher를 썼고, 대량 데이터 한계를 겪은 뒤 RDB를 core storage로 두고 ontology graph를 schema/path reasoning layer로 쓰는 방향까지 경험했습니다.

이 과정에서 얻은 결론은 명확합니다. AI agent가 안정적으로 동작하려면, 문서 검색만이 아니라 데이터의 의미 구조와 관계 경로를 함께 제공해야 합니다.

## Samsung Connection

이 경험은 삼성의 개인화 AI와 직접 연결된다고 생각합니다.

스마트폰에는 통화, 캘린더, 사진, 위치, 앱 사용 기록처럼 사용자의 맥락을 설명하는 event data가 계속 쌓입니다. 하지만 이 데이터를 단순 로그나 문서 형태로만 보면 "어제 통화하고 나서 들른 곳", "그 장소에서 찍은 사진", "그때 만난 사람" 같은 질문에 안정적으로 답하기 어렵습니다.

그래서 저는 event-centric RDF personal KG가 필요하다고 봅니다. CallEvent, VisitEvent, AppUsageEvent, PhotoContent 같은 event를 중심에 두고 user, person, place, app, time을 연결하면, 자연어 회상 검색과 근거 경로 설명이 가능해집니다.

또한 개인 KG는 본질적으로 sparse합니다. 모든 관계가 명시적으로 저장되어 있지는 않습니다. 그래서 저는 R-GCN + TransE로 누락된 관계 후보를 만들고, LLM이 시간/장소 문맥으로 검증하는 hybrid 구조를 프로토타입으로 구현했습니다.

중요한 것은 예측 결과를 KG에 바로 써넣지 않는다는 점입니다. request scope에서만 후보를 쓰고, SPARQL을 다시 생성해 답변합니다. 개인화 시스템에서는 신뢰성과 추적 가능성이 중요하기 때문에 이 구조가 적합하다고 생각합니다.

## Roadmap

입사 후에는 세 단계로 기여할 수 있다고 생각합니다.

Phase 1은 schema-first personal KG 구축입니다. Android source schema를 event-centric RDF로 매핑하고, Text2SPARQL agent와 기본 회상 시나리오를 서비스화하는 것입니다.

Phase 2는 cross-device integration입니다. Phone, Watch, TV 데이터가 합쳐지려면 동일 사용자와 동일 이벤트를 맞추는 entity alignment도 필요하지만, 더 근본적으로는 device별 schema와 attribute를 통합해야 합니다. 이 부분은 제가 온톨로지와 schema 설계를 해온 경험으로 기여할 수 있습니다.

Phase 3은 context-aware proactive AI입니다. 사용자의 반복 패턴과 현재 맥락을 기반으로 선제 알림과 추천을 제공하는 방향입니다.

## Closing

저는 연구 아이디어를 실제 시스템으로 만들고, 실제 서비스에서 검증해본 경험이 있습니다.  
삼성리서치에서 개인화 AI가 더 깊은 사용자 맥락을 이해해야 하는 시점에, 저는 Knowledge Graph, Ontology, Agent, GNN을 연결하는 실전형 엔지니어로 기여하고 싶습니다.

감사합니다.

---

# 3. 페이지별 백업 설명 노트

## Page 9. AUC 설명

질문 트리거:

- "왜 accuracy가 아니라 AUC를 봤나요?"
- "유의인자 ranking에서 AUC가 무슨 의미인가요?"

30초 답변:

> Link prediction은 positive edge보다 negative pair가 훨씬 많은 불균형 문제입니다. Accuracy만 보면 대부분을 "연결 안 됨"으로 예측해도 높게 나올 수 있습니다. 그래서 저는 실제 연결된 노드 쌍이 연결되지 않은 노드 쌍보다 더 높은 점수를 받는지, 즉 ranking 품질을 보기 위해 AUC를 사용했습니다.

90초 설명:

> AUC는 맞다/틀리다를 특정 threshold로 자르는 지표라기보다, positive sample이 negative sample보다 높은 score를 받을 확률에 가깝습니다. 제가 만든 변수 그래프에서는 실제 edge가 있는 변수쌍의 embedding score가 높고, edge가 없는 변수쌍의 score가 낮아야 합니다. 그래서 AUC가 높다는 것은 임베딩 공간이 그래프의 구조적 유사성을 잘 보존하고 있다는 뜻으로 해석했습니다. 제조 데이터에서는 연결되지 않은 노드쌍이 압도적으로 많기 때문에 accuracy보다 AUC가 더 직관적인 평가 지표였습니다.

주의할 표현:

- "AUC가 높으니 무조건 좋은 모델입니다"라고 말하지 않는다.
- "AUC는 ranking 관점의 지표이고, 실제 서비스에서는 threshold와 현업 검증이 추가로 필요합니다"라고 덧붙인다.

## Page 9. GraphSAGE와 GCN 차이

질문 트리거:

- "GraphSAGE를 왜 썼고 왜 바꿨나요?"
- "GraphSAGE와 GCN 차이를 설명해보세요."

30초 답변:

> GraphSAGE는 이웃 node feature를 sampling해서 aggregate하는 데 강점이 있는 inductive 모델입니다. 대규모 그래프와 새로운 노드 대응에 유리합니다. 반면 GCN은 인접 행렬 기반으로 연결된 이웃 정보를 정규화해 전체 topology를 더 부드럽게 반영합니다. 제조 변수 그래프에서는 새로운 노드가 계속 들어오는 문제보다, 정적인 변수 관계 구조를 잘 보존하는 것이 더 중요해서 GCN 계열이 더 적합했습니다.

90초 설명:

> GraphSAGE의 핵심은 모든 이웃을 보지 않고 고정된 수의 이웃을 sampling해 평균, pooling, LSTM 같은 aggregator로 요약하는 것입니다. 그래서 매우 큰 graph에서도 연산량을 제어할 수 있고, 학습 때 보지 못한 새 node도 주변 이웃 feature만 있으면 embedding할 수 있습니다. 다만 무작위 sampling 때문에 edge의 전체 위상 구조를 온전히 반영하지 못할 수 있습니다.  
> GCN은 normalized adjacency matrix를 사용해 연결된 이웃의 정보를 propagation합니다. 이웃이 많은 node의 영향은 degree normalization으로 조정하고, 여러 layer를 거치며 그래프 구조가 embedding에 부드럽게 반영됩니다. 제조 변수 그래프처럼 node와 edge가 비교적 정적이고, 전체 correlation topology를 반영하는 것이 중요한 경우에는 GCN 계열이 더 좋은 선택이 될 수 있다고 판단했습니다.

주의할 표현:

- "GraphSAGE가 나쁘다"가 아니라 "문제 조건이 달랐다"로 말한다.
- 대규모 동적 그래프나 inductive setting에서는 GraphSAGE가 여전히 강점이 있다고 인정한다.

## Page 9. Negative Sampling

질문 트리거:

- "Negative sampling을 왜 했나요?"
- "negative가 많아서 불균형을 맞춘 건가요?"

30초 답변:

> 맞습니다. 모든 연결되지 않은 노드쌍을 negative로 쓰면 수가 너무 많고 학습이 비효율적입니다. 그래서 positive edge 하나에 대해 일부 tail을 깨뜨린 negative sample을 만들고, positive triple의 score는 높이고 negative triple의 score는 낮추도록 학습했습니다.

90초 설명:

> Graph link prediction에서는 관측된 edge가 positive이고, 관측되지 않은 대부분의 node pair는 negative 후보입니다. 하지만 전체 negative를 다 쓰면 계산량이 너무 커지고, positive/negative 불균형도 심해집니다. 그래서 학습 batch에서 `(head, relation, tail)` positive triple을 두고 tail을 random node로 바꾼 corrupted triple을 negative로 샘플링합니다. 모델은 positive score가 negative score보다 margin만큼 높아지도록 학습합니다.  
> 즉 줄이는 것은 내적값 자체가 아니라 loss입니다. positive pair는 score를 키워 loss를 줄이고, negative pair는 score를 낮춰 loss를 줄입니다. 이 방식은 모든 negative를 다 보지 않고도 ranking boundary를 학습하게 해줍니다.

주의할 표현:

- "관측되지 않은 edge가 모두 진짜 negative"라고 단정하지 않는다.
- KG에서는 closed-world assumption이 위험하므로 "negative candidate로 샘플링했다"고 말한다.

## Page 10. 현재 코드 기준 R-GCN + TransE 구조

질문 트리거:

- "R-GCN이 relation마다 다르게 학습된다는 게 코드에 어떻게 들어가 있나요?"
- "TransE는 정확히 어떤 역할인가요?"
- "후보 link는 누가 만들어주나요?"

30초 답변:

> 현재 구현에서는 RDF triple 중 subject와 object가 URI인 것만 graph edge로 만들고, predicate URI마다 relation id를 부여합니다. 이 relation id가 `edge_type`으로 R-GCN에 들어갑니다. R-GCN은 relation type별 message passing으로 node embedding을 만들고, TransE는 `h + r`이 어떤 tail embedding에 가까운지 계산해 top-K tail 후보를 ranking합니다. 이후 LLM verifier가 시간/장소/질의 문맥으로 최종 후보를 선택합니다.

90초 설명:

> 구현 흐름은 네 단계입니다.  
> 첫째, RDF graph builder가 Fuseki에서 가져온 URI-URI triple을 PyTorch Geometric graph로 변환합니다. 이때 subject와 object는 node index가 되고, predicate URI는 relation index가 됩니다. 예를 들어 `log:callee`, `log:place`, `log:relatedEvent`, `log:metDuring`이 각각 다른 relation id가 됩니다.  
> 둘째, R-GCN forward에 `edge_index`와 `edge_type`을 함께 넣습니다. 그래서 같은 이웃이라도 `callee` edge로 들어온 정보와 `place` edge로 들어온 정보가 다른 relation weight를 통해 집계됩니다. 이것이 vanilla GCN과 다른 점입니다.  
> 셋째, 학습은 observed triples와 weak supervision triples를 positive로 두고, tail을 random node로 바꾼 negative triples를 만듭니다. positive triple의 TransE score가 negative triple보다 margin만큼 높아지도록 margin ranking loss를 사용합니다.  
> 넷째, inference에서는 `(head, relation, ?tail)` 형태로 질문합니다. 모델은 `h + r` 벡터를 만들고, 전체 node embedding 중 이 벡터와 가장 가까운 tail 후보를 top-K로 뽑습니다. 실사용에서는 `visit`, `photo`, `cal_` 같은 URI/type filter로 후보 공간을 줄입니다.

현재 코드 기준으로 말할 수 있는 구조:

- `graph_builder.py`: RDF predicate URI -> relation id, `edge_type` 생성
- `gcn_transe_hybrid.py`: `FastRGCNConv(..., num_relations)`와 TransE score `-||h + r - t||`
- `trainer.py`: negative sampling + margin ranking loss
- `kg_model_manager.py`: Fuseki observed triples + weak supervision을 학습용 graph에 병합
- `predictor.py`: node embedding을 캐싱하고 tail 후보를 ranking
- `link_prediction_tools.py`: relation별 head 후보 조회, embedding prediction, rule fallback, 2-hop chain 처리
- `stages.py`: query analysis, LLM verifier, LP stage, `VALUES` SPARQL 재생성

주의할 표현:

- "confidence가 확률입니다"라고 말하지 않는다. 현재는 후보군 score를 softmax한 ranking confidence다.
- "모든 관계를 완벽히 예측합니다"라고 말하지 않는다. sparse KG 보완 후보를 생성하고 LLM이 검증하는 구조라고 말한다.

## Page 10. Agent가 비어 있는 관계를 판단하는 흐름

질문 트리거:

- "언제 link prediction이 실행되나요?"
- "SPARQL과 LP는 어떤 순서로 연결되나요?"

30초 답변:

> 먼저 LLM과 rule이 질의에서 필요한 relation 또는 2-hop chain을 감지합니다. 그다음 SPARQL을 먼저 실행합니다. 결과가 있으면 그대로 답하고, 결과가 0건이거나 sparse하면 link prediction stage가 실행됩니다. LP가 후보 triple을 만들면 LLM이 검증하고, 선택된 URI를 `VALUES`로 고정해 SPARQL을 다시 생성합니다.

90초 설명:

> 예를 들어 "4월 17일 투썸플레이스에서 찍은 사진이랑 연결된 방문에서 누구 만났어?"라는 질문은 `relatedEvent + metDuring` 2-hop chain으로 감지됩니다.  
> 1차로 `(photo, relatedEvent, ?visit)`를 예측해서 방문 후보를 만들고, LLM이 가장 그럴듯한 visit을 선택합니다. 이 visit을 intermediate node로 저장합니다.  
> 2차로 `(visit, metDuring, ?person)`을 예측해서 사람 후보를 만들고, 다시 LLM이 선택합니다.  
> 마지막으로 예측된 URI를 운영 KG에 쓰지 않고, 해당 request 안에서만 `VALUES`로 고정해 SPARQL을 재생성합니다. 이 방식은 예측 기반 답변을 가능하게 하면서도 KG 자체를 오염시키지 않습니다.

## Page 10. 이 구조가 합당한 이유와 한계

질문 트리거:

- "왜 R-GCN + TransE + LLM 조합이 적합한가요?"
- "이 구조의 한계는 무엇인가요?"

30초 답변:

> 개인 KG는 relation type이 다양하고 관측 triple이 sparse합니다. R-GCN은 RDF predicate별 relation-aware embedding을 만들 수 있고, TransE는 빠르게 tail 후보를 ranking할 수 있습니다. 다만 embedding만으로 시간/장소/자연어 문맥을 완전히 판단하기 어렵기 때문에 LLM verifier를 붙였습니다. 현재 한계는 multi-hop chain 일부가 rule 기반이고, confidence가 calibrated probability는 아니라는 점입니다.

90초 설명:

> 이 구조는 세 역할이 분리되어 있어 합리적입니다. R-GCN은 KG의 heterogeneous relation structure를 학습합니다. TransE는 link prediction scorer로서 `(head, relation, tail)` plausibility를 빠르게 계산합니다. LLM은 사용자의 자연어 질의와 시간/장소 문맥을 해석해 top-K 후보 중 최종 선택을 합니다.  
> 특히 personal KG에서는 모든 관계를 명시적으로 저장하기 어렵습니다. 사진과 방문, 통화와 방문, 방문과 만남 같은 관계는 로그에는 따로 존재하지만 명시 edge로 없을 수 있습니다. 그래서 KG completion이 필요합니다.  
> 한계도 분명합니다. 현재 literal time 자체가 R-GCN embedding에 직접 들어가는 구조는 아니고, 시간 신뢰도는 rule fallback이나 LLM verifier 쪽에서 강하게 쓰입니다. 또 2-hop chain은 현재 일부 시나리오를 rule로 감지합니다. 향후에는 OWL property chain, RDFox rule, temporal KG embedding을 결합해 일반화할 계획입니다.

## Page 11. Personal KG가 필요한 이유

질문 트리거:

- "그냥 RAG로 하면 안 되나요?"
- "개인화에 KG가 왜 필요한가요?"

30초 답변:

> RAG는 문장 유사도 검색에는 강하지만, 시간, 장소, 사람, 이벤트가 얽힌 관계 경로를 찾는 데는 한계가 있습니다. personal KG는 CallEvent, VisitEvent, PhotoContent 같은 event를 중심으로 맥락을 연결하기 때문에 "통화 후 방문", "그 장소에서 찍은 사진", "그때 만난 사람" 같은 회상 질의에 더 적합합니다.

90초 설명:

> 예를 들어 "지난주 회의 끝나고 들른 카페"라는 질문은 단순히 "카페"라는 단어와 유사한 문서를 찾는 문제가 아닙니다. 회의 이벤트의 종료 시각, 이후 방문 이벤트, 장소 타입이 cafe인지, 사용자와 연결된 기록인지가 모두 필요합니다. KG는 이 관계를 graph path로 표현할 수 있고, SPARQL은 이 path를 직접 조회할 수 있습니다. 또한 답변 근거를 `CalendarEvent -> VisitEvent -> Place`처럼 설명할 수 있어 신뢰성이 높습니다.

## Page 12. Event-centric RDF와 direct edge 비교

질문 트리거:

- "왜 event를 1급 엔티티로 올리나요?"
- "그냥 user와 place를 직접 연결하면 안 되나요?"

30초 답변:

> 직접 edge는 단순하지만 시간, duration, provenance, 후속 이벤트를 붙이기 어렵습니다. personal KG에서는 통화, 방문, 앱 사용, 사진 촬영 같은 event를 중심 노드로 두어야 시간과 근거를 함께 표현할 수 있습니다.

90초 설명:

> `user -> visited -> place`처럼 만들면 사용자가 장소를 방문했다는 사실은 표현되지만, 언제 방문했는지, 어떤 로그에서 왔는지, 그 직전에 누구와 통화했는지, 그 장소에서 어떤 사진을 찍었는지 연결하기 어렵습니다. 반면 `VisitEvent`를 만들고 `visitor`, `place`, `visitedAt`, `wasDerivedFrom`을 붙이면 event 중심으로 모든 맥락을 확장할 수 있습니다.  
> 그래서 저는 Android source log를 먼저 `call_log`, `app_usage_event`, `calendar_instance` 같은 중간 정규화 layer로 만들고, 이를 RDF event ontology로 매핑하는 방식을 생각하고 있습니다.

## Page 12. RDF/SPARQL 도메인 테스트 핵심

### `rdf:type`

30초 답변:

> `rdf:type`은 인스턴스가 어떤 클래스에 속하는지 선언하는 predicate입니다. 예를 들어 `data:call_245 rdf:type log:CallEvent`는 `call_245`라는 실제 이벤트가 `CallEvent` 클래스의 인스턴스라는 뜻입니다.

### URI와 literal

30초 답변:

> URI는 다른 엔티티와 계속 연결될 수 있는 식별자이고, literal은 날짜, 숫자, 문자열 같은 값입니다. 사람, 장소, 앱, 이벤트는 URI로 두고, duration이나 timestamp는 literal로 두는 것이 일반적입니다.

### Turtle의 `a`와 `;`

30초 답변:

> Turtle에서 `a`는 `rdf:type`의 축약이고, `;`는 같은 subject에 여러 predicate-object를 이어 쓸 때 사용하는 축약 문법입니다. RDF 의미는 모두 subject-predicate-object triple의 집합입니다.

### Prefix

30초 답변:

> prefix는 긴 URI를 짧게 쓰기 위한 alias입니다. 보통 `data:`는 실제 인스턴스, `log:`는 ontology class/property, `xsd:`는 datatype, `rdfs:`는 label 같은 표준 vocabulary, `prov:`는 provenance vocabulary로 씁니다.

### PROV-O

30초 답변:

> PROV-O는 데이터의 출처와 생성 과정을 표현하는 W3C provenance ontology입니다. 예를 들어 `event/call_245 prov:wasDerivedFrom raw/calllog_row_245`라고 두면 이 RDF event가 어떤 원천 로그에서 왔는지 추적할 수 있습니다.

### OWL-Time

30초 답변:

> 단순 timestamp는 `xsd:dateTime` literal로도 충분하지만, interval, duration, before/after 같은 시간 관계를 표준적으로 다루려면 OWL-Time을 사용할 수 있습니다.

### R2RML/RML

30초 답변:

> R2RML은 관계형 DB를 RDF로 매핑하는 W3C 표준이고, RML은 이를 CSV, JSON, XML 같은 이기종 소스로 확장한 매핑 언어입니다. Android 로그가 DB, JSON, CSV로 섞여 있을 수 있기 때문에 실무적으로는 RML까지 고려할 수 있습니다.

## Page 13. Schema Retrieval 현재/목표 구분

질문 트리거:

- "Schema retrieval이 실제로 구현되어 있나요?"
- "전체 schema를 넣는 것과 뭐가 다른가요?"

30초 답변:

> 현재 personal KG 프로토타입에서는 schema retrieval이 완전 구현된 상태는 아닙니다. 다만 회사 프로젝트에서는 value search 후 seed entity를 만들고, 그 주변 N-hop graph structure와 관련 schema를 추출하는 구조를 이미 구현했습니다. 이 경험을 personal KG에 적용해 전체 schema가 아니라 선택된 entity와 관련된 class/property만 top-K로 넣는 방향입니다.

90초 설명:

> 예를 들어 "김철수와 간 카페가 어디야?"라는 질문이 들어오면 먼저 김철수와 카페라는 표현을 분석합니다. 그다음 value search로 `person/KimChulSu`, `Cafe`, 과거 방문 place 후보를 찾고, LLM이 문맥상 필요한 seed entity를 보강합니다. 이 seed entity 주변의 class와 property만 추출하면 프롬프트가 작아지고, Text2SPARQL이 잘못된 property를 쓰는 위험도 줄어듭니다.  
> 현재 포트폴리오에서는 target architecture로 표현되어 있고, 현 프로젝트 경험상 구현 가능한 부분이라고 구분해서 말하는 것이 좋습니다.

주의할 표현:

- "이미 personal KG에 완전 구현했습니다"라고 말하지 않는다.
- "회사 프로젝트에서 구현한 schema/path retrieval 경험을 personal KG로 이식할 계획입니다"라고 말한다.

## Page 14. 시연 설명 카드

### Single-hop

> 이미 KG에 존재하는 triple을 SPARQL로 바로 조회하는 케이스입니다. 예를 들어 특정 사람과의 통화 기록, 특정 앱 사용 기록처럼 명시된 event property를 가져옵니다.

### 1-hop LP

> `CallEvent -> VisitEvent`처럼 명시 edge가 없는 경우입니다. SPARQL 결과가 0건이면 `(call, visitedAfter, ?visit)` 형태로 R-GCN+TransE가 visit 후보를 만들고, LLM이 시간/장소 맥락으로 최종 선택합니다.

### 2-hop LP

> `Photo -> VisitEvent -> Person`처럼 두 번의 관계 추론이 필요한 경우입니다. 1차로 사진과 연결된 방문을 예측하고, 2차로 그 방문에서 만난 사람을 예측합니다. 각 hop마다 LLM 검증을 거치고, 최종 URI를 `VALUES`로 고정해 SPARQL을 다시 실행합니다.

## Page 15. Phase 2 Entity/Schema Alignment

질문 트리거:

- "Phase 2에서 entity alignment는 정확히 뭘 하겠다는 건가요?"
- "Phone/Watch/TV 통합에서 가장 어려운 점은 무엇인가요?"

30초 답변:

> Phase 2의 핵심은 단순 동일 사용자 식별이 아니라 cross-device schema integration입니다. Phone, Watch, TV가 각각 다른 event schema와 attribute를 가지기 때문에, entity alignment와 함께 schema/attribute alignment, relation consistency 검증이 필요합니다.

90초 설명:

> 예를 들어 Phone의 `AppUsageEvent`, Watch의 `WorkoutEvent`, TV의 `MediaWatchEvent`는 모두 사용자 행동 event지만 attribute와 timestamp semantics가 다릅니다. 그래서 Samsung Account 같은 anchor로 user-level weak supervision을 만들 수는 있지만, 그것만으로 충분하지 않습니다. device별 class/property를 맞추고, 동일 event인지 후보를 만들고, entity뿐 아니라 relation consistency까지 검증해야 통합 KG가 깨지지 않습니다.  
> 이 부분은 현재 구현 설명이 아니라 입사 후 Phase 2 확장 전략으로 말하는 것이 맞습니다.

논문 연결 표현:

- ProLEA: entity profile을 만들고 LLM으로 candidate를 재평가하는 방향. 현재 seed entity/candidate verification의 확장으로 설명한다.
- Group, Embed and Reason: metadata 기반 schema/attribute alignment. Phone/Watch/TV schema integration의 핵심 근거로 쓴다.
- Beyond Entity Alignment: entity만 맞추지 말고 relation consistency까지 같이 보자는 근거로 쓴다.
- EasyEA: seed pair가 적을 때 시작할 수 있는 baseline 정도로만 언급한다.
- DAEA: 실제 서비스 데이터는 benchmark보다 훨씬 이질적이라는 경고로 짧게 쓴다.

주의할 표현:

- "Phase 2 alignment를 이미 구현했습니다"라고 하지 않는다.
- "현재는 single-device personal KG query/completion prototype이고, Phase 2에서 cross-device alignment로 확장하겠습니다"라고 말한다.

---

# 4. 예상 질문과 모범 답안

## A. 기술 질문 - RDF, OWL, SPARQL

### Q1. Ontology-based KG가 정확히 무슨 뜻인가요?

30초 답변:

> 단순히 node와 edge를 저장한 그래프가 아니라, class, property, domain/range, hierarchy 같은 의미 구조를 먼저 정의하고 그 제약 안에서 데이터를 표현하는 KG를 의미합니다. 제 프로젝트에서는 이 schema를 agent가 query path를 선택하고 SPARQL/Cypher를 생성하는 기준으로 사용했습니다.

90초 답변:

> Graph DB만 쓰면 구조는 그래프지만 의미 제약이 약할 수 있습니다. Ontology-based KG는 `CallEvent`, `VisitEvent`, `Person`, `Place` 같은 class와 `callee`, `place`, `visitedAt` 같은 property를 정의하고, 어떤 class와 class가 어떤 relation으로 연결될 수 있는지를 명시합니다. 이렇게 하면 LLM agent가 아무 property나 생성하는 것을 줄이고, schema-aware query generation이 가능해집니다.

### Q2. SPARQL과 SQL의 가장 큰 차이는 무엇인가요?

30초 답변:

> SQL은 테이블과 컬럼 중심으로 row를 조회하는 언어이고, SPARQL은 subject-predicate-object triple pattern을 매칭해 그래프 경로를 찾는 언어입니다. 관계 경로가 중요한 KG에서는 SPARQL이 자연스럽지만, 대량 transaction 처리와 운영 성능은 SQL이 강합니다.

### Q3. 왜 RDF를 쓰나요? Neo4j로도 되지 않나요?

30초 답변:

> Neo4j/Cypher는 LLM query generation과 visualization에는 장점이 큽니다. 다만 RDF는 W3C 표준, OWL/RDFS reasoning, triple store, ontology vocabulary와 잘 맞기 때문에 Android event log를 semantic KG로 만들고 reasoning engine과 연결하기 좋습니다. 삼성의 RDFox 맥락을 고려하면 RDF 기반 접근이 더 자연스럽다고 봅니다.

### Q4. OWL property chain으로 2-hop rule을 풀겠다는 건 무슨 뜻인가요?

30초 답변:

> 현재 프로토타입은 `relatedEvent + metDuring` 같은 2-hop chain을 일부 rule로 감지합니다. 향후에는 이런 관계 경로를 ontology나 RDFox rule로 정의해, agent 코드의 keyword rule이 아니라 schema/reasoning layer에서 일반화하려는 계획입니다.

90초 답변:

> 예를 들어 `Photo relatedEvent VisitEvent`이고 `VisitEvent metDuring Person`이면, 질문에 따라 `Photo indirectlyMet Person` 같은 추론 관계를 만들 수 있습니다. 지금은 이 chain을 코드의 `MULTIHOP_CHAINS`로 갖고 있지만, production 구조에서는 ontology-level property chain이나 RDFox rule로 올리는 것이 유지보수와 확장성 측면에서 더 좋습니다.

### Q5. R2RML과 RML을 어디에 쓰나요?

30초 답변:

> R2RML은 RDB table을 RDF triple로 바꾸는 표준 매핑 언어이고, RML은 JSON/CSV/XML까지 확장합니다. Android log나 app data가 여러 형태로 존재할 수 있으므로, source schema를 event-centric RDF ontology로 매핑하는 선언적 layer로 사용할 수 있습니다.

## B. GNN / Link Prediction 질문

### Q6. 이 프로젝트에서 link prediction은 무엇을 예측하나요?

30초 답변:

> 명시적으로 저장되지 않은 relation edge를 예측합니다. 예를 들어 사진과 방문 사이의 `relatedEvent`, 방문과 사람 사이의 `metDuring`, 통화와 방문 사이의 `visitedAfter` 같은 edge가 없을 때 `(head, relation, ?tail)` 후보를 ranking합니다.

### Q7. R-GCN은 일반 GCN과 뭐가 다른가요?

30초 답변:

> 일반 GCN은 이웃 정보를 relation 구분 없이 집계하는 반면, R-GCN은 edge type별로 다른 transformation을 사용합니다. RDF KG에서는 predicate가 다양하기 때문에 `callee`, `place`, `relatedEvent`를 같은 edge로 보면 안 됩니다. 그래서 R-GCN이 더 적합합니다.

### Q8. TransE는 왜 붙였나요?

30초 답변:

> R-GCN은 node embedding을 만들고, TransE는 triple scoring을 담당합니다. `h + r`이 `t`에 가까우면 해당 `(head, relation, tail)` triple이 그럴듯하다고 보고, 이 점수로 tail 후보를 top-K ranking합니다.

### Q9. 후보 tail은 누가 만들어주나요?

30초 답변:

> 모델이 전체 node embedding을 대상으로 `h + r`과 가까운 node를 찾습니다. 그 후 실사용에서는 relation별 expected type이나 URI pattern으로 후보를 줄입니다. 예를 들어 `relatedEvent`의 tail은 visit 후보로, `usedDuring`의 tail은 calendar 후보로 필터링합니다.

### Q10. confidence는 확률인가요?

30초 답변:

> 현재는 엄밀한 calibrated probability는 아닙니다. TransE raw score를 후보군 내에서 softmax-normalize한 ranking confidence입니다. 그래서 답변에는 "가능성이 높다"는 표현을 쓰고, 중요한 결론은 LLM verification과 SPARQL 근거를 함께 제시합니다.

### Q11. 시간 정보는 R-GCN에 직접 들어가나요?

30초 답변:

> 현재 구현에서는 URI-URI triple 중심으로 R-GCN graph를 만들기 때문에 literal timestamp는 embedding에 직접 들어가지 않습니다. 시간 정보는 rule fallback, candidate evidence, LLM verifier에서 강하게 사용합니다. 향후에는 temporal KG embedding이나 time-aware feature를 추가할 수 있습니다.

## C. 프로토타입 현재 구현/한계 질문

### Q12. 현재 구현된 것과 앞으로 할 것을 구분해보세요.

30초 답변:

> 현재 구현된 것은 RDF 기반 personal KG prototype, Text2SPARQL flow, SPARQL 결과 0건 시 R-GCN+TransE 후보 생성, LLM verifier, request-scoped `VALUES` 재생성입니다. 아직 목표 구조인 full schema retrieval, ontology-level property chain, cross-device alignment는 고도화 계획입니다.

### Q13. rule-based라고 한 부분은 무엇인가요?

30초 답변:

> 현재 2-hop chain 감지는 일부 keyword/rule 기반입니다. 예를 들어 사진과 "누구 만났어"가 같이 나오면 `relatedEvent + metDuring` chain으로 보는 식입니다. 또한 embedding 예측이 없을 때 시간 차이를 이용한 rule fallback이 있습니다. 이 부분을 향후 ontology rule과 RDFox reasoning으로 올리는 것이 계획입니다.

### Q14. 예측한 triple을 KG에 저장하지 않는 이유는 무엇인가요?

30초 답변:

> 개인 KG에서는 잘못 예측된 edge가 영구 저장되면 이후 답변을 계속 오염시킬 수 있습니다. 그래서 현재는 request scope에서만 예측 triple을 사용하고, 선택된 URI를 `VALUES`로 고정해 SPARQL을 재생성합니다. 검증된 관계만 별도 승인 후 저장하는 구조가 더 안전합니다.

### Q15. LLM verifier가 있으면 hallucination 위험이 있지 않나요?

30초 답변:

> 그래서 LLM에게 자유롭게 답을 만들게 하지 않고, R-GCN+TransE가 만든 top-K 후보와 Fuseki에서 가져온 evidence 안에서 선택하게 합니다. 최종 답변도 예측 confidence와 근거를 함께 표시합니다.

## D. 삼성 적합성 질문

### Q16. 삼성리서치에서 이 경험이 왜 중요한가요?

30초 답변:

> 삼성의 개인화 AI는 기기 안의 통화, 사진, 앱, 위치, 캘린더 데이터를 사용자의 맥락으로 연결해야 합니다. 저는 제조 도메인에서 복잡한 legacy data를 ontology와 agent로 연결해본 경험이 있고, 이를 personal KG와 on-device agent로 확장하는 프로토타입까지 만들어봤기 때문에 바로 기여할 수 있다고 생각합니다.

### Q17. RDFox나 Personal Data Engine과 어떤 접점이 있나요?

30초 답변:

> RDFox는 RDF 기반 reasoning engine이고, Personal Data Engine은 on-device에서 개인 데이터를 연결해 개인화 기능을 제공하는 방향으로 이해하고 있습니다. 제 제안은 Android event log를 event-centric RDF KG로 만들고, sLLM/Text2SPARQL agent와 sparse completion을 결합하는 구조라 이 맥락과 잘 맞습니다.

### Q18. Cross-device alignment에서 가장 중요한 문제는 무엇인가요?

30초 답변:

> 동일 사용자 식별도 중요하지만, 더 핵심은 schema/attribute alignment입니다. Phone, Watch, TV가 각자 다른 event schema를 가지기 때문에 class/property를 맞추고 relation consistency를 검증해야 통합 KG가 안정적으로 동작합니다.

### Q19. On-device에서 무겁지 않나요?

30초 답변:

> production에서는 모든 모델을 무겁게 돌리는 구조가 아니라 tiering이 필요합니다. 기본 retrieval은 SQLite FTS5와 cached schema로 가볍게 처리하고, 자주 쓰는 시나리오는 rule/reasoning으로 처리하며, GNN/LLM은 sparse하거나 모호한 질의에서만 선택적으로 호출하는 방식이 적합합니다.

## E. 경력/리더십 질문

### Q20. 가장 힘들었던 프로젝트 문제는 무엇이었고 어떻게 해결했나요?

30초 답변:

> 제조 agent 프로젝트에서 가장 힘들었던 점은 데이터가 많다는 것보다 데이터의 의미 관계가 파편화되어 있었다는 점입니다. LLM에 많은 schema와 few-shot을 넣어도 복잡한 관계 질의에서 흔들렸습니다. 그래서 ontology schema와 multi-agent path planning 구조로 바꾸고, 중간에 human-in-the-loop을 넣어 신뢰성을 높였습니다.

90초 답변:

> 초기에는 SQL generation 중심으로 접근했지만, 설비, 공정, 품질, 이력 데이터가 얽힌 질문에서는 어떤 테이블을 어떤 순서로 join해야 하는지 LLM이 안정적으로 판단하지 못했습니다. 저는 문제를 "프롬프트 개선"이 아니라 "AI가 읽을 수 있는 데이터 구조 부족"으로 봤습니다. 그래서 entity/relation schema를 만들고, agent가 schema를 기반으로 path를 선택하도록 구조를 바꿨습니다. 이 과정에서 고객과 현업을 설득해 ontology modeling과 HITL 프로세스를 넣었고, 결과적으로 더 안정적인 탐색 구조를 만들었습니다.

### Q21. 기술 리더로서 갈등을 해결한 경험이 있나요?

30초 답변:

> 저장소 선택에서 graph DB를 계속 쓸지 RDB로 전환할지 의견이 갈린 적이 있습니다. 저는 기술 선호가 아니라 데이터 규모, 운영 비용, LLM query generation 정확도, 고객 환경을 기준으로 비교했고, graph DB를 전체 저장소로 쓰기보다 RDB를 core로 두고 ontology graph를 reasoning layer로 쓰는 절충안을 제안했습니다.

### Q22. 60억 수주에 어떻게 기여했나요?

30초 답변:

> 단순 제안서 작성이 아니라 고객의 문제를 AI 과제로 재정의하고, 기술 구조와 단계별 구현 가능성을 제시한 역할을 했습니다. 특히 KG/Agent 구조를 통해 기존 검색이나 SQL 자동화로 풀기 어려운 복합 관계 탐색 문제를 해결할 수 있다는 점을 설득했습니다.

### Q23. 12,000명 서비스 운영에서 배운 점은 무엇인가요?

30초 답변:

> 모델 성능만큼 중요한 것은 운영 안정성, 실패 대응, 사용자 피드백 루프라는 점을 배웠습니다. 실제 서비스에서는 한 번의 멋진 demo보다 지속적으로 정확도를 유지하고, 실패 케이스를 수집해 개선하는 체계가 더 중요했습니다.

### Q24. 왜 삼성리서치인가요?

30초 답변:

> 삼성은 스마트폰, 워치, TV처럼 개인 맥락 데이터가 발생하는 접점이 매우 넓습니다. 저는 KG와 agent를 실제 데이터 문제에 적용해본 경험이 있고, 이 경험을 온디바이스 개인화 AI로 확장하고 싶습니다. 연구와 실제 서비스 임팩트가 만나는 지점이 삼성리서치라고 생각합니다.

### Q25. 입사하면 가장 먼저 무엇을 하겠습니까?

30초 답변:

> 먼저 현재 데이터 소스와 target scenario를 파악하고, event-centric ontology의 최소 schema를 정의하겠습니다. 그다음 2-3개 핵심 회상 시나리오를 기준으로 RDF ingestion, entity retrieval, Text2SPARQL, sparse completion까지 end-to-end prototype을 빠르게 검증하겠습니다.

---

# 마지막 암기 카드

## 30초 자기소개

저는 온톨로지 기반 Knowledge Graph와 Multi-agent 시스템을 실제 제조 도메인에서 설계하고 운영해온 AI 엔지니어 김문수입니다. SPARQL, Cypher, SQL을 모두 실전에서 써봤고, 12,000명 대상 agent 서비스를 운영했으며, 최근에는 Android RDF KG에 R-GCN + TransE link prediction을 적용해 개인 KG sparse 문제를 보완하는 프로토타입을 만들었습니다. 삼성리서치에서는 이 경험을 바탕으로 온디바이스 personal KG와 개인화 agent 고도화에 기여하고 싶습니다.

## 1분 기술 요약

제 핵심 경험은 복잡한 데이터를 AI가 이해할 수 있는 의미 구조로 바꾸는 것입니다. 제조 프로젝트에서는 legacy data를 ontology schema의 entity/relation으로 구조화하고, multi-agent가 KG 위에서 query path를 선택하게 했습니다. 또한 SPARQL, Cypher, SQL을 모두 적용해보며 저장소와 query 언어의 trade-off를 경험했습니다. 최근에는 개인 KG가 sparse하다는 문제를 해결하기 위해 RDF predicate를 edge type으로 보는 R-GCN embedding과 TransE scoring을 결합했고, LLM verifier가 시간/장소 문맥으로 후보를 검증하는 구조를 구현했습니다.

## 1분 삼성 기여 요약

삼성의 개인화 AI는 통화, 캘린더, 사진, 위치, 앱 사용 기록 같은 event data를 사용자의 맥락으로 연결해야 합니다. 저는 이 문제를 event-centric RDF personal KG로 풀 수 있다고 봅니다. CallEvent, VisitEvent, AppUsageEvent 같은 event를 중심으로 user, person, place, app, time을 연결하고, Text2SPARQL agent가 필요한 경로를 탐색하게 만들 수 있습니다. KG에 없는 관계는 R-GCN+TransE로 후보를 만들고 LLM이 검증하는 방식으로 sparse 문제를 보완할 수 있습니다. 입사 후에는 schema 설계, triple ingestion, agent flow, sparse completion을 빠르게 end-to-end로 검증해 기여하고 싶습니다.

## 말하면 안 좋은 표현

- "schema retrieval은 이미 personal KG에 완성되어 있습니다."
- "confidence는 실제 정답 확률입니다."
- "R-GCN이 시간 정보를 전부 이해합니다."
- "LLM이 알아서 최종 답을 생성합니다."
- "GraphSAGE는 성능이 안 좋은 모델입니다."
- "Entity alignment는 이미 구현했습니다."

## 좋은 대체 표현

- "현재 프로토타입에서는 일부 구현했고, 회사 프로젝트에서 유사 구조를 구현한 경험이 있어 이식할 계획입니다."
- "confidence는 후보군 내 ranking confidence로 보고 있습니다."
- "시간 정보는 현재 verifier와 rule evidence에서 강하게 사용하고, 향후 temporal KG로 확장할 수 있습니다."
- "LLM은 자유 생성이 아니라 top-K 후보 중 검증자 역할로 제한했습니다."
- "GraphSAGE는 inductive 대규모 그래프에 강하지만, 제 문제에서는 전체 topology 보존이 더 중요했습니다."
- "Entity/schema alignment는 Phase 2 확장 전략입니다."
