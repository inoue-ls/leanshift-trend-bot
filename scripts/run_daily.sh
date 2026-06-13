#!/usr/bin/env bash
# 毎朝 7 時に cron から呼び出す日次実行スクリプト
# ログは logs/YYYY-MM-DD.log に追記される
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/$(date +%Y-%m-%d).log"

mkdir -p "$PROJECT_ROOT/logs"

{
  echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] run_daily.sh 開始 ==="

  cd "$PROJECT_ROOT"

  # .env が存在する場合のみ読み込む（GEMINI_API_KEY 等をエクスポート）
  if [ -f ".env" ]; then
    set -a
    # shellcheck source=/dev/null
    source .env
    set +a
  fi

  python3 main.py

  echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 完了 ==="
} >> "$LOG_FILE" 2>&1
