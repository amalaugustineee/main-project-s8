from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
import json

class HealthReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    summary: str
    raw_json: str  # Stores the full JSON analysis if needed for details

    # Relationship to test results
    test_results: List["TestResult"] = Relationship(back_populates="report")

class TestResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: Optional[int] = Field(default=None, foreign_key="healthreport.id")
    
    test_name: str = Field(index=True)
    value: float
    unit: str
    risk_percent: int
    risk_reason: Optional[str] = None
    timestamp: datetime = Field(index=True)

    report: Optional[HealthReport] = Relationship(back_populates="test_results")

class Prescription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    
    medicines: List["PrescriptionMedicine"] = Relationship(back_populates="prescription")

class PrescriptionMedicine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prescription_id: Optional[int] = Field(default=None, foreign_key="prescription.id")
    
    medicine_name: str
    frequency: Optional[str] = None
    duration: Optional[str] = None
    dosage: Optional[str] = None
    timings: Optional[str] = None # e.g. "After Food", "Before Breakfast"
    
    prescription: Optional[Prescription] = Relationship(back_populates="medicines")
