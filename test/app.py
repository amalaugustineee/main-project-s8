from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import os
import json
from icalendar import Calendar, Event, vText
import uuid
from datetime import datetime, timedelta, date

import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from pypdf import PdfReader
import io

# Local LLM (replaces Google Gemini)
from llm_local import llm_generate
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

# --- Initialize ChromaDB for Local RAG ---
chroma_client = chromadb.PersistentClient(path="./chroma_db")
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text",
)
rag_collection = chroma_client.get_or_create_collection(
    name="medical_records", 
    embedding_function=ollama_ef
)

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development. Tighten in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Local LLM (Ollama) ----------
# llm_generate() is imported from llm_local.py above.
# No API key needed — runs locally via Ollama.

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
            
            # Add the DB ID to the response so the frontend can generate calendar exports
            result["prescription_id"] = pres.id
            
        except Exception as db_e:
            print(f"⚠️ Failed to save prescription to DB: {db_e}")
            
        # --- FEATURE 3: Smart Medication Interaction Checker ---
        try:
            # Fetch past prescriptions (last 3, excluding the current one)
            recent_pres = session.exec(select(Prescription).where(Prescription.id != pres.id).order_by(Prescription.created_at.desc()).limit(3)).all()
            
            if recent_pres:
                existing_meds = []
                for rp in recent_pres:
                    for m in rp.medicines:
                        existing_meds.append(m.medicine_name)
                
                new_meds = [m.get("medicine", "") for m in result.get("medicines", [])]
                
                if existing_meds and new_meds:
                    prompt = f"""
You are a pharmacology AI. The patient is currently taking these medications: {', '.join(set(existing_meds))}.
They were just prescribed these NEW medications: {', '.join(new_meds)}.

Check for any severe or highly notable drug-drug interactions between the CURRENT and NEW medications.

Return ONLY a JSON object (no markdown, no extra text) with this exact structure:
{{
  "has_interactions": true,
  "warnings": ["Warning 1", "Warning 2"]
}}
If there are no notable interactions, return has_interactions as false and an empty list for warnings.
"""
                    interaction_res = llm_generate(prompt, json_mode=True)
                    result["interactions"] = interaction_res
        except Exception as interaction_e:
            print(f"⚠️ Failed to check drug interactions: {interaction_e}")
            
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prescription analysis failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)

@app.get("/prescription/{pres_id}/calendar")
def export_prescription_calendar(pres_id: int, session: Session = Depends(get_session)):
    """Generate an .ics file with medication reminders for a given prescription."""
    pres = session.get(Prescription, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="Prescription not found")

    cal = Calendar()
    cal.add('prodid', '-//Mediware Intelligence API//Calendar Export//EN')
    cal.add('version', '2.0')
    
    # Simple logic for duration, defaulting to 7 days
    duration_days = 7
    if pres.medicines and pres.medicines[0].duration:
        try:
            # try to extract a number from duration string
            digits = [int(s) for s in pres.medicines[0].duration.split() if s.isdigit()]
            if digits:
                duration_days = digits[0]
        except Exception:
            pass

    start_date = date.today()
    end_date = start_date + timedelta(days=duration_days)
    
    for med in pres.medicines:
        # Parse frequency (e.g., 1-0-1 or 101) to specific times
        daily_times = parse_frequency(str(med.frequency), str(med.timings or ""))
        
        for time_str in daily_times:
            # Create a recurring event
            event = Event()
            event.add('summary', f"Take {med.medicine_name}")
            
            # Simple assumption: start the reminders today at the specific time
            hour, minute = map(int, time_str.split(':'))
            start_dt = datetime.combine(start_date, datetime.min.time()).replace(hour=hour, minute=minute)
            event.add('dtstart', start_dt)
            event.add('dtend', start_dt + timedelta(minutes=15))
            
            # Recurrence Rule: daily until end_date
            event.add('rrule', {'freq': 'daily', 'until': end_date})
            
            desc = f"Medicine: {med.medicine_name}\n"
            if med.timings:
                desc += f"Instructions: {med.timings}\n"
            if pres.doctor_name:
                desc += f"Doctor: {pres.doctor_name}\n"
                
            event.add('description', desc)
            event['uid'] = str(uuid.uuid4()) + '@mediware'
            cal.add_component(event)

    ics_content = cal.to_ical()
    headers = {
        'Content-Disposition': f'attachment; filename="prescription_{pres_id}.ics"'
    }
    return Response(content=ics_content, media_type="text/calendar", headers=headers)

# ---------- 2. Health-Summary Endpoint ----------
@app.post("/health/summary")
def health_summary(session: Session = Depends(get_session)):
    """
    Analyze current health condition based on historical Lab Reports and Prescriptions.
    """
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

    # 3. Ask local LLM
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
        analysis_text = llm_generate(prompt)
        return {"analysis": analysis_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local LLM Analysis Failed: {e}")



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

# ---------- FEATURE 1: Medical Records RAG Upload ----------
@app.post("/records/upload")
async def upload_record(file: UploadFile = File(...)):
    """Upload a PDF or TXT medical record to the local knowledge base."""
    text_content = ""
    try:
        contents = await file.read()
        if file.filename.lower().endswith('.pdf'):
            reader = PdfReader(io.BytesIO(contents))
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        else:
            text_content = contents.decode("utf-8", errors="ignore")
            
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from file.")
            
        # Very simple chunking
        chunk_size = 1000
        overlap = 200
        chunks = []
        for i in range(0, len(text_content), chunk_size - overlap):
            chunk = text_content[i:i + chunk_size].strip()
            if len(chunk) > 100:
                chunks.append(chunk)
                
        if not chunks:
            raise HTTPException(status_code=400, detail="File content too short to index.")

        # Assign unique IDs
        doc_id = str(uuid.uuid4())
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": file.filename, "type": "medical_record"} for _ in chunks]
        
        # Add to ChromaDB
        rag_collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        
        return JSONResponse(content={"message": f"Successfully indexed '{file.filename}' into {len(chunks)} chunks."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {e}")
        
@app.post("/wellbeing-chat")
async def wellbeing_chat(req: ChatRequest, session: Session = Depends(get_session)):
    """
    Intelligent chatbot using local LLM.
    Proactively fetches context from DB before calling the model.
    """
    user_q = (req.question or "").strip()
    if not user_q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # --- Step 1: Proactive Context Fetching (Cheap DB Ops) ---
    # Lab Reports
    recent_reports = session.exec(select(HealthReport).order_by(HealthReport.created_at.desc()).limit(3)).all()
    lab_context = ""
    if recent_reports:
        for r in recent_reports:
            lab_context += f"\n--- Report ({r.created_at.strftime('%Y-%m-%d')}) ---\n"
            lab_context += f"Summary: {r.summary}\n"
            for t in r.test_results:
                lab_context += f"- {t.test_name}: {t.value} {t.unit}\n"
            
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

    # --- Step 2: Unstructured Context (Local RAG) ---
    rag_context = ""
    try:
        results = rag_collection.query(
            query_texts=[user_q],
            n_results=3
        )
        if results and results.get("documents") and results["documents"][0]:
            rag_context = ""
            for doc in results["documents"][0]:
                rag_context += f"- {doc}\n"
    except Exception as rag_e:
        print(f"⚠️ RAG Retrieval failed: {rag_e}")

    # --- Step 3: Unified Prompt (1 Call to local LLM) ---
    full_prompt = (
        "You are a helpful medical assistant. The user is asking a question.\n"
        "We have fetched some recent medical history for your context:\n\n"
        f"**Recent Lab Reports:**\n{lab_context or 'None'}\n\n"
        f"**Recent Prescriptions:**\n{med_context or 'None'}\n\n"
        f"**Historical Medical Documents (Knowledge Base):**\n{rag_context or 'None'}\n\n"
        "**Instructions:**\n"
        "1. **Trend Analysis**: If the user asks about a specific metric (e.g. 'How is my glucose?'), analyzing the trend is a priority. Compare values across recent reports. Do NOT just list the values.\n"
        "2. **Actionable Advice**: After stating the trend, provide a Specific Action Plan (Dietary, Lifestyle, or Medical).\n"
        "3. **Visuals**: If the user asks about a metric we have data for, append `[GRAPH: Metric Name]` at the very end of your response (use exact name from Recent Lab Reports).\n"
        "4. If the user asks a general health question, answer generally.\n"
        "5. Keep answers concise, helpful, and use **Markdown** for readability.\n\n"
        f"User Question: {user_q}"
    )

    try:
        answer_text = llm_generate(full_prompt)
        return {"answer": answer_text}
    except Exception as e:
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
    risk_percent: float
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
    return results
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
