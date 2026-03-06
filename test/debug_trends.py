import requests
import json

URL = "http://localhost:8000/trends/Glucose%20(Fasting)"

def check_trends():
    try:
        r = requests.get(URL)
        r.raise_for_status()
        data = r.json()
        print(f"Status: {r.status_code}")
        print(f"Count: {len(data)}")
        print("Data:")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_trends()
