from sqlmodel import SQLModel
from database import engine
# Import models to ensure they are registered in metadata
from models import HealthReport, TestResult, Prescription, PrescriptionMedicine

def main():
    print("Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    print("Creating all tables...")
    SQLModel.metadata.create_all(engine)
    print("Database cleared successfully.")

if __name__ == "__main__":
    main()
