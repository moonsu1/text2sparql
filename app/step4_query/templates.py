"""
Query Templates
SPARQL 쿼리 템플릿 정의
"""

# Intent별 SPARQL 템플릿

RECENT_CALLS_TEMPLATE = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX data: <http://example.org/data/>

SELECT ?call ?person ?personName ?time
WHERE {{
    ?call a log:CallEvent ;
          log:callee ?person ;
          log:startedAt ?time .
    ?person rdfs:label ?personName .
    FILTER(?time > "{start_time}"^^xsd:dateTime)
}}
ORDER BY DESC(?time)
LIMIT {limit}
"""

CALL_AFTER_VISIT_CAFE_TEMPLATE = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX data: <http://example.org/data/>

SELECT ?call ?visit ?person ?personName ?cafe ?cafeName ?callTime ?visitTime
WHERE {{
    ?call a log:CallEvent ;
          log:callee ?person ;
          log:startedAt ?callTime .
    ?person rdfs:label ?personName .
    {person_filter}
    
    ?visit a log:VisitEvent ;
           log:place ?cafe ;
           log:visitedAt ?visitTime .
    ?cafe log:placeType "cafe" ;
          rdfs:label ?cafeName .
    
    FILTER(?visitTime > ?callTime)
    FILTER(?visitTime < ?callTime + "PT3H"^^xsd:duration)
    {time_filter}
}}
ORDER BY ?visitTime
LIMIT 1
"""

MOST_USED_APP_TEMPLATE = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?app ?appName (COUNT(?event) AS ?count)
WHERE {{
    ?event a log:AppUsageEvent ;
           log:usedApp ?app ;
           log:occurredAt ?time .
    ?app rdfs:label ?appName .
    {time_filter}
}}
GROUP BY ?app ?appName
ORDER BY DESC(?count)
LIMIT 1
"""

MEETING_LOCATION_TEMPLATE = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?meeting ?title ?location ?startTime
WHERE {{
    ?meeting a log:CalendarEvent ;
             log:title ?title ;
             log:startTime ?startTime .
    OPTIONAL {{ ?meeting rdfs:comment ?location }}
    {time_filter}
}}
ORDER BY DESC(?startTime)
LIMIT {limit}
"""

VISITED_PLACES_TEMPLATE = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?visit ?place ?placeName ?visitTime ?placeType
WHERE {{
    ?visit a log:VisitEvent ;
           log:place ?place ;
           log:visitedAt ?visitTime .
    ?place rdfs:label ?placeName ;
           log:placeType ?placeType .
    {time_filter}
    {place_type_filter}
}}
ORDER BY DESC(?visitTime)
LIMIT {limit}
"""

PHOTOS_AT_PLACE_TEMPLATE = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?photo ?place ?placeName ?capturedTime ?visitTime
WHERE {{
    ?visit a log:VisitEvent ;
           log:place ?place ;
           log:visitedAt ?visitTime .
    ?place rdfs:label ?placeName .
    
    ?photo a log:Content ;
           log:contentType "photo" ;
           log:capturedPlace ?place ;
           log:capturedAt ?capturedTime .
    
    FILTER(abs(xsd:integer(?capturedTime) - xsd:integer(?visitTime)) < 600)
    {time_filter}
}}
ORDER BY DESC(?capturedTime)
LIMIT {limit}
"""

# Intent와 템플릿 매핑
INTENT_TEMPLATES = {
    "recent_calls": RECENT_CALLS_TEMPLATE,
    "call_after_visit_cafe": CALL_AFTER_VISIT_CAFE_TEMPLATE,
    "most_used_app": MOST_USED_APP_TEMPLATE,
    "meeting_location": MEETING_LOCATION_TEMPLATE,
    "visited_places": VISITED_PLACES_TEMPLATE,
    "photos_at_place": PHOTOS_AT_PLACE_TEMPLATE,
}
