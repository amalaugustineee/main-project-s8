import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")

if not key:
    print("No Key")
    exit(1)

models = ["gemini-1.5-flash", "gemini-pro"]

for m in models:
    print(f"\nTesting {m}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": "Ping"}]}]}

    req = urllib.request.Request(url, json.dumps(data).encode(), headers)
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"✅ Status: {resp.status}")
            print(resp.read().decode())
            print(f"!!! WORKING MODEL: {m} !!!")
            exit(0)
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} {e.reason}")
        print(e.read().decode())
    except Exception as e:
        print(f"❌ Error: {e}")
