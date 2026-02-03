from dotenv import load_dotenv
import os
from google import genai

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")

if not key:
    print("❌ No key")
    exit(1)

client = genai.Client(api_key=key)

candidates = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-pro"
]

print(f"Testing models for key ...{key[-5:]}")

for model in candidates:
    print(f"\nTrying {model}...", end=" ")
    try:
        response = client.models.generate_content(
            model=model, 
            contents="Hi"
        )
        print(f"✅ SUCCESS!")
        print(f"Working model found: {model}")
        break  # Stop at first success
    except Exception as e:
        print(f"❌ Failed: {e}")
