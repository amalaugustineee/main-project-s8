import os
import sys
import json
import logging
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import shutil
import re
from google import genai  # ✅ Official Gemini SDK

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------- CONFIG ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError("❌ GEMINI_API_KEY environment variable not set")

# Initialize Gemini SDK client
client = genai.Client(api_key=GEMINI_API_KEY)

# ---------- OCR ----------
def ocr_file(path):
    """
    Perform OCR using Tesseract on image or PDF.
    Supports: PDF, PNG, JPG, JPEG, TIFF.
    """
    ext = os.path.splitext(path)[1].lower()

    # On Windows, allow explicit Tesseract path
    tcmd_env = os.getenv("TESSERACT_CMD")
    if tcmd_env:
        pytesseract.pytesseract.tesseract_cmd = tcmd_env

    # If no Tesseract detected, try auto-detect
    tcmd = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    if not tcmd or not shutil.which(os.path.basename(tcmd)):
        found = shutil.which("tesseract")
        if found:
            pytesseract.pytesseract.tesseract_cmd = found
        else:
            raise EnvironmentError(
                "Tesseract not found. Install it and ensure it’s on PATH, "
                "or set TESSERACT_CMD to the full path to tesseract.exe."
            )

    # OCR from PDF or image
    if ext == ".pdf":
        pages = convert_from_path(path, dpi=300)
        text = ""
        for page in pages:
            text += pytesseract.image_to_string(page, lang="eng") + "\n"
        return text
    else:
        img = Image.open(path)
        return pytesseract.image_to_string(img, lang="eng")

# ---------- GEMINI (SDK) ----------
def analyze_prescription_with_gemini(ocr_text):
    """
    Sends OCR text to Gemini and asks for structured JSON of medicines, frequency, and duration.
    """
    prompt = (
        "Extract medicine details from the following prescription text. "
        "Return the result as a **single-line JSON array of objects**. "
        "Each object must contain: "
        "'medicine' → name of the medicine, "
        "'frequency' → when to take the medicine (morning-afternoon-night) like '1-0-1', "
        "'days' → number of days to take it or 'PRN' if as needed. "
        "If the text is unclear, infer possible values carefully.\n\n"
        f"Prescription text:\n{ocr_text}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()
        # Remove any Markdown-style code fences (```json ... ```)
        cleaned = re.sub(r"^\s*```json\s*|\s*```\s*$", "", text, flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        return parsed

    except json.JSONDecodeError as e:
        logging.error(f"❌ Failed to parse Gemini JSON output: {text[:500]}...")
        raise
    except Exception as e:
        logging.error(f"❌ Gemini API error: {e}")
        raise

# ---------- MAIN PIPELINE ----------
def analyze_prescription(path):
    """
    Main pipeline: OCR → Gemini → JSON output
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Prescription file not found: {path}")

    if path.suffix.lower() not in [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    logging.info(f"📄 Reading prescription from: {path}")
    ocr_text = ocr_file(str(path))
    if not ocr_text.strip():
        raise ValueError("OCR produced no readable text. Check file clarity.")

    logging.info("🤖 Sending extracted text to Gemini for medicine extraction...")
    result = analyze_prescription_with_gemini(ocr_text)

    # Print and return JSON
    print(json.dumps(result, indent=2))
    return result

# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Usage: python prescription_parser_gemini.py <path_to_prescription>")
            print("\nExample:")
            print("  python prescription_parser_gemini.py my_prescription.jpg")
            sys.exit(1)

        analyze_prescription(sys.argv[1])
        sys.exit(0)

    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
        sys.exit(2)
    except ValueError as e:
        logging.error(f"Error: {e}")
        sys.exit(3)
    except EnvironmentError as e:
        logging.error(f"Environment Error: {e}")
        sys.exit(4)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(5)
