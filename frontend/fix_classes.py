import re

files = ["index.html", "prescription.html", "labreports.html", "diet.html", "trends.html"]

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    # We caused duplicate class="" tags.
    # Ex: class="flex ... group" class="text-..." 
    # We want to merge the second class into the first.
    def merge_classes(match):
        c1 = match.group(1)
        c2 = match.group(2)
        return f'class="{c1} {c2}"'

    content = re.sub(r'class="([^"]+)"\n\s*class="([^"]+)"', merge_classes, content)
    
    with open(f, 'w') as file:
        file.write(content)

print("Duplicate classes merged.")
