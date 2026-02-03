from dotenv import load_dotenv
import os
from google import genai

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")

if not key:
    print("❌ No key found")
    exit(1)

client = genai.Client(api_key=key)

print(f"Listing models for key ...{key[-5:]}:")
try:
    # Listing models (v1beta check)
    for m in client.models.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"❌ Failed to list models: {e}")
