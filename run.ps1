$ErrorActionPreference = "Stop"

# 프로젝트 루트 기준으로 .venv 를 준비하고 그 안의 Python 으로 Streamlit 실행
# - .venv 가 없으면 생성
# - requirements.txt 가 바뀌었으면 자동으로 재설치
# - 전역 Python 으로는 절대 실행하지 않음

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir     = Join-Path $projectRoot ".venv"
$python      = Join-Path $venvDir "Scripts\python.exe"
$reqFile     = Join-Path $projectRoot "requirements.txt"
$stampFile   = Join-Path $venvDir ".requirements.sha256"
$app         = Join-Path $projectRoot "app\main.py"
$port        = 8501

Push-Location $projectRoot
try {
    if (-not (Test-Path $python)) {
        Write-Host "[run] .venv 가 없어 새로 만듭니다..."
        $basePython = (Get-Command py -ErrorAction SilentlyContinue)
        if ($basePython) { & py -3.11 -m venv $venvDir; if (-not $?) { & py -3 -m venv $venvDir } }
        else { & python -m venv $venvDir }
        if (-not (Test-Path $python)) { throw ".venv 생성 실패. Python 3.11 이상이 설치되어 있는지 확인하세요." }
    }

    $reqHash = (Get-FileHash $reqFile -Algorithm SHA256).Hash
    $oldHash = if (Test-Path $stampFile) { (Get-Content $stampFile -Raw).Trim() } else { "" }
    if ($reqHash -ne $oldHash) {
        Write-Host "[run] requirements.txt 변경 감지 -> 패키지 설치 중..."
        & $python -m pip install --disable-pip-version-check -q -r $reqFile
        if ($LASTEXITCODE -ne 0) { throw "패키지 설치 실패" }
        Set-Content -Path $stampFile -Value $reqHash -Encoding ascii
    }

    if (-not (Test-Path (Join-Path $projectRoot ".env"))) {
        Write-Warning ".env 가 없습니다. .env.example 을 복사해서 값을 채워 주세요."
    }

    # 기존 Streamlit 프로세스가 포트를 점유하고 있으면 종료합니다.
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $listeners) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "포트 $port 사용 중인 프로세스 종료: $($process.ProcessName) (PID $processId)"
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    Start-Sleep -Milliseconds 500
    & $python -m streamlit run $app --server.port=$port --server.address=localhost --server.headless=false
}
finally {
    Pop-Location
}
