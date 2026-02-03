from dotenv import load_dotenv
import os
from google import genai
import time

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")

print(f"Testing Key: ...{key[-5:] if key else 'None'}")
print("Checking model: gemini-2.0-flash")

if not key:
    print("❌ No key found in environment!")
    exit(1)

client = genai.Client(api_key=key)

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Ping"
    )
    print(f"✅ gemini-2.0-flash Success: {response.text.strip()}")
except Exception as e:
    print(f"❌ gemini-2.0-flash Failed: {e}")
    
    print("\nAttempting fallback to gemini-1.5-flash...")
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents="Ping"
        )
        print(f"✅ gemini-1.5-flash Success: {response.text.strip()}")
    except Exception as e2:
        print(f"❌ gemini-1.5-flash Failed: {e2}")
