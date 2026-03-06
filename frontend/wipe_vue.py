import os
import re

files = ["index.html", "prescription.html", "labreports.html", "diet.html", "trends.html"]
pattern = re.compile(r'v-scope="{\s*\.\.\.\{.*?\},\s*\$emit\(\)\s*\{\}\s*}"', re.DOTALL)

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    new_content = pattern.sub('v-scope', content)
    
    with open(f, 'w') as file:
        file.write(new_content)
print("Done wiping vue scopes!")
