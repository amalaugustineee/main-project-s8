import pytesseract
from PIL import Image
import json
import os
import sys

# Local LLM (replaces Google Gemini)
from llm_local import llm_generate

# --- Configuration ---

# 1. Tesseract Config
tesseract_path = os.getenv('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    print(f"⚠️ Warning: Tesseract not found at '{tesseract_path}'. OCR may fail.", file=sys.stderr)


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


# --- LLM Call ---
def generate_diet_plan(current_health_status, region, cuisine, condition, weight, age, allergies, historical_context):
    """Generate diet plan using local LLM."""
    prompt = f"""
You are a specialized medical and nutritional AI assistant. Your task is to analyze the patient's latest health report, patient info, and historical health trends to generate a personalized health and diet plan.

Patient Data:
- Region: {region}
- Cuisine Preference: {cuisine}
- Medical Condition (Current): {condition}
- Weight: {weight} kg
- Age: {age} years
- Allergies/Restrictions: {allergies}

Historical Health Trends (Previous Reports):
{historical_context}

Latest Health Report Analysis (from Database):
---
{current_health_status}
---

Instructions:
1. Analyze the Latest Health Report to understand the user's immediate needs.
2. Consider the Historical Health Trends to see the trajectory.
3. Create a 7-day diet plan strictly adhering to the Region, Cuisine, and Allergies.
4. Provide recommendations that are medically sound and practical.

Return ONLY a JSON object with this exact structure (no other text):
{{
  "patient_info": {{
    "region": "string",
    "condition": "string",
    "weight_kg": "string",
    "age": "string"
  }},
  "lab_analysis": {{
    "extracted_values": [
      {{"parameter": "string", "value": 0, "unit": "string", "status": "string"}}
    ],
    "summary": "string",
    "concerns": ["string"]
  }},
  "diet_plan": {{
    "monday":    {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}},
    "tuesday":   {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}},
    "wednesday": {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}},
    "thursday":  {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}},
    "friday":    {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}},
    "saturday":  {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}},
    "sunday":    {{"breakfast": "string", "lunch": "string", "dinner": "string", "snacks": "string"}}
  }},
  "recommendations": {{
    "foods_to_include": ["string"],
    "foods_to_avoid": ["string"],
    "key_nutrients": ["string"],
    "hydration": "string",
    "exercise": "string"
  }}
}}
"""

    try:
        result = llm_generate(prompt, json_mode=True)
        # Return as JSON string (caller expects a string to json.loads())
        return json.dumps(result)
    except Exception as e:
        print(f"❌ Local LLM Error: {e}", file=sys.stderr)
        return None


# --- Main Execution ---
def main():
    if len(sys.argv) == 6:
        image_path, region, condition, weight, age = sys.argv[1:6]
    elif len(sys.argv) == 2 and sys.argv[1].lower() in ["-h", "--help"]:
        print("\nUsage:")
        print("  python dietplan.py <lab_report_image> <region> <condition> <weight_kg> <age_years>")
        print("\nExample:")
        print("  python dietplan.py lab.png 'South Indian' 'Type 2 Diabetes' 70 45")
        sys.exit(0)
    else:
        print("\n❌ Invalid usage.")
        print("Usage: python dietplan.py <lab_report_image> <region> <condition> <weight_kg> <age_years>")
        sys.exit(1)

    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    print(f"📄 Processing Lab Report: {os.path.basename(image_path)}")

    ocr_text = extract_text_from_image(image_path)
    if not ocr_text:
        print("❌ OCR extraction failed. Aborting.", file=sys.stderr)
        sys.exit(1)

    print("🧠 Generating structured diet plan using local LLM...")
    result_text = generate_diet_plan(ocr_text, region, "", condition, weight, age, "", "")

    if not result_text:
        print("❌ Failed to get response from local LLM.", file=sys.stderr)
        sys.exit(1)

    try:
        parsed = json.loads(result_text)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        with open("diet_plan_output.json", "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        print("\n✅ Success! Output saved to diet_plan_output.json")
    except json.JSONDecodeError as e:
        print(f"❌ LLM response not valid JSON: {e}", file=sys.stderr)
        print(result_text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
