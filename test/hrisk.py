import os
import sys
import json
import logging
from pathlib import Path
import requests
from requests.exceptions import RequestException
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import shutil
import re

# Local LLM (replaces Google Gemini)
from llm_local import llm_generate

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

# ---------- OCR ----------
def ocr_file(path):
    ext = os.path.splitext(path)[1].lower()

    # Ensure Tesseract is available. Allow override via TESSERACT_CMD env var.
    tcmd_env = os.getenv("TESSERACT_CMD")
    if tcmd_env:
        pytesseract.pytesseract.tesseract_cmd = tcmd_env

    tcmd = getattr(pytesseract.pytesseract, 'tesseract_cmd', None)
    if not tcmd or not shutil.which(os.path.basename(tcmd)):
        found = shutil.which('tesseract')
        if found:
            pytesseract.pytesseract.tesseract_cmd = found
        else:
            raise EnvironmentError(
                "Tesseract executable not found.\n"
                "Install Tesseract OCR and ensure it's on PATH, "
                "or set TESSERACT_CMD to the full path."
            )
    if ext == ".pdf":
        pages = convert_from_path(path, dpi=300)
        text = ""
        for page in pages:
            text += pytesseract.image_to_string(page) + "\n"
        return text
    else:
        img = Image.open(path)
        return pytesseract.image_to_string(img)

# ---------- LOCAL LLM ANALYSIS ----------
def analyze_with_llm(ocr_text):
    """
    Sends OCR text to local LLM and returns structured JSON analysis of lab report values and risks.
    """
    prompt = f"""
    You are a medical data analysis model. The following text is an OCR extraction from a patient's lab report.
    
    Your task:
    1. Identify each test and its current value with units.
    2. Compare each value with the safe/normal range.
    3. Assign a health risk percentage (0-100%) based on how far it deviates from normal.
    4. Give a short reason (using the test value).
    5. Output in **strict JSON** with the following structure:
    
    {{
      "summary": "overall health risk summary sentence",
      "tests": [
        {{
          "name": "LDL Cholesterol",
          "current_value": "165 mg/dL",
          "safe_range": "<100 mg/dL",
          "risk_percent": 75,
          "risk_reason": "LDL above 130 mg/dL increases CVD risk"
        }},
        ...
      ]
    }}
    
    Return **only JSON**, no extra text.
    
    Lab report text:
    \"\"\"{ocr_text}\"\"\"
    """

    try:
        parsed = llm_generate(prompt, json_mode=True)
        return parsed
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response from LLM: {e}")
        raise
    except Exception as e:
        logging.error(f"Local LLM analysis failed: {e}")
        raise

# ---------- PUBMED ----------
def fetch_pubmed_articles(test_name, retmax=2):
    """
    Returns short summaries and links from PubMed for the given test.
    """
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
    Main function to analyze a lab report file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lab report file not found: {path}")
        
    if path.suffix.lower() not in ['.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff']:
        raise ValueError(f"Unsupported file type: {path.suffix}. Use PDF or common image formats.")
    
    logging.info(f"🔍 OCR processing {path} ...")
    try:
        ocr_text = ocr_file(str(path))
    except Exception as e:
        logging.error(f"OCR processing failed: {e}")
        raise
    
    if not ocr_text.strip():
        raise ValueError("OCR produced no text. Check if the file is valid and readable.")
    
    logging.info("🧠 Sending to local LLM for structured analysis...")
    try:
        llm_output = analyze_with_llm(ocr_text)
    except Exception as e:
        logging.error(f"Local LLM analysis failed: {e}")
        raise
    
    tests = llm_output.get("tests", [])
    if not tests:
        logging.warning("No test results found in the analysis")
    
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
            
        analyze_labreport(sys.argv[1])
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