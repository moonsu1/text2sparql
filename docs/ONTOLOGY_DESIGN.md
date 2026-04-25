# Ontology Design 설명

## Event-Centric Ontology란?

전통적인 관계형 DB나 property graph에서는 주로 **direct edge** 방식으로 데이터를 표현해요:

```
(User) -[CALLED]-> (Person)
```

하지만 이 방식은 다음과 같은 질문에 답하기 어려워요:
- "언제 전화했지?"
- "통화 후에 어디 갔지?"
- "이 정보의 근거는 뭐지?"

**Event-Centric Ontology**는 Event를 1급 엔티티로 올려서 이런 문제를 해결해요:

```
(User) -[caller]-> (CallEvent) -[callee]-> (Person)
                       |
                       +-- startedAt: "2026-04-19T11:05:00"
                       +-- durationSeconds: 180
                       +-- prov:wasDerivedFrom: RawLog#245
```

## 왜 Event-Centric인가?

### 1. 시간적 관계 표현이 자연스러워요

**질문**: "어제 김철수와 통화하고 나서 들른 카페 어디였지?"

**Direct Edge 방식** (어려움):
```sparql
# User와 Place를 직접 연결하면 "통화 후"라는 시간 순서를 표현하기 어려움
SELECT ?cafe WHERE {
  ?user :called :KimChulSu .
  ?user :visited ?cafe .
  # 어떻게 순서를 보장하지?
}
```

**Event-Centric 방식** (쉬움):
```sparql
SELECT ?cafe WHERE {
  ?callEvent a log:CallEvent ;
             log:caller :user_main ;
             log:callee :KimChulSu ;
             log:startedAt ?callTime .
  
  ?visitEvent a log:VisitEvent ;
              log:visitor :user_main ;
              log:place ?cafe ;
              log:visitedAt ?visitTime .
  
  ?cafe log:placeType "cafe" .
  
  FILTER(?visitTime > ?callTime)
  FILTER(?visitTime < ?callTime + "PT2H"^^xsd:duration)  # 2시간 이내
}
ORDER BY ?visitTime
LIMIT 1
```

### 2. Provenance(근거) 추적이 가능해요

모든 Event는 원본 로그와 연결돼요:

```turtle
data:call_001 a log:CallEvent ;
    log:caller data:user_main ;
    log:callee data:KimChulSu ;
    log:startedAt "2026-04-19T11:05:00+09:00"^^xsd:dateTime ;
    prov:wasDerivedFrom data:rawlog_call_001 .

data:rawlog_call_001 a log:RawLog ;
    log:sourceFile "call_logs.json" ;
    log:rowIndex 0 .
```

이렇게 하면 "이 정보는 어디서 왔는지" 항상 추적 가능해요.

### 3. 복잡한 컨텍스트를 담을 수 있어요

하나의 Event에 여러 정보를 풍부하게 붙일 수 있어요:

```turtle
data:meeting_001 a log:CalendarEvent ;
    log:title "제품 기획 회의" ;
    log:startTime "2026-04-19T10:00:00+09:00"^^xsd:dateTime ;
    log:endTime "2026-04-19T11:00:00+09:00"^^xsd:dateTime ;
    log:eventPlace data:meeting_room_b ;
    log:participant data:KimChulSu ;
    log:participant data:LeeYounghee ;
    log:category "work" ;
    prov:wasDerivedFrom data:rawlog_calendar_001 .

# 같은 시간에 촬영된 사진
data:photo_001 a log:Content ;
    log:capturedAt "2026-04-19T10:30:00+09:00"^^xsd:dateTime ;
    log:capturedPlace data:meeting_room_b ;
    log:relatedEvent data:meeting_001 .
```

## 클래스 계층 구조

```
owl:Thing
├── log:User (스마트폰 주인)
├── log:Person (연락처의 사람들)
├── log:Place (장소)
│   ├── log:Home
│   ├── log:Office
│   ├── log:Cafe
│   ├── log:Restaurant
│   └── log:Station
├── log:App (애플리케이션)
├── log:Content (사진/영상)
├── log:Event (모든 이벤트의 추상 클래스)
│   ├── log:CallEvent (통화)
│   ├── log:AppUsageEvent (앱 사용)
│   ├── log:CalendarEvent (캘린더 일정)
│   └── log:VisitEvent (장소 방문)
└── log:RawLog (원본 로그 레코드)
    └── prov:Entity
```

## 주요 Property 패턴

### Pattern 1: Event → Agent

이벤트의 주체를 나타내요:

```turtle
?callEvent log:caller ?user .
?visitEvent log:visitor ?user .
?appEvent log:usedApp ?app .
```

### Pattern 2: Event → Patient

이벤트의 대상을 나타내요:

```turtle
?callEvent log:callee ?person .
?visitEvent log:place ?place .
?content log:capturedPlace ?place .
```

### Pattern 3: Event → Time

이벤트의 시간 정보:

```turtle
?callEvent log:startedAt ?time .
?visitEvent log:visitedAt ?time .
?calendarEvent log:startTime ?start ;
               log:endTime ?end .
```

### Pattern 4: Event → Provenance

이벤트의 근거:

```turtle
?event prov:wasDerivedFrom ?rawLog .
?rawLog log:sourceFile "call_logs.json" ;
        log:rowIndex 5 .
```

## RDF Triple 예시

### CallEvent 예시

```turtle
data:call_001 a log:CallEvent ;
    log:caller data:user_main ;
    log:callee data:KimChulSu ;
    log:startedAt "2026-04-19T11:05:00+09:00"^^xsd:dateTime ;
    log:durationSeconds 180 ;
    log:callType "outgoing" ;
    rdfs:label "김철수님과의 통화" ;
    prov:wasDerivedFrom data:rawlog_call_001 .

data:user_main a log:User ;
    rdfs:label "나" .

data:KimChulSu a log:Person ;
    rdfs:label "김철수" .

data:rawlog_call_001 a log:RawLog ;
    log:sourceFile "call_logs.json" ;
    log:rowIndex 0 .
```

### VisitEvent 예시

```turtle
data:visit_001 a log:VisitEvent ;
    log:visitor data:user_main ;
    log:place data:starbucks_yeoksam ;
    log:visitedAt "2026-04-19T11:30:00+09:00"^^xsd:dateTime ;
    log:wifiSSID "Starbucks_WiFi_7429" ;
    log:stayDuration 1800 ;
    rdfs:label "스타벅스 역삼점 방문" ;
    prov:wasDerivedFrom data:rawlog_visit_001 .

data:starbucks_yeoksam a log:Cafe ;
    rdfs:label "스타벅스 역삼점" ;
    log:placeType "cafe" ;
    log:latitude 37.4979 ;
    log:longitude 127.0276 .
```

### Content with Event Link 예시

```turtle
data:photo_001 a log:Content ;
    log:contentType "photo" ;
    log:createdBy data:user_main ;
    log:capturedAt "2026-04-19T11:35:00+09:00"^^xsd:dateTime ;
    log:capturedPlace data:starbucks_yeoksam ;
    log:relatedEvent data:visit_001 ;
    log:filePath "/storage/photos/2026-04-19_11-35-00.jpg" ;
    rdfs:label "커피 사진" ;
    prov:wasDerivedFrom data:rawlog_photo_001 .
```

## SPARQL 쿼리 예시

### 1. 최근 통화한 사람 찾기

```sparql
PREFIX log: <http://example.org/smartphone-log#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?person ?time WHERE {
  ?call a log:CallEvent ;
        log:caller ?user ;
        log:callee ?person ;
        log:startedAt ?time .
  
  ?person rdfs:label ?personName .
  
  FILTER(?time > "2026-04-18T00:00:00+09:00"^^xsd:dateTime)
}
ORDER BY DESC(?time)
LIMIT 5
```

### 2. 통화 후 방문한 카페 찾기

```sparql
PREFIX log: <http://example.org/smartphone-log#>

SELECT ?callPerson ?cafe ?visitTime WHERE {
  ?call a log:CallEvent ;
        log:callee ?callPerson ;
        log:startedAt ?callTime .
  
  ?callPerson rdfs:label "김철수" .
  
  ?visit a log:VisitEvent ;
         log:place ?cafe ;
         log:visitedAt ?visitTime .
  
  ?cafe log:placeType "cafe" ;
        rdfs:label ?cafeName .
  
  FILTER(?visitTime > ?callTime)
  FILTER(?visitTime < ?callTime + "PT3H"^^xsd:duration)
}
ORDER BY ?visitTime
LIMIT 1
```

### 3. 장소에서 찍은 사진 찾기

```sparql
PREFIX log: <http://example.org/smartphone-log#>

SELECT ?photo ?time ?place WHERE {
  ?visit a log:VisitEvent ;
         log:place ?place ;
         log:visitedAt ?visitTime .
  
  ?place rdfs:label ?placeName .
  
  ?photo a log:Content ;
         log:contentType "photo" ;
         log:capturedAt ?time ;
         log:capturedPlace ?place .
  
  FILTER(abs(?time - ?visitTime) < 600)  # 10분 이내
}
```

## 왜 Vector DB가 아니라 Triple Store인가?

### Vector DB의 장점
- 의미 기반 유사도 검색
- 빠른 nearest neighbor search
- 임베딩 기반 검색

### Vector DB의 한계
- **시간적 순서 관계** 쿼리가 어려움
  - "A 이벤트 **후에** B 이벤트"를 표현하기 어려움
- **그래프 관계 탐색**이 약함
  - "통화한 사람과 만난 장소" 같은 multi-hop 추론이 어려움
- **정확한 필터링**이 약함
  - "정확히 어제 오후 2시-3시 사이"같은 정밀한 조건
- **Provenance 추적**이 어려움
  - 결과의 근거를 명확히 추적하기 어려움

### Triple Store (Fuseki)의 장점
- ✅ **SPARQL**로 복잡한 그래프 쿼리 가능
- ✅ **시간적 관계** 표현 및 쿼리 자연스러움
- ✅ **Provenance** 추적 표준 (PROV-O)
- ✅ **정확한 논리적 추론** 가능
- ✅ **표준 기술** (RDF, SPARQL, OWL)

### Hybrid 접근 (2차 목표)

나중에는 둘 다 사용할 수 있어요:

```
사용자 질의
    ↓
Entity Retrieval (Vector DB 또는 FTS)
    ↓
SPARQL Generation
    ↓
Triple Store (Fuseki) 쿼리
    ↓
결과 설명 개선 (Vector DB로 유사 사례 검색)
```

하지만 **메인 저장소는 Triple Store**이고, Vector DB는 보조 도구로만 사용!

## 시간 모델링 전략

### 1차 구현: xsd:dateTime

가장 간단한 방식:

```turtle
?event log:occurredAt "2026-04-19T11:05:00+09:00"^^xsd:dateTime .
```

SPARQL에서 직접 비교 가능:

```sparql
FILTER(?time > "2026-04-19T00:00:00+09:00"^^xsd:dateTime)
```

### 2차 확장: OWL-Time (선택적)

더 복잡한 시간 관계가 필요하면:

```turtle
?event time:hasTime [
    a time:Instant ;
    time:inXSDDateTime "2026-04-19T11:05:00+09:00"^^xsd:dateTime
] .

?meeting time:hasTime [
    a time:Interval ;
    time:hasBeginning [ time:inXSDDateTime "2026-04-19T10:00:00+09:00"^^xsd:dateTime ] ;
    time:hasEnd [ time:inXSDDateTime "2026-04-19T11:00:00+09:00"^^xsd:dateTime ]
] .
```

이렇게 하면 `time:before`, `time:after` 같은 Allen의 Interval Algebra를 사용할 수 있어요.

하지만 1차에서는 **xsd:dateTime만으로도 충분해요!**

## 다음 단계

이제 이 온톨로지를 바탕으로:
1. ✅ Synthetic data 생성
2. ✅ Python으로 RDF triple 생성
3. ✅ Fuseki에 적재
4. ✅ SPARQL 쿼리 작성
5. ✅ Text2SPARQL 구현

으로 진행할 거예요!
