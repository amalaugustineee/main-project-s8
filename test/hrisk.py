import sys
import json
import logging
from pathlib import Path
import requests
from requests.exceptions import RequestException
from pdf2image import convert_from_path
from PIL import Image

# Vision LLM — replaces Tesseract entirely
from llm_local import vision_analyze, llm_generate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# NCBI Endpoints
NCBI_ESearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_ESummary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Optional PubMed API key for higher rate limits
NCBI_API_KEY = ""

# ---------- VISION PROMPT ----------
LAB_REPORT_PROMPT = """You are an expert medical lab report reader with the ability to read printed, scanned, photographed, and digitally-generated lab reports.

Look carefully at this image. It may be:
- A photo of a printed lab report
- A scanned PDF page
- A digital/computer-generated lab report image
- A screenshot of a lab report

Your task — extract ALL visible medical test values:
1. Scan the ENTIRE image for any test name paired with a numeric result.
   Common section headers: CBC, Lipid Panel, Metabolic Panel, Thyroid, Renal, Liver, Urine.
2. For each test row you can see:
   - Test name (e.g. "Glucose", "HbA1c", "LDL Cholesterol")
   - Result value with unit (e.g. "115 mg/dL", "6.8 %")
   - Reference/normal range if visible — otherwise use standard medical ranges
   - How far the result deviates from normal (risk_percent 0-100)
3. If values are HIGHLIGHTED, FLAGGED, marked H/L/HIGH/LOW/ABNORMAL — assign risk_percent ≥ 50
4. Normal/within-range values → risk_percent 0-20
5. The summary should be a single sentence describing the overall health picture

Return ONLY a JSON object — no markdown, no extra text:
{
  "summary": "One sentence overall health summary based on the values seen",
  "tests": [
    {
      "name": "Glucose (Fasting)",
      "current_value": "115 mg/dL",
      "safe_range": "70-99 mg/dL",
      "risk_percent": 45,
      "risk_reason": "Fasting glucose of 115 mg/dL is above normal (70-99) — pre-diabetic range"
    }
  ]
}

If you genuinely cannot find ANY numeric medical values in the image, return:
{"summary": "No lab values detected", "tests": []}
"""



# ---------- PUBMED ----------
def fetch_pubmed_articles(test_name, retmax=2):
    """Returns short summaries and links from PubMed for the given test."""
    params = {
        "db": "pubmed",
        "term": f"{test_name} health risk meta-analysis",
        "retmode": "json",
        "retmax": retmax
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    try:
        r = requests.get(NCBI_ESearch, params=params, timeout=20)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        r = requests.get(NCBI_ESummary, params=params, timeout=20)
        r.raise_for_status()
        summaries = []
        for pid in ids:
            info = r.json().get("result", {}).get(pid)
            if info:
                summaries.append({
                    "title": info.get("title"),
                    "source": info.get("source"),
                    "pubdate": info.get("pubdate"),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
                })
        return summaries
    except Exception as e:
        logging.warning(f"PubMed fetch failed: {e}")
        return []


# ---------- MAIN ----------
def analyze_labreport(path):
    """
    Vision pipeline: Image → Vision Model → structured JSON
    Tesseract is not used. The vision model reads the table directly.
    Supports: PDF, PNG, JPG, JPEG, TIFF.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lab report file not found: {path}")

    if path.suffix.lower() not in ['.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff']:
        raise ValueError(f"Unsupported file type: {path.suffix}. Use PDF or common image formats.")

    logging.info(f"🔍 Analyzing lab report with vision model: {path}")

    # Load image(s)
    if path.suffix.lower() == ".pdf":
        pages = convert_from_path(str(path), dpi=200)
        # For multi-page lab reports, combine all pages
        # For now, use first page (most lab reports are single-page)
        img = pages[0]
        if len(pages) > 1:
            logging.info(f"📄 PDF has {len(pages)} pages — analyzing page 1")
    else:
        img = Image.open(str(path))

    # Ensure RGB for vision model
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    logging.info("🧠 Sending image to vision model for direct extraction...")
    try:
        llm_output = vision_analyze(img, LAB_REPORT_PROMPT)
    except Exception as e:
        logging.error(f"Vision model analysis failed: {e}")
        raise

    tests = llm_output.get("tests", [])
    logging.info(f"✅ Extracted {len(tests)} test result(s)")

    if not tests:
        logging.warning("No test results found — check image quality or model output")

    # Enrich each test with PubMed research
    for t in tests:
        name = t.get("name", "")
        try:
            articles = fetch_pubmed_articles(name)
            t["pubmed_support"] = articles
        except Exception as e:
            logging.warning(f"PubMed lookup failed for {name}: {e}")
            t["pubmed_support"] = []

    logging.info("\n===== Health Risk Analysis =====")
    return llm_output


# ---------- RUN ----------
if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Usage: python hrisk.py <path_to_lab_report>")
            print("\nExample:")
            print("  python hrisk.py lab_results.pdf")
            print("\nSupported formats: PDF, PNG, JPG, TIFF")
            sys.exit(1)

        result = analyze_labreport(sys.argv[1])
        print(json.dumps(result, indent=2))
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