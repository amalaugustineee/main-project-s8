import re

files = ["index.html", "prescription.html", "labreports.html", "diet.html", "trends.html"]

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    # 1. Strip remaining inline v-scope=" {...} " bindings 
    content = re.sub(r'v-scope="\{.*?\}"', 'v-scope', content)
    
    # 2. Re-wire standard navigation classes to not use vue logic
    # Find things like :class="activeItem === 'dashboard' ? 'bg-[#88A68B] text-white' : 'text-[#6D726D] hover:bg-[#E8E1D5]'"
    content = re.sub(r':class="activeItem === \'.*?\' \?.*?\'(.*?)\'.*?\'(.*?)\'"', r'class="\2"', content)
    
    # Also fix iconify-icons dynamic class
    content = re.sub(r':class="activeItem === \'.*?\' \?.*?\'(.*?)\'.*?\'(.*?)\'"', '', content)
    
    # Special fix to re-activate the right tab
    if f == "index.html":
        content = content.replace('href="index.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           class="text-[#6D726D] hover:bg-[#E8E1D5]"', 'href="index.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group bg-[#88A68B] text-white"')
    if f == "prescription.html":
        content = content.replace('href="prescription.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           class="text-[#6D726D] hover:bg-[#E8E1D5]"', 'href="prescription.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group bg-[#88A68B] text-white"')
    if f == "labreports.html":
        content = content.replace('href="labreports.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           class="text-[#6D726D] hover:bg-[#E8E1D5]"', 'href="labreports.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group bg-[#88A68B] text-white"')
    if f == "diet.html":
        content = content.replace('href="diet.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           class="text-[#6D726D] hover:bg-[#E8E1D5]"', 'href="diet.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group bg-[#88A68B] text-white"')
    if f == "trends.html":
        content = content.replace('href="trends.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           class="text-[#6D726D] hover:bg-[#E8E1D5]"', 'href="trends.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group bg-[#88A68B] text-white"')
        
    with open(f, 'w') as file:
        file.write(content)

print("Vars and classes stripped")
