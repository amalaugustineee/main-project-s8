from sqlmodel import Session, select
from datetime import datetime, timedelta
from database import engine
from models import HealthReport, TestResult
import random

def seed_trends():
    with Session(engine) as session:
        # Check current data
        existing = session.exec(select(TestResult).where(TestResult.test_name == "Glucose (Fasting)")).all()
        count = len(existing)
        print(f"Current Glucose count: {count}")
        
        if count >= 3:
            print("Enough data exists.")
            return

        print("Seeding missing trend data...")
        dates = [
            datetime.now() - timedelta(days=60),
            datetime.now() - timedelta(days=30),
            datetime.now() - timedelta(days=10)
        ]
        
        for d in dates:
            # Create a dummy report
            report = HealthReport(created_at=d, summary="Auto-seeded historical report for trends.")
            session.add(report)
            session.commit()
            session.refresh(report)
            
            # Add Glucose
            tr = TestResult(
                report_id=report.id,
                test_name="Glucose (Fasting)",
                value=random.randint(80, 110),
                unit="mg/dL",
                risk_percent=random.randint(0, 20),
                risk_reason="Seeded data",
                timestamp=d
            )
            session.add(tr)
            
            # Add Cholesterol too
            tr2 = TestResult(
                report_id=report.id,
                test_name="Cholesterol, Total",
                value=random.randint(150, 220),
                unit="mg/dL",
                risk_percent=random.randint(0, 50),
                risk_reason="Seeded data",
                timestamp=d
            )
            session.add(tr2)

        session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    seed_trends()
