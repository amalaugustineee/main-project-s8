import pytesseract
from PIL import Image
from google import genai
from google.genai import types
import json
import os
import sys

# --- Configuration & Initialization ---

# 1. Tesseract Config
tesseract_path = os.getenv('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    print(f"⚠️ Warning: Tesseract not found at '{tesseract_path}'. OCR may fail.", file=sys.stderr)

# 2. Gemini Client Config
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("❌ Error: GEMINI_API_KEY not set.", file=sys.stderr)
    sys.exit(1)

try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    print(f"❌ Error initializing Gemini client: {e}", file=sys.stderr)
    sys.exit(1)


# --- Core Functions ---
def extract_text_from_image(image_path):
    """Extract text from image using OCR."""
    try:
        image = Image.open(image_path)
        extracted_text = pytesseract.image_to_string(image, lang='eng')
        return extracted_text.strip()
    except Exception as e:
        print(f"❌ OCR Error ({image_path}): {e}", file=sys.stderr)
        return ""


# --- JSON Schema (unchanged) ---
JSON_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "patient_info": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "region": types.Schema(type=types.Type.STRING),
                "condition": types.Schema(type=types.Type.STRING),
                "weight_kg": types.Schema(type=types.Type.STRING),
                "age": types.Schema(type=types.Type.STRING)
            }
        ),
        "lab_analysis": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "extracted_values": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "parameter": types.Schema(type=types.Type.STRING),
                            "value": types.Schema(type=types.Type.NUMBER),
                            "unit": types.Schema(type=types.Type.STRING),
                            "status": types.Schema(type=types.Type.STRING)
                        },
                        required=["parameter", "value", "unit", "status"]
                    )
                ),
                "summary": types.Schema(type=types.Type.STRING),
                "concerns": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING))
            }
        ),
        "diet_plan": types.Schema(
            type=types.Type.OBJECT,
            properties={day: types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "breakfast": types.Schema(type=types.Type.STRING),
                    "lunch": types.Schema(type=types.Type.STRING),
                    "dinner": types.Schema(type=types.Type.STRING),
                    "snacks": types.Schema(type=types.Type.STRING)
                }
            ) for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]}
        ),
        "recommendations": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "foods_to_include": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "foods_to_avoid": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "key_nutrients": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "hydration": types.Schema(type=types.Type.STRING),
                "exercise": types.Schema(type=types.Type.STRING)
            }
        )
    },
    required=["patient_info", "lab_analysis", "diet_plan", "recommendations"]
)


# --- Gemini Call ---
def generate_diet_plan(ocr_text, region, condition, weight, age):
    """Generate diet plan using Gemini AI."""
    prompt = f"""
You are a specialized medical and nutritional AI assistant. Your task is to analyze a lab report's OCR text and patient info to generate a health and diet plan.

Patient Data:
- Region/Cuisine: {region}
- Medical Condition: {condition}
- Weight: {weight} kg
- Age: {age} years

Lab Report OCR Text:
---
{ocr_text}
---

Follow JSON structure strictly (schema enforced). Analyze lab values, summarize key findings, create a 7-day diet plan, and add recommendations.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JSON_SCHEMA
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini API Error: {e}", file=sys.stderr)
        return None


# --- Main Execution ---
def main():
    if len(sys.argv) == 6:
        image_path, region, condition, weight, age = sys.argv[1:6]
        is_interactive = False
    elif len(sys.argv) == 2 and sys.argv[1].lower() in ["-h", "--help"]:
        print("\nUsage:")
        print("  python script.py <lab_report_image> <region> <condition> <weight_kg> <age_years>")
        print("\nExample:")
        print("  python script.py C:\\reports\\lab.png 'South Indian' 'Type 2 Diabetes' 70 45")
        sys.exit(0)
    else:
        print("\n❌ Invalid usage.")
        print("Usage: python script.py <lab_report_image> <region> <condition> <weight_kg> <age_years>")
        sys.exit(1)

    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    print(f"📄 Processing Lab Report: {os.path.basename(image_path)}")

    ocr_text = extract_text_from_image(image_path)
    if not ocr_text:
        print("❌ OCR extraction failed. Aborting.", file=sys.stderr)
        sys.exit(1)

    print("🧠 Generating structured diet plan using Gemini...")
    result_text = generate_diet_plan(ocr_text, region, condition, weight, age)

    if not result_text:
        print("❌ Failed to get response from Gemini.", file=sys.stderr)
        sys.exit(1)

    try:
        parsed = json.loads(result_text)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        with open("diet_plan_output.json", "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        print("\n✅ Success! Output saved to diet_plan_output.json")
    except json.JSONDecodeError as e:
        print(f"❌ Gemini response not valid JSON: {e}", file=sys.stderr)
        print(result_text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
