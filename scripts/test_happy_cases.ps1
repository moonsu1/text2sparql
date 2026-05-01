$queries = @(
    # Chain 1: relatedEvent+metDuring (사진→방문→만난사람)
    @{ chain="relatedEvent+metDuring"; q="4월 17일 투썸플레이스에서 찍은 사진이랑 연결된 방문에서 누구 만났어?" },
    @{ chain="relatedEvent+metDuring"; q="스타벅스 사진 연결된 방문에서 누구 만났어?" },

    # Chain 2: visitedAfter+metDuring (통화→방문→만난사람)
    @{ chain="visitedAfter+metDuring"; q="Jung Su-jin이랑 통화하고 나서 들른 카페에서 누구 만났어?" },
    @{ chain="visitedAfter+metDuring"; q="4월 17일 Jung Su-jin 통화 후 들른 카페에서 누구 만났어?" },

    # Chain 3: relatedEvent+visitedAfter_rev (사진→방문←통화: 사진 전 통화)
    @{ chain="relatedEvent+visitedAfter_rev"; q="스타벅스 사진 찍히기 전에 어떤 통화가 있었지?" },
    @{ chain="relatedEvent+visitedAfter_rev"; q="4월 17일 투썸플레이스 사진 찍히기 전에 어떤 통화가 있었어?" },

    # Chain 4: visitedAfter+relatedEvent_rev (통화→방문←사진: 통화 후 방문에서 찍힌 사진)
    @{ chain="visitedAfter+relatedEvent_rev"; q="Jung Su-jin이랑 통화 후 들른 카페에서 찍은 사진 있어?" },
    @{ chain="visitedAfter+relatedEvent_rev"; q="4월 17일 Jung Su-jin 통화 후 간 카페에서 찍은 사진은?" }
)

$results = @()

foreach ($item in $queries) {
    $q = $item.q
    $chain = $item.chain
    Write-Host "`n[$chain] $q"
    $bodyObj = @{ model="gpt-4o"; messages=@(@{ role="user"; content=$q }) }
    $body = [System.Text.Encoding]::UTF8.GetBytes(($bodyObj | ConvertTo-Json -Depth 5))
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 120
        $content = $resp.choices[0].message.content
        $confLines = $content -split "`n" | Select-String "confidence|결과.*행|results.*row"
        Write-Host "  → $($confLines -join ' | ')"
        $results += @{ chain=$chain; q=$q; lines=($confLines -join '|') }
    } catch {
        Write-Host "  → ERROR: $_"
        $results += @{ chain=$chain; q=$q; lines="ERROR" }
    }
}

Write-Host "`n`n========== 최종 결과 요약 =========="
foreach ($r in $results) {
    Write-Host "[$($r.chain)] $($r.q)"
    Write-Host "  $($r.lines)"
}
