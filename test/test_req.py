import requests
import time
from PIL import Image
import io

# Create a dummy image
img = Image.new('RGB', (100, 100), color='white')
buf = io.BytesIO()
img.save(buf, format='PNG')
buf.seek(0)

print("Uploading to /prescription...")
resp = requests.post("http://localhost:8000/prescription", files={"file": ("test.png", buf, "image/png")})
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
