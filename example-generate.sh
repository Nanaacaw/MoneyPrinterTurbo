#!/usr/bin/env bash
# Contoh generate video via API MoneyPrinterTurbo (LLM = 9router/hemat)
set -e
API=${API:-http://127.0.0.1:8080}
SUBJECT="Manfaat minum air putih"

# 1. Generate script via LLM
SCRIPT=$(curl -s -X POST $API/api/v1/scripts \
  -H 'Content-Type: application/json' \
  -d "{\"video_subject\":\"$SUBJECT\",\"video_language\":\"Indonesian\",\"paragraph_number\":1}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['video_script'])")
echo "=== SCRIPT ===\n$SCRIPT"

# 2. Submit video task
TASK_ID=$(curl -s -X POST $API/api/v1/videos \
  -H 'Content-Type: application/json' \
  -d "{
    \"video_subject\":\"$SUBJECT\",
    \"video_script\":\"$SCRIPT\",
    \"voice_name\":\"id-ID-GadisNeural-Female\",
    \"video_aspect\":\"9:16\",
    \"video_clip_duration\":3,
    \"subtitle_enabled\":true,
    \"video_count\":1
  }" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['task_id'])")
echo "task_id: $TASK_ID"

# 3. Poll sampai selesai (~2-3 menit)
while true; do
  sleep 15
  STATE=$(curl -s $API/api/v1/tasks/$TASK_ID | python3 -c "
import json,sys
d=json.load(sys.stdin)['data']
print(d['state'], d['progress'], d.get('error') or '')")
  echo "$STATE"
  echo "$STATE" | grep -qE '^1 100|^0 ' && break   # state 1=completed, 0=failed
done

echo "Hasil: $PWD/storage/tasks/$TASK_ID/final-1.mp4"
