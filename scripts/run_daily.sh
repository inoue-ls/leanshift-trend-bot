#!/usr/bin/env bash
# 毎朝 7 時に cron から呼び出す日次実行スクリプト
# PC 起動時（~/.bashrc 等）からも呼べる。冪等ガードにより当日分が生成済みなら即 exit。
# ログは logs/YYYY-MM-DD.log に追記される
set -euo pipefail

# .bashrc から & で起動すると、ターミナルを閉じたときに SIGHUP で python ごと止まる。
# 無視する設定は子プロセス（python3 main.py）にも引き継がれる。
trap '' HUP

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/$(date +%Y-%m-%d).log"

mkdir -p "$PROJECT_ROOT/logs"

# 二重起動ガード: cron と .bashrc が同時に起動しても、実行中なら後から来た方は何もしない
exec 9> "$PROJECT_ROOT/logs/.run_daily.lock"
if ! flock -n 9; then
  echo "[SKIP] 実行中のため起動しない: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
  exit 0
fi

# 冪等ガード: 当日分の outputs がすでに存在する場合はスキップ
TODAY=$(date +%Y-%m-%d)
OUTPUT="$PROJECT_ROOT/outputs/${TODAY}_trends.md"
if [ -f "$OUTPUT" ]; then
  echo "[SKIP] 本日分は生成済み: $OUTPUT" >> "$LOG_FILE"
  exit 0
fi

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

  status=0
  python3 main.py || status=$?

  if [ "$status" -eq 0 ]; then
    echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 完了 ==="
  else
    echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 失敗 (exit $status) ==="
  fi

  # 日次トリアージ（L1: 報告のみ）。結果の行をログに書いたあとに走らせ、失敗した日も走らせる。
  # トリアージ自体が失敗しても、日次実行の結果（exit code）は変えない
  python3 -m core.daily_triage || echo "[警告] 日次トリアージに失敗しました"

  exit "$status"
} >> "$LOG_FILE" 2>&1
