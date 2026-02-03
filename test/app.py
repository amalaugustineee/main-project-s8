from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
import tempfile
import os
import json



# Import callable functions from your local scripts
from datetime import datetime
from dotenv import load_dotenv
load_dotenv("../.env")

from prescription_read import analyze_prescription
from hrisk import analyze_labreport
from dietplan import extract_text_from_image, generate_diet_plan

# Database imports
from sqlmodel import Session, select, SQLModel
from database import create_db_and_tables, get_session
from models import HealthReport, TestResult, Prescription, PrescriptionMedicine
from fastapi import Depends
from typing import List

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

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

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

# Retry Helper
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def safe_generate(model, contents):
    try:
        return gemini_client.models.generate_content(model=model, contents=contents)
    except Exception as e:
        print(f"⚠️ safe_generate failed (attempting retry): {e}")
        raise e

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
@app.get("/prescription/history")
def get_prescription_history(session: Session = Depends(get_session)):
    """Get a list of past prescriptions with their medicines."""
    prescriptions = session.exec(select(Prescription).order_by(Prescription.created_at.desc())).all()
    # We rely on Relationship loading (lazy or default) or we can just return properties
    # SQLModel relationships might need explicit inclusion if not default.
    # However, for simple JSON response, fastapi will try to serialize. 
    # Let's ensure we return what's needed.
    return prescriptions 

@app.post("/prescription")
async def prescription_analysis(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """
    Upload a prescription image/PDF, extract medicine details using Gemini, and save to DB.
    """
    path = save_temp_file(file)
    try:
        # Analyzed result is now a dict: {'doctor_name':..., 'hospital_name':..., 'medicines': [...]}
        result = analyze_prescription(path)
        
        # --- Save to Time Series DB ---
        try:
            # Create Prescription Record
            doc_name = result.get("doctor_name", "Unknown")
            hosp_name = result.get("hospital_name", "Unknown")
            pres = Prescription(hospital_name=hosp_name, doctor_name=doc_name)
            
            session.add(pres)
            session.commit()
            session.refresh(pres)
            
            # Create Medicine Records
            meds = result.get("medicines", [])
            if isinstance(meds, list):
                for item in meds:
                    pm = PrescriptionMedicine(
                        prescription_id=pres.id,
                        medicine_name=item.get("medicine", "Unknown"),
                        frequency=item.get("frequency", ""),
                        duration=str(item.get("days", "")),
                        dosage="", # parsed if available
                        timings=item.get("timings", "")
                    )
                    session.add(pm)
                session.commit()
                
            # --- Schedule Reminders (Redis) ---
                
            # --- Schedule Reminders (Redis) ---
            # Removed per user request
            # await schedule_medicine_reminders(meds)
            
        except Exception as db_e:
            print(f"⚠️ Failed to save prescription to DB: {db_e}")
            
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prescription analysis failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------- 2. Health-Risk Endpoint ----------
@app.post("/health/summary")
def health_summary(session: Session = Depends(get_session)):
    """
    Analyze current health condition based on historical Lab Reports and Prescriptions.
    """
    if not gemini_client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    # 1. Fetch recent Lab Reports (last 5)
    reports = session.exec(select(HealthReport).order_by(HealthReport.created_at.desc()).limit(5)).all()
    
    lab_context = "No recent lab reports found."
    if reports:
        lab_context = ""
        for r in reports:
            lab_context += f"\n--- Report Date: {r.created_at.strftime('%Y-%m-%d')} ---\n"
            lab_context += f"Summary: {r.summary}\n"
            for t in r.test_results:
                lab_context += f"  - {t.test_name}: {t.value} {t.unit} (Risk: {t.risk_percent}% - {t.risk_reason})\n"

    # 2. Fetch recent Prescriptions (last 5)
    prescriptions = session.exec(select(Prescription).order_by(Prescription.created_at.desc()).limit(5)).all()
    
    med_context = "No recent prescriptions found."
    if prescriptions:
        med_context = ""
        for p in prescriptions:
            med_context += f"\n--- Prescription Date: {p.created_at.strftime('%Y-%m-%d')} ---\n"
            for m in p.medicines:
                med_context += f"  - {m.medicine_name} (Freq: {m.frequency}, Timing: {m.timings or 'N/A'}, Duration: {m.duration})\n"

    # 3. Ask Gemini
    prompt = f"""
    You are a detailed medical AI assistant. Analyze the patient's Current Health Condition based on their history.
    
    ### PATIENT HISTORY
    
    **Lab Report History (Trends):**
    {lab_context}
    
    **Prescription History:**
    {med_context}
    
    ### INSTRUCTIONS
    1. **Current Status**: Summarize their health status. Are they improving? Deteriorating? specific conditions?
    2. **Risk Analysis**: Highlight any concerning trends (e.g. rising blood sugar, consistent high BP).
    3. **Action Plan**: Suggest immediate actions (e.g. "Consult Cardiologist") and lifestyle changes.
    4. **Output Format**: Return **STRICT MARKDOWN**. 
       - Use `## Headings` for sections.
       - Use `**Bold**` for key terms.
       - Use `- Bullet points` for lists.
       - Do NOT use plain text blocks. Structure everything clearly.
    """
    
    try:
        from tenacity import RetryError
        try:
            resp = safe_generate(
                model="gemini-2.5-flash-preview-09-2025",
                contents=prompt,
            )
            return {"analysis": resp.text}
        except RetryError as re:
            last_exc = re.last_attempt.exception()
            raise HTTPException(status_code=500, detail=f"Gemini Analysis Failed: {str(last_exc)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Analysis Failed: {e}")



# ---------- 2. Health-Risk Endpoint ----------
@app.post("/healthrisk")
async def health_risk_analysis(file: UploadFile = File(...)):
    """
    Upload a lab report image/PDF and analyze health risks with PubMed enrichment.
    """
    path = save_temp_file(file)
    try:
        from tenacity import RetryError
        try:
            result = analyze_labreport(path)
            return JSONResponse(content=result)
        except RetryError as re:
             # Get the original exception
             last_exc = re.last_attempt.exception()
             return JSONResponse(
                 status_code=500, 
                 content={"detail": f"⚠️ AI Service Failure: {str(last_exc)}"}
             )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health-risk analysis failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------- 3. Diet-Plan Endpoint ----------
# ---------- 3. Diet-Plan Endpoint ----------
@app.post("/generate-diet-plan")
async def diet_plan_generation(
    region: str = Form(""),
    cuisine: str = Form(""),
    condition: str = Form(""),
    allergies: str = Form(""),
    weight: float = Form(0.0),
    age: int = Form(0),
    session: Session = Depends(get_session)
):
    """
    Generate a personalized diet plan using the patient's existing health records.
    No file upload required - uses the latest Lab Report from the database.
    """
    try:
        # 1. Fetch History (Last 10 Reports to find latest + history)
        # We need at least 1 report to generate a plan based on "Current Health"
        reports = session.exec(select(HealthReport).order_by(HealthReport.created_at.desc()).limit(10)).all()
        
        if not reports:
            raise HTTPException(status_code=400, detail="No health reports found. Please analyze a Lab Report (Risk Assessment) first.")

        # 2. Separate Latest vs History
        latest_report = reports[0]
        history_reports = reports[1:] if len(reports) > 1 else []

        # Format Structure for Latest Report
        current_health_status = f"Report Date: {latest_report.created_at.strftime('%Y-%m-%d')}\n"
        current_health_status += f"Summary: {latest_report.summary}\nTests:\n"
        for t in latest_report.test_results:
             current_health_status += f"- {t.test_name}: {t.value} {t.unit} (Risk: {t.risk_percent}% - {t.risk_reason})\n"

        # Format Structure for History
        historical_context = "No previous history available."
        if history_reports:
            historical_context = ""
            for r in history_reports:
                historical_context += f"\n--- Report Date: {r.created_at.strftime('%Y-%m-%d')} ---\n"
                historical_context += f"Summary: {r.summary}\n"
                for t in r.test_results:
                     historical_context += f"- {t.test_name}: {t.value} {t.unit} (Risk: {t.risk_percent}%)\n"

        # 3. Generate Plan
        result_text = generate_diet_plan(
            current_health_status, 
            region, 
            cuisine, 
            condition, 
            weight, 
            age, 
            allergies, 
            historical_context
        )
        
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


# ---------- Root ----------
@app.get("/")
def root():
    return {"message": "✅ Medical Intelligence API running. Visit /docs for Swagger UI."}



# ---------- 4. Wellbeing Chat & Retrieval ----------
class ChatRequest(BaseModel):
    question: str

def search_lab_reports(session: Session, start_date: datetime = None, end_date: datetime = None, keyword: str = None) -> str:
    """Search for lab reports based on date range and keywords."""
    query = select(HealthReport).order_by(HealthReport.created_at.desc())
    
    if start_date:
        query = query.where(HealthReport.created_at >= start_date)
    if end_date:
        query = query.where(HealthReport.created_at <= end_date)
        
    results = session.exec(query).all()
    
    # Filter by keyword in Python if needed (simpler for now)
    filtered = []
    for r in results:
        # If keyword provided, check summary or test names
        if keyword:
            kw = keyword.lower()
            if kw in r.summary.lower():
                filtered.append(r)
                continue
            # Check tests
            for t in r.test_results:
                if kw in t.test_name.lower():
                    filtered.append(r)
                    break
        else:
            filtered.append(r)
            
    if not filtered:
        return "No lab reports found matching your criteria."
        
    # Format output
    output = ""
    for r in filtered:
        output += f"\n--- Lab Report ({r.created_at.strftime('%Y-%m-%d')}) ---\n"
        output += f"Summary: {r.summary}\n"
        for t in r.test_results:
             output += f"- {t.test_name}: {t.value} {t.unit} (Risk: {t.risk_percent}%)\n"
    return output

def search_prescriptions(session: Session, start_date: datetime = None, end_date: datetime = None, keyword: str = None) -> str:
    """Search for prescriptions based on date range and keywords."""
    query = select(Prescription).order_by(Prescription.created_at.desc())
    
    if start_date:
        query = query.where(Prescription.created_at >= start_date)
    if end_date:
        query = query.where(Prescription.created_at <= end_date)
        
    results = session.exec(query).all()
    
    filtered = []
    for p in results:
        if keyword:
            kw = keyword.lower()
            # Check doctor or medicines
            found = False
            if p.doctor_name and kw in p.doctor_name.lower():
                found = True
            else:
                for m in p.medicines:
                    if kw in m.medicine_name.lower():
                        found = True
                        break
            if found:
                filtered.append(p)
        else:
            filtered.append(p)
            
    if not filtered:
        return "No prescriptions found matching your criteria."
        
    output = ""
    for p in filtered:
        output += f"\n--- Prescription ({p.created_at.strftime('%Y-%m-%d')}) ---\n"
        output += f"Doctor: {p.doctor_name or 'N/A'}\n"
        for m in p.medicines:
            output += f"- {m.medicine_name} ({m.frequency} for {m.duration})\n"
    return output

@app.post("/wellbeing-chat")
async def wellbeing_chat(req: ChatRequest, session: Session = Depends(get_session)):
    """
    Intelligent chatbot (Optimized Single-Call).
    Proactively fetches context to avoid double-calling the API.
    """
    if not gemini_client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    user_q = (req.question or "").strip()
    if not user_q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # --- Step 1: Proactive Context Fetching (Cheap DB Ops) ---
    # We fetch the last 3 reports and last 3 prescriptions to provide context "just in case"
    # This saves us from making a "Classifier" call to Gemini first.
    
    # Lab Reports
    recent_reports = session.exec(select(HealthReport).order_by(HealthReport.created_at.desc()).limit(3)).all()
    lab_context = ""
    if recent_reports:
        for r in recent_reports:
            lab_context += f"- Report ({r.created_at.strftime('%Y-%m-%d')}): {r.summary}\n"
            
    # Prescriptions
    recent_prescriptions = session.exec(select(Prescription).order_by(Prescription.created_at.desc()).limit(3)).all()
    med_context = ""
    if recent_prescriptions:
        for p in recent_prescriptions:
            med_details = []
            for m in p.medicines:
                detail = f"{m.medicine_name} ({m.frequency or '?'} - {m.timings or 'No timing'})"
                med_details.append(detail)
            med_str = ", ".join(med_details)
            med_context += f"- Prescription ({p.created_at.strftime('%Y-%m-%d')}): {med_str} (Dr. {p.doctor_name})\n"

    # --- Step 2: Unified Prompt (1 Call) ---
    system_preamble = (
        "You are a helpful medical assistant. The user is asking a question.\n"
        "We have fetched some recent medical history for you context:\n\n"
        f"**Recent Lab Reports:**\n{lab_context or 'None'}\n\n"
        f"**Recent Prescriptions:**\n{med_context or 'None'}\n\n"
        "**Instructions:**\n"
        "1. If the user asks about their reports/medicines, use the context above.\n"
        "2. If the user asks a general health question, answer generally.\n"
        "3. Keep answers concise and helpful. formatting in Markdown."
    )

    try:
        final_resp = safe_generate(
            model="gemini-2.5-flash-preview-09-2025",
            contents=f"{system_preamble}\n\nUser Question: {user_q}"
        )
        return {"answer": final_resp.text}

    except Exception as e:
        # Graceful error handling
        from tenacity import RetryError
        if isinstance(e, RetryError):
            e = e.last_attempt.exception()
        return {"answer": f"⚠️ **System Error**: {str(e)}"}



# ---------- 5. Reports & Trends Endpoints ----------

class SaveReportRequest(BaseModel):
    analysis_result: dict
    timestamp: str | None = None  # User can optionally provide a date, else now

@app.post("/reports/save")
def save_report(req: SaveReportRequest, session: Session = Depends(get_session)):
    """
    Save a health report and its test results to the database.
    """
    try:
        data = req.analysis_result
        summary = data.get("summary", "No summary provided")
        
        # Create Report
        report = HealthReport(
            summary=summary,
            raw_json=json.dumps(data)
            # created_at defaults to now
        )
        session.add(report)
        session.commit()
        session.refresh(report)

        # Create Test Results
        tests = data.get("tests", [])
        for t in tests:
            # Parse value safely (basic parsing, handling "165 mg/dL")
            raw_val = str(t.get("current_value", "0"))
            import re
            # Extract first float found
            match = re.search(r"[-+]?\d*\.\d+|\d+", raw_val)
            val_float = float(match.group()) if match else 0.0
            
            unit = t.get("current_value", "").replace(str(val_float), "").strip()

            test_result = TestResult(
                report_id=report.id,
                test_name=t.get("name", "Unknown"),
                value=val_float,
                unit=unit,
                risk_percent=t.get("risk_percent", 0),
                risk_reason=t.get("risk_reason"),
                timestamp=report.created_at
            )
            session.add(test_result)
        
        session.commit()
        return {"message": "Report saved successfully", "report_id": report.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save report: {e}")

from sqlalchemy.orm import selectinload

# Read Models for API Responses
class TestResultRead(SQLModel):
    test_name: str
    value: float
    unit: str
    risk_percent: int
    timestamp: datetime

class HealthReportRead(SQLModel):
    id: int
    created_at: datetime
    summary: str
    test_results: List[TestResultRead] = []

@app.get("/reports/history", response_model=List[HealthReportRead])
def get_report_history(session: Session = Depends(get_session)):
    """Get a list of past reports with their test results."""
    statement = select(HealthReport).options(selectinload(HealthReport.test_results)).order_by(HealthReport.created_at.desc())
    reports = session.exec(statement).all()
    return reports

@app.get("/trends")
def get_trend_parameters(session: Session = Depends(get_session)):
    """Get list of available test names for trending."""
    # distinct test names
    statement = select(TestResult.test_name).distinct()
    results = session.exec(statement).all()
    return {"parameters": results}

@app.get("/trends/{test_name}")
def get_trend_data(test_name: str, session: Session = Depends(get_session)):
    """Get historical data for a specific test."""
    statement = select(TestResult).where(TestResult.test_name == test_name).order_by(TestResult.timestamp)
    results = session.exec(statement).all()
# ---------- 6. Reminders (Queue) ----------
from datetime import datetime, timedelta

def parse_frequency(freq_str: str, timings_str: str = "") -> List[str]:
    """
    Returns a list of daily times (HH:MM) based on frequency/timings.
    """
    times = []
    freq = freq_str.replace(" ", "").replace("-", "") # "101"
    
    # Standard patterns
    if freq == "101":
        times = ["08:00", "20:00"]
    elif freq == "111":
        times = ["08:00", "13:00", "20:00"]
    elif freq == "100":
        times = ["08:00"]
    elif freq == "001":
        times = ["20:00"]
    elif freq == "010":
        times = ["13:00"]
    else:
        # Heuristic fallbacks based on timing string
        t_lower = timings_str.lower()
        if "night" in t_lower or "bed" in t_lower:
            times.append("21:00")
        if "morning" in t_lower or "breakfast" in t_lower:
            times.append("08:30")
        if "afternoon" in t_lower or "lunch" in t_lower:
            times.append("13:30")
            
    # If still empty, default to 9AM
    if not times:
        times = ["09:00"]
        
    return times

@app.get("/reminders/upcoming")
def get_upcoming_reminders(param: str = None, session: Session = Depends(get_session)):
    """
    Returns next 3 upcoming doses for active medicines.
    Example: 
    [
      {"medicine": "Dolo", "time": "20:00", "status": "Upcoming", "instruction": "After Food"},
      ...
    ]
    """
    if not session:
        return []
    
    # Get all medicines from recent prescriptions (simple logic: all for now)
    # Ideally filter by date, but for demo we take all distinct names.
    stmt = select(PrescriptionMedicine)
    results = session.exec(stmt).all()
    
    seen_meds = set()
    upcoming_queue = []
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    for m in results:
        # Avoid duplicates (if multiple prescriptions have same med, take latest - logic simplified here)
        if m.medicine_name in seen_meds:
            continue
        seen_meds.add(m.medicine_name)
        
        daily_times = parse_frequency(str(m.frequency), str(m.timings or ""))
        
        # Calculate Next Dose for TODAY
        for t in daily_times:
            # If time is in future today
            if t > current_time_str:
                upcoming_queue.append({
                    "medicine": m.medicine_name,
                    "time": t, # HH:MM
                    "date": "Today",
                    "instruction": m.timings or m.frequency or "As prescribed",
                    "sort_key": f"{now.strftime('%Y-%m-%d')} {t}"
                })
            else:
                # It's tomorrow
                upcoming_queue.append({
                    "medicine": m.medicine_name,
                    "time": t,
                    "date": "Tomorrow",
                    "instruction": m.timings or m.frequency or "As prescribed",
                    "sort_key": f"{(now + timedelta(days=1)).strftime('%Y-%m-%d')} {t}"
                })

    # Sort by time
    upcoming_queue.sort(key=lambda x: x['sort_key'])
    
    # Return top 5
    return upcoming_queue[:5]



# ---------- 6. Notifications & Redis (REMOVED) ----------
# Reverted to simplify architecture per user request.
