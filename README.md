# 🏥 Mediware — AI-Powered Medical Intelligence Platform

Mediware is a locally-hosted, AI-powered health management web app. It analyzes prescriptions and lab reports, generates personalized diet plans, tracks health trends over time, and provides an intelligent wellbeing chatbot — all powered by a local LLM (Ollama/LLaMA) with no cloud dependency.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📋 **Prescription Analyzer** | Upload a prescription image/PDF → extracts medicines, dosage, frequency |
| 🔬 **Lab Report Analyzer** | Upload a lab report → health risk assessment with % risk per test |
| 🥗 **Diet Plan Generator** | Generates personalized meal plans based on your health history |
| 📈 **Health Trends** | Tracks lab values over time with interactive charts |
| 🤖 **Wellbeing Chatbot** | Ask health questions — contextual answers using your medical history |
| 💊 **Medication Reminders** | Upcoming dose scheduler based on prescription frequency |
| 📅 **Calendar Export** | Export medication schedule as `.ics` for Google/Apple Calendar |
| ⚠️ **Drug Interaction Checker** | Detects interactions between new and existing prescriptions |
| 📁 **RAG Knowledge Base** | Upload medical documents (PDF/TXT) for the chatbot to reference |

---

## 🛠️ Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite via SQLModel
- **Vector DB**: ChromaDB (for RAG / document search)
- **AI / LLM**: Ollama with `llama3.2` (runs fully locally)
- **Embeddings**: `nomic-embed-text` via Ollama
- **OCR**: Tesseract + Pytesseract
- **Frontend**: Vanilla HTML, CSS, JavaScript

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running
- Tesseract OCR installed (`brew install tesseract` on macOS)

### 1. Clone the repo

```bash
git clone https://github.com/amalaugustineee/main-project-s8.git
cd main-project-s8
```

### 2. Set up Python environment

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 3. Pull required Ollama models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
# Add any API keys here if needed (currently runs fully locally)
```

### 5. Run the app

**Start Ollama:**
```bash
ollama serve
```

**Start the backend:**
```bash
cd test
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Start the frontend:**
```bash
cd frontend
python3 -m http.server 3000
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📁 Project Structure

```
mediware/
├── frontend/           # HTML, CSS, JS frontend
│   ├── index.html      # Dashboard
│   ├── prescription.html
│   ├── labreports.html
│   ├── trends.html
│   ├── diet.html
│   ├── summary.html
│   ├── healthrisk.html
│   ├── app.js          # Main frontend logic
│   ├── dashboard_integration.js
│   └── styles.css
├── test/               # Backend
│   ├── app.py          # FastAPI application (main entry point)
│   ├── llm_local.py    # Ollama LLM helper
│   ├── hrisk.py        # Lab report risk analysis
│   ├── prescription_read.py  # Prescription OCR + extraction
│   ├── dietplan.py     # Diet plan generation
│   ├── models.py       # SQLModel DB models
│   ├── database.py     # DB engine setup
│   └── database.db     # SQLite database
├── env/                # Python virtual environment
├── requirements.txt
└── .env
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/prescription` | Analyze a prescription image/PDF (returns job ID) |
| `GET` | `/prescription/history` | Get all past prescriptions |
| `GET` | `/prescription/{id}/calendar` | Download .ics medication calendar |
| `POST` | `/healthrisk` | Analyze a lab report (returns job ID) |
| `GET` | `/jobs/{job_id}` | Poll background job status |
| `POST` | `/reports/save` | Save a health report to DB |
| `GET` | `/reports/history` | Get all past health reports |
| `GET` | `/trends` | Get available trend parameters |
| `GET` | `/trends/{test_name}` | Get historical data for a test |
| `POST` | `/generate-diet-plan` | Generate a personalized diet plan |
| `POST` | `/wellbeing-chat` | Chat with the health AI assistant |
| `POST` | `/records/upload` | Upload documents to RAG knowledge base |
| `POST` | `/health/summary` | Generate an AI health summary |
| `GET` | `/reminders/upcoming` | Get upcoming medication reminders |

Full interactive docs available at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🏗️ Clearing the Database

To wipe all data and start fresh:

```bash
cd test
python clear_db.py
```

---

## 📝 License

This project is for academic/demo purposes.
