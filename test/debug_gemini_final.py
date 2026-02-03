from google import genai
import os
from dotenv import load_dotenv

load_dotenv("../.env")
key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=key)

print("Searching for a working model...")

try:
    # Iterate all models available to this key
    for m in client.models.list():
        # Check support
        methods = getattr(m, 'supported_generation_methods', [])
        if 'generateContent' not in methods:
            continue

        raw_name = m.name # e.g. "models/gemini-1.5-flash"
        short_name = raw_name.replace("models/", "")

        candidates = [short_name, raw_name]
        
        for cand in candidates:
            print(f"Testing '{cand}'...", end=" ")
            try:
                client.models.generate_content(model=cand, contents="Ping")
                print("✅ WORKS!")
                print(f"\n!!! SUCCESS: The working model ID is: '{cand}' !!!\n")
                exit(0) # Stop immediately
            except Exception as e:
                if "429" in str(e):
                    print("⚠️ 429 Rate Limit (Retrying might work)")
                elif "404" in str(e):
                    print("❌ 404 Not Found")
                else:
                    print(f"❌ Error: {e}")

    print("\n❌ Failed to find ANY working model.")

except Exception as e:
    print(f"Critical Error: {e}")
