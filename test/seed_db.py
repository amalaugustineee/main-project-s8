from sqlmodel import Session, select
from database import engine
from models import HealthReport, TestResult
from datetime import datetime, timedelta

def main():
    with Session(engine) as session:
        # Check if already has data
        if session.exec(select(HealthReport)).first():
            print("Database already has data. Skipping seed.")
            return

        print("Seeding database with dummy reports...")
        
        # Report 1: 2 months ago
        r1 = HealthReport(
            summary="High blood sugar detected.",
            created_at=datetime.now() - timedelta(days=60),
            raw_json="{}"
        )
        session.add(r1)
        session.commit()
        session.refresh(r1)
        
        t1 = TestResult(
            report_id=r1.id,
            test_name="HbA1c",
            value=8.5,
            unit="%",
            risk_percent=80,
            risk_reason="High Risk",
            timestamp=r1.created_at
        )
        session.add(t1)

        # Report 2: 1 month ago
        r2 = HealthReport(
            summary="Blood sugar slightly improved but still high.",
            created_at=datetime.now() - timedelta(days=30),
            raw_json="{}"
        )
        session.add(r2)
        session.commit()
        session.refresh(r2)
        
        t2 = TestResult(
            report_id=r2.id,
            test_name="HbA1c",
            value=7.8,
            unit="%",
            risk_percent=65,
            risk_reason="Moderate Risk",
            timestamp=r2.created_at
        )
        session.add(t2)
        
        session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    main()
