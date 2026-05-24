#!/bin/bash
# Ch4.2 Workshop: 切到「降級 Sheet」(雲林故事館 row 弱化) + 重啟 BOT
# 上完課記得跑 ./rag-kit-restore.sh 切回 v3
set -euo pipefail

cd "$(dirname "$0")"
DEGRADED_ID="1xqXswuy5bKUEgDH8BZxF0IqdBVrP5EEaKCLOaCylWDs"

# 改 .env
sed -i "s|^LANDMARKS_SHEET_CSV_URL=.*|LANDMARKS_SHEET_CSV_URL=\"https://docs.google.com/spreadsheets/d/${DEGRADED_ID}/export?format=csv\"|" .env

# 重啟容器讓 .env 重新載入 + cache 清空
docker compose up -d line-bot >/dev/null
sleep 5
curl -fsS http://localhost:8001/healthz && echo " — BOT 切到降級版"
echo
echo "📋 Sheet (學生可編輯加 ref photo): https://docs.google.com/spreadsheets/d/${DEGRADED_ID}/edit"
echo "💡 上完課跑 ./rag-kit-restore.sh 切回 v3"
