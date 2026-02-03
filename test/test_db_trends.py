import sys
import os

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from typing import Generator

# Add the test directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, get_session
from models import HealthReport, TestResult

# Use a test database (in-memory) with StaticPool to share connection
sqlite_url = "sqlite:///:memory:"
engine = create_engine(
    sqlite_url, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_test_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_test_session

client = TestClient(app)

def test_save_report_and_trends():
    print("Tables in metadata:", SQLModel.metadata.tables.keys())
    create_db_and_tables()
    print("Tables created.")
    
    # 1. Save a sample report
    report_data = {
        "summary": "Patient has high cholesterol.",
        "tests": [
            {
                "name": "LDL Cholesterol",
                "current_value": "165 mg/dL",
                "risk_percent": 75,
                "risk_reason": "High"
            },
            {
                "name": "Vitamin D",
                "current_value": "20 ng/mL",
                "risk_percent": 40,
                "risk_reason": "Low"
            }
        ]
    }
    
    response = client.post("/reports/save", json={"analysis_result": report_data})
    if response.status_code != 200:
        print(f"Error saving report: {response.text}")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Report saved successfully"
    assert "report_id" in data
    
    # 2. Verify History
    response = client.get("/reports/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["summary"] == "Patient has high cholesterol."
    
    # 3. Verify Trends Parameters
    response = client.get("/trends")
    assert response.status_code == 200
    params = response.json()["parameters"]
    assert "LDL Cholesterol" in params
    assert "Vitamin D" in params
    
    # 4. Verify Trend Data for LDL
    response = client.get("/trends/LDL Cholesterol")
    assert response.status_code == 200
    trend_data = response.json()
    assert len(trend_data) == 1
    assert trend_data[0]["value"] == 165.0
    assert trend_data[0]["risk_percent"] == 75
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    # Manually run the test function
    try:
        test_save_report_and_trends()
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test error: {e}")
        sys.exit(1)
