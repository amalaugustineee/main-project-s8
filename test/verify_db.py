from sqlmodel import Session, select
from database import engine
from models import HealthReport, TestResult, Prescription, PrescriptionMedicine

def main():
    with Session(engine) as session:
        reports = session.exec(select(HealthReport)).all()
        results = session.exec(select(TestResult)).all()
        prescriptions = session.exec(select(Prescription)).all()
        medicines = session.exec(select(PrescriptionMedicine)).all()
        
        counts = {
            "HealthReport": len(reports),
            "TestResult": len(results),
            "Prescription": len(prescriptions),
            "PrescriptionMedicine": len(medicines)
        }
        
        print("Table counts:", counts)
        
        if all(count == 0 for count in counts.values()):
            print("✅ Verification Successful: All tables are empty.")
        else:
            print("❌ Verification Failed: Some tables are not empty.")

if __name__ == "__main__":
    main()
