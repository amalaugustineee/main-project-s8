import os
from PIL import Image, ImageDraw, ImageFont

# Create a dummy image with a text table simulating a lab report
img = Image.new('RGB', (600, 300), color='white')
d = ImageDraw.Draw(img)

table_text = """
Test Name          | Result | Units  | Reference Range | Status
----------------------------------------------------------------
Glucose (Fasting)  | 95     | mg/dL  | 70-99           | Normal
Cholesterol        | 210    | mg/dL  | <200            | High
"""

d.text((10,10), table_text, fill=(0,0,0))
img.save('dummy_table.jpg')

print("Created dummy_table.jpg")
