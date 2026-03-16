import sys
import json
import logging
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image

# Vision LLM — replaces Tesseract entirely
from llm_local import vision_analyze

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------- VISION PROMPT ----------
PRESCRIPTION_PROMPT = """You are an expert medical prescription reader.
Look carefully at this prescription image and extract all information.

Your task:
1. Read every medicine name visible in the image — including handwritten text.
   Use the correct standard pharmaceutical name (e.g. fix obvious misspellings).
2. For each medicine, extract:
   - Dosage strength (e.g. "500mg", "10mg") if visible
   - Frequency in '1-0-1' format (morning-afternoon-night):
       once daily      → "1-0-0"
       twice daily     → "1-0-1"
       three times/day → "1-1-1"
       as needed / PRN → "PRN"
   - Duration in days (integer) or "PRN" if as-needed
   - Timing instruction (e.g. "After Food", "Empty Stomach", "Before Bed")
3. Read the doctor name and hospital/clinic name if visible.

Return ONLY a JSON object with this exact structure:
{
  "doctor_name": "Dr. Name or Unknown",
  "hospital_name": "Clinic name or Unknown",
  "medicines": [
    {
      "medicine": "Medicine Name",
      "dosage": "500mg or null",
      "frequency": "1-0-1 or PRN",
      "days": 5,
      "timings": "After Food or null"
    }
  ]
}
"""


# ---------- MAIN PIPELINE ----------
def analyze_prescription(path):
    """
    Vision pipeline: Image → Vision Model → structured JSON
    Tesseract is not used. The vision model reads the image directly.
    Supports: PDF, PNG, JPG, JPEG, TIFF.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Prescription file not found: {path}")

    if path.suffix.lower() not in [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    logging.info(f"📄 Analyzing prescription with vision model: {path}")

    # Load image(s)
    if path.suffix.lower() == ".pdf":
        pages = convert_from_path(str(path), dpi=200)
        # For prescriptions, first page is almost always sufficient
        # For multi-page, we analyze page 1 (or could iterate)
        img = pages[0]
        if len(pages) > 1:
            logging.info(f"📄 PDF has {len(pages)} pages — analyzing page 1 (prescription page)")
    else:
        img = Image.open(str(path))

    # Ensure RGB for vision model
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    logging.info("🔍 Sending image to vision model for direct extraction...")
    result = vision_analyze(img, PRESCRIPTION_PROMPT)

    logging.info(f"✅ Extracted {len(result.get('medicines', []))} medicine(s)")
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
    except RuntimeError as e:
        logging.error(f"Vision model error: {e}")
        sys.exit(4)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(5)
