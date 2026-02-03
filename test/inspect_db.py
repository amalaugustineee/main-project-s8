from sqlmodel import Session, select
from database import engine
from models import HealthReport, TestResult, Prescription
import pprint

def inspect():
    with Session(engine) as session:
        print("=== HEALTH REPORTS (RAW) ===")
        reports = session.exec(select(HealthReport)).all()
        if not reports:
            print("No health reports found.")
        for r in reports:
            data = r.model_dump()
            # Attach tests manually since model_dump might not include relationships by default
            data['test_results'] = [t.model_dump() for t in r.test_results]
            pprint.pprint(data)
            print("-" * 40)
        
        print("\n=== PRESCRIPTIONS (RAW) ===")
        prescriptions = session.exec(select(Prescription)).all()
        if not prescriptions:
            print("No prescriptions found.")
        for p in prescriptions:
            data = p.model_dump()
            data['medicines'] = [m.model_dump() for m in p.medicines]
            pprint.pprint(data)
            print("-" * 40)

if __name__ == "__main__":
    inspect()
