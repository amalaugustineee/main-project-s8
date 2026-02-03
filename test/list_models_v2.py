from dotenv import load_dotenv
import os
from google import genai

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")

if not key:
    print("❌ No key")
    exit(1)

client = genai.Client(api_key=key)

print(f"Listing models for key ...{key[-5:]}:")
try:
    # Try the correct method for the new SDK
    for m in client.models.list():
        print(f"- {m.name}")
except Exception as e:
    print(f"❌ Failed to list: {e}")
    print("Dir of client.models:", dir(client.models))
