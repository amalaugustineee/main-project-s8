import requests
import json
import os

BASE_URL = "http://localhost:8000"

def tprint(msg):
    print(f"\\n{'='*50}\\n[TEST] {msg}\\n{'-'*50}")

def test_endpoints():
    errors = []

    # 1. Reminders
    tprint("1. /reminders/upcoming")
    try:
        r = requests.get(f"{BASE_URL}/reminders/upcoming")
        print(r.status_code, r.text[:200])
    except Exception as e:
        errors.append(f"Reminders: {e}")

    # 2. Prescription History
    tprint("2. /prescription/history")
    try:
        r = requests.get(f"{BASE_URL}/prescription/history")
        print(r.status_code, r.text[:200])
    except Exception as e:
        errors.append(f"Rx History: {e}")

    # 3. Health Summary
    tprint("3. /health/summary")
    try:
        r = requests.post(f"{BASE_URL}/health/summary")
        print(r.status_code, r.text[:200])
    except Exception as e:
        errors.append(f"Health Summary: {e}")

    # 4. Wellbeing Chat
    tprint("4. /wellbeing-chat")
    try:
        r = requests.post(f"{BASE_URL}/wellbeing-chat", json={"question": "What is a balanced diet?"})
        print(r.status_code, r.text[:300])
    except Exception as e:
        errors.append(f"Chat: {e}")

    # 5. Health Risk (Upload Lab Report)
    tprint("5. /healthrisk (Upload Lab Report)")
    lab_path = "sample_labreport.png"
    if os.path.exists(lab_path):
        try:
            with open(lab_path, "rb") as f:
                r = requests.post(f"{BASE_URL}/healthrisk", files={"file": f})
                print(r.status_code)
                print(r.text[:500])
        except Exception as e:
            errors.append(f"HealthRisk: {e}")
    else:
        print(f"Missing {lab_path}")

    # 6. Prescription (Upload)
    tprint("6. /prescription (Upload)")
    rx_path = "sample_prescription.png"
    if os.path.exists(rx_path):
        try:
            with open(rx_path, "rb") as f:
                r = requests.post(f"{BASE_URL}/prescription", files={"file": f})
                print(r.status_code)
                print(r.text[:500])
        except Exception as e:
            errors.append(f"Prescription Upload: {e}")
    else:
        print(f"Missing {rx_path}")

    # 7. Generate Diet Plan
    tprint("7. /generate-diet-plan")
    data = {
        "region": "Asian",
        "cuisine": "Indian",
        "condition": "Diabetes",
        "allergies": "None",
        "weight": "75",
        "age": "30"
    }
    try:
        r = requests.post(f"{BASE_URL}/generate-diet-plan", data=data)
        print(r.status_code)
        print(r.text[:300])
    except Exception as e:
        errors.append(f"Diet Plan: {e}")

    # 8. Trends
    tprint("8. /trends")
    try:
        r = requests.get(f"{BASE_URL}/trends")
        print(r.status_code, r.text[:200])
    except Exception as e:
        errors.append(f"Trends: {e}")

    tprint("Summary")
    if errors:
        print("ERRORS ENCOUNTERED:")
        for err in errors:
            print(f" - {err}")
    else:
        print("All requests completed without exceptions.")

if __name__ == "__main__":
    test_endpoints()
