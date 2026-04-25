"""
Fuseki 데이터 직접 확인 스크립트
웹 UI 없이 PowerShell로 SPARQL 쿼리 실행
"""

# Triple 개수 확인
$countQuery = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
$body = @{
    query = $countQuery
}

Write-Host "=== Fuseki 데이터 확인 ===" -ForegroundColor Green
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "http://localhost:3030/smartphone_log/query" `
        -Method POST `
        -ContentType "application/x-www-form-urlencoded" `
        -Body $body `
        -UseBasicParsing
    
    $result = $response.Content | ConvertFrom-Json
    $count = $result.results.bindings[0].count.value
    Write-Host "✅ 총 Triple 개수: $count" -ForegroundColor Cyan
} catch {
    Write-Host "❌ 쿼리 실패: $_" -ForegroundColor Red
}

Write-Host ""

# Person 목록 확인
$personQuery = @"
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?person ?label WHERE {
    ?person a log:Person .
    ?person rdfs:label ?label .
}
LIMIT 5
"@

$body = @{
    query = $personQuery
}

try {
    $response = Invoke-WebRequest -Uri "http://localhost:3030/smartphone_log/query" `
        -Method POST `
        -ContentType "application/x-www-form-urlencoded" `
        -Body $body `
        -UseBasicParsing
    
    $result = $response.Content | ConvertFrom-Json
    
    Write-Host "✅ Person 목록:" -ForegroundColor Cyan
    foreach ($binding in $result.results.bindings) {
        $label = $binding.label.value
        Write-Host "   - $label"
    }
} catch {
    Write-Host "❌ 쿼리 실패: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 더 많은 쿼리를 실행하려면 ===" -ForegroundColor Yellow
Write-Host "http://localhost:3030/smartphone_log/query 엔드포인트에 POST로 SPARQL 보내면 돼요!"
