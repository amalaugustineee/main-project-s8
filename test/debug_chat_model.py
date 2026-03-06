from google import genai
import os
from dotenv import load_dotenv

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=key)

model = "gemini-2.0-flash-lite"

print(f"Testing Chat Model: {model}")
try:
    response = client.models.generate_content(
        model=model,
        contents="Hello, this is a test chat message."
    )
    print(f"✅ Works! Response: {response.text.strip()}")
except Exception as e:
    print(f"❌ Failed: {e}")
