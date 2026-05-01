$queries = @(
    @{ rank="[싱글홉 1위]"; q="4월 17일 투썸플레이스에서 찍은 사진은 어떤 방문 기록이랑 연결돼?" },
    @{ rank="[싱글홉 2위]"; q="4월 21일 스타벅스 방문에서 누구 만났지?" },
    @{ rank="[싱글홉 3위]"; q="Jung Su-jin이랑 통화하고 나서 어디 들렀어?" },
    @{ rank="[멀티홉 1위]"; q="4월 17일 투썸플레이스에서 찍은 사진이랑 연결된 방문에서 누구 만났어?" },
    @{ rank="[멀티홉 2위]"; q="Jung Su-jin이랑 통화하고 나서 들른 스타벅스에서 누구 만났어?" },
    @{ rank="[멀티홉 3위]"; q="4월 21일 스타벅스에서 찍은 사진이랑 연결된 방문에서 누구 만났지?" }
)

$pass = 0; $fail = 0

foreach ($item in $queries) {
    Write-Host "`n$($item.rank) $($item.q)"
    $body = [System.Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @{model="gpt-4o";messages=@(@{role="user";content=$item.q})}))
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 120
        $content = $resp.choices[0].message.content
        $confLines = $content -split "`n" | Select-String "confidence"
        $confs = $confLines | ForEach-Object { if ($_ -match "(\d+\.\d+)") { [double]$matches[1] } }
        $topConf = ($confs | Measure-Object -Maximum).Maximum
        if ($topConf -ge 0.45) {
            Write-Host "  ✅ PASS  최고 신뢰도: $topConf"
            $pass++
        } else {
            Write-Host "  ⚠️  LOW   최고 신뢰도: $topConf"
            $fail++
        }
    } catch {
        Write-Host "  ❌ ERROR: $_"
        $fail++
    }
}

Write-Host "`n========== 결과: $pass/$($pass+$fail) PASS =========="
