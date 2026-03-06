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

# Local LLM (replaces Google Gemini)
from llm_local import llm_generate

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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
                "Tesseract not found. Install it and ensure it's on PATH, "
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

# ---------- LLM ANALYSIS ----------
def analyze_prescription_with_llm(ocr_text):
    """
    Sends OCR text to the local LLM and asks for structured JSON of medicines, frequency, and duration.
    """
    prompt = (
        "Extract prescription details from the following text. "
        "Return a **single JSON object** with the following keys:\n"
        "- 'doctor_name': Name of the doctor (or 'Unknown').\n"
        "- 'hospital_name': Name of the hospital/clinic (or 'Unknown').\n"
        "- 'medicines': A list of objects, each containing:\n"
        "   - 'medicine': Name of the medicine.\n"
        "   - 'frequency': Dosing frequency (e.g., '1-0-1').\n"
        "   - 'days': Duration (number of days or 'PRN').\n"
        "   - 'timings': Specific timing instructions (e.g., 'After Food', 'Empty Stomach', 'Night').\n\n"
        "Return ONLY the JSON object, no extra text.\n\n"
        f"Prescription text:\n{ocr_text}"
    )

    try:
        parsed = llm_generate(prompt, json_mode=True)
        return parsed
    except json.JSONDecodeError as e:
        logging.error(f"❌ Failed to parse LLM JSON output: {e}")
        raise
    except Exception as e:
        logging.error(f"❌ Local LLM error: {e}")
        raise

# ---------- MAIN PIPELINE ----------
def analyze_prescription(path):
    """
    Main pipeline: OCR → Local LLM → JSON output
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

    logging.info("🤖 Sending extracted text to local LLM for medicine extraction...")
    result = analyze_prescription_with_llm(ocr_text)

    # Print and return JSON
    print(json.dumps(result, indent=2))
    return result

# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Usage: python prescription_read.py <path_to_prescription>")
            print("\nExample:")
            print("  python prescription_read.py my_prescription.jpg")
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
