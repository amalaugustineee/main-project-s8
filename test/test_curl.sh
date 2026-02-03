#!/bin/bash
# Load .env variables
export $(grep -v '^#' ../.env | xargs)

echo "Testing Gemini 1.5 Flash via REST API..."
curl -s -X POST \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"Ping"}]}]}' \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_API_KEY}"
