import os
from PIL import Image, ImageDraw, ImageFont

def create_image(filename, text):
    img = Image.new('RGB', (1000, 800), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except IOError:
        font = ImageFont.load_default()
    
    d.text((40, 40), text, fill=(0, 0, 0), font=font)
    img.save(filename)
    print(f"Saved {filename}")

lab_text = """
LABORATORY REPORT
--------------------------------
Patient Name: John Doe
Date: 2026-03-03

Test Name           Result       Unit       Reference Range
------------------------------------------------------------
LDL Cholesterol      165         mg/dL      < 100
Fasting Glucose      115         mg/dL      70 - 99
Hemoglobin A1C       6.8         %          < 5.7
Triglycerides        180         mg/dL      < 150
Vitamin D            18          ng/mL      30 - 100
"""

rx_text = """
PRESCRIPTION
--------------------------------
Dr. Sarah Smith, MD
City Central Hospital

Patient: John Doe
Date: 2026-03-03

Medicines:
1. Paracetamol 500mg
   Frequency: 1-0-1 (Morning and Night)
   Duration: 5 days
   Instructions: After Food

2. Amoxicillin 250mg
   Frequency: 1-1-1
   Duration: 7 days
   Instructions: After Food

3. Cetirizine 10mg
   Frequency: 0-0-1
   Duration: 3 days
   Instructions: Night, before bed
"""

create_image('sample_labreport.png', lab_text)
create_image('sample_prescription.png', rx_text)
