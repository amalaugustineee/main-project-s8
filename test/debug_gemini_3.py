import os
import time
from dotenv import load_dotenv
from google import genai

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")

print(f"Key: ...{key[-5:] if key else 'None'}")
client = genai.Client(api_key=key)

models_to_test = [
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
    "learnlm-1.5-pro-experimental",
    "gemini-experimental"
]

print("\n--- Starting Extended Diagnostics ---")

for model in models_to_test:
    print(f"\nTesting model: {model}")
    try:
        response = client.models.generate_content(
            model=model,
            contents="Ping"
        )
        print(f"✅ Success! Response: {response.text.strip()}")
        print(f"RECOMMENDATION: Switch app to {model}")
        break
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
