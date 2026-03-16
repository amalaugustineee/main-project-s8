import requests
import time

print("Uploading to /healthrisk...")
with open("test.jpg", "rb") as f:
    resp = requests.post("http://localhost:8000/healthrisk", files={"file": ("test.jpg", f, "image/jpeg")})

if resp.status_code != 200:
    print("Upload failed:", resp.text)
    exit(1)

job_id = resp.json().get("job_id")
print("Got job_id:", job_id)

while True:
    res = requests.get(f"http://localhost:8000/jobs/{job_id}")
    data = res.json()
    status = data.get("status")
    if status == "processing":
        print(".", end="", flush=True)
        time.sleep(2)
    elif status == "done":
        print("\nSuccess:", data.get("result"))
        break
    else:
        print("\nFailed:", data.get("error"))
        break
