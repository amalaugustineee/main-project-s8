import os
from PIL import Image

# Create a dummy lab report with table
img = Image.new('RGB', (400, 200), color='white')
img.save('dummy_lab.jpg')

print("Created dummy lab report. Run: ../env/bin/python hrisk.py dummy_lab.jpg")
