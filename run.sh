#!/usr/bin/env bash
# 프로젝트 .venv 를 준비하고 그 안의 Python 으로 Streamlit 실행 (Git Bash / macOS / Linux)
# - .venv 가 없으면 생성
# - requirements.txt 가 바뀌었으면 자동으로 재설치
set -euo pipefail

cd "$(dirname "$0")"

if [ -x .venv/Scripts/python.exe ]; then
  PY=.venv/Scripts/python.exe        # Windows (Git Bash)
elif [ -x .venv/bin/python ]; then
  PY=.venv/bin/python                # macOS / Linux
else
  echo "[run] .venv 가 없어 새로 만듭니다..."
  if command -v python3 >/dev/null 2>&1; then python3 -m venv .venv; else python -m venv .venv; fi
  if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi
fi

STAMP=.venv/.requirements.sha256
NEW_HASH=$("$PY" -c "import hashlib;print(hashlib.sha256(open('requirements.txt','rb').read()).hexdigest().upper())")
OLD_HASH=$(cat "$STAMP" 2>/dev/null || true)
if [ "$NEW_HASH" != "$OLD_HASH" ]; then
  echo "[run] requirements.txt 변경 감지 -> 패키지 설치 중..."
  "$PY" -m pip install --disable-pip-version-check -q -r requirements.txt
  echo "$NEW_HASH" > "$STAMP"
fi

[ -f .env ] || echo "[run] 경고: .env 가 없습니다. .env.example 을 복사해서 값을 채워 주세요." >&2

exec "$PY" -m streamlit run app/main.py --server.port=8501 --server.address=localhost --server.headless=false
