import requests
import json

URL = "http://localhost:8000/wellbeing-chat"

def test_chat():
    payload = {"question": "How is my glucose level?"}
    try:
        r = requests.post(URL, json=payload, timeout=30)
        r.raise_for_status()
        ans = r.json().get("answer", "")
        print("=== Chatbot Response ===")
        print(ans)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()
