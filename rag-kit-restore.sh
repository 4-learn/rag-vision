#!/bin/bash
# Ch4.2 Workshop 結束後: 切回 Sheet B v3 (老師完整版) + 重啟 BOT
set -euo pipefail

cd "$(dirname "$0")"
V3_ID="1Kl4cm_3kFgPpNg4FPXKu-PWtNO0HtVVCZqcYIY_aF8M"

sed -i "s|^LANDMARKS_SHEET_CSV_URL=.*|LANDMARKS_SHEET_CSV_URL=\"https://docs.google.com/spreadsheets/d/${V3_ID}/export?format=csv\"|" .env

docker compose up -d line-bot >/dev/null
sleep 5
curl -fsS http://localhost:8001/healthz && echo " — BOT 切回 v3 (老師完整版)"
