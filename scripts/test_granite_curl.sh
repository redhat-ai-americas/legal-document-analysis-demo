#!/usr/bin/env bash
set -euo pipefail

# Load .env if present
if [ -f "$(dirname "$0")/../.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$(dirname "$0")/../.env"
  set +a
fi

API_KEY="${GRANITE_INSTRUCT_API_KEY:-${GRANITE_API_KEY:-}}"
BASE_URL="${GRANITE_INSTRUCT_URL:-${GRANITE_BASE_URL:-}}"
MODEL_NAME="${GRANITE_INSTRUCT_MODEL_NAME:-${GRANITE_MODEL:-}}"

if [ -z "$API_KEY" ] || [ -z "$BASE_URL" ] || [ -z "$MODEL_NAME" ]; then
  echo "Missing Granite env vars. Please set GRANITE_INSTRUCT_API_KEY, GRANITE_INSTRUCT_URL, GRANITE_INSTRUCT_MODEL_NAME (or legacy names)." >&2
  exit 1
fi

URL="${BASE_URL%/}/v1/chat/completions"

cat <<JSON > /tmp/granite_test_payload.json
{
  "model": "${MODEL_NAME}",
  "messages": [
    {"role": "user", "content": "Return only the word OK"}
  ],
  "max_tokens": 8,
  "temperature": 0.0,
  "logprobs": true
}
JSON

set -x
curl -sS -X POST "$URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  --data @/tmp/granite_test_payload.json | jq . | sed -e 's/\(api_key\): ".*"/\1: "***"/'
