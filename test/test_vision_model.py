import sys
from PIL import Image
import llm_local

print("Testing Vision Model...")
try:
    img = Image.new('RGB', (100, 100), color = 'red')
    prompt = "What color is this image? Reply with a JSON object containing a 'color' key."
    res = llm_local.vision_analyze(img, prompt)
    print("Success:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Error:", e)
