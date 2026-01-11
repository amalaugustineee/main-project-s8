from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
import tempfile
import os
import json

# Import callable functions from your local scripts
from prescription_read import analyze_prescription
from hrisk import analyze_labreport
from dietplan import extract_text_from_image, generate_diet_plan

app = FastAPI(
    title="Medical Intelligence API",
    description=(
        "Unified API providing:\n"
        "1️⃣ Prescription text extraction → JSON of medicines/dosage\n"
        "2️⃣ Lab report analysis → Health-risk + PubMed enrichment\n"
        "3️⃣ Personalized diet planning → Region/condition-aware meal plan"
    ),
    version="2.0.0"
)

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development. Tighten in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Gemini Client (shared) ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ---------- Utility ----------
def save_temp_file(uploaded_file: UploadFile) -> str:
    """Save uploaded file to a temporary location and return its path."""
    suffix = os.path.splitext(uploaded_file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.file.read())
        tmp_path = tmp.name
    uploaded_file.file.close()
    return tmp_path


# ---------- 1. Prescription Endpoint ----------
@app.post("/prescription")
async def prescription_analysis(file: UploadFile = File(...)):
    """
    Upload a prescription image/PDF and extract medicine details using Gemini.
    """
    path = save_temp_file(file)
    try:
        result = analyze_prescription(path)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prescription analysis failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------- 2. Health-Risk Endpoint ----------
@app.post("/healthrisk")
async def health_risk_analysis(file: UploadFile = File(...)):
    """
    Upload a lab report image/PDF and analyze health risks with PubMed enrichment.
    """
    path = save_temp_file(file)
    try:
        result = analyze_labreport(path)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health-risk analysis failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------- 3. Diet-Plan Endpoint ----------
@app.post("/generate-diet-plan")
async def diet_plan_generation(
    file: UploadFile = File(...),
    region: str = Form(...),
    condition: str = Form(...),
    weight: float = Form(...),
    age: int = Form(...)
):
    """
    Upload a lab report and generate a personalized diet plan.
    Requires additional inputs: region, condition, weight, and age.
    """
    path = save_temp_file(file)
    try:
        ocr_text = extract_text_from_image(path)
        if not ocr_text:
            raise HTTPException(status_code=400, detail="OCR failed: no readable text found.")

        result_text = generate_diet_plan(ocr_text, region, condition, weight, age)
        if not result_text:
            raise HTTPException(status_code=500, detail="Gemini returned empty response.")

        try:
            parsed_json = json.loads(result_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Gemini returned invalid JSON format.")

        return JSONResponse(content=parsed_json)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diet-plan generation failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------- Root ----------
@app.get("/")
def root():
    return {"message": "✅ Medical Intelligence API running. Visit /docs for Swagger UI."}


# ---------- 4. Wellbeing Chat (general health Q&A) ----------
class ChatRequest(BaseModel):
    question: str


@app.post("/wellbeing-chat")
async def wellbeing_chat(req: ChatRequest):
    """
    Answer general daily well-being and non-diagnostic health questions using Gemini.
    This avoids advanced diagnostics; provides lifestyle, nutrition, hydration, sleep,
    exercise, and general guidance. Not a substitute for professional medical advice.
    """
    if not gemini_client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server")

    user_q = (req.question or "").strip()
    if not user_q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    system_preamble = (
        "You are a friendly wellbeing assistant. Answer only general, day-to-day health questions. "
        "Avoid diagnosing diseases or interpreting lab results. Emphasize hydration, balanced diet, "
        "sleep hygiene, stress management, safe exercise, and when to seek professional care. "
        "Keep answers practical, concise, and non-alarming."
    )

    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_preamble}\n\nUser question: {user_q}",
        )
        answer = (resp.text or "").strip()
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")
