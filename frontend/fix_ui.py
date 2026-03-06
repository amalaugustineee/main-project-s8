import os
import re

files = ["index.html", "prescription.html", "labreports.html", "diet.html", "trends.html"]
base_dir = "/Users/anu/mediware main project s8/mediware/frontend"

for f in files:
    path = os.path.join(base_dir, f)
    with open(path, 'r') as file:
        content = file.read()
    
    # Remove CDATA
    content = content.replace('<![CDATA[', '')
    content = content.replace(']]>', '')

    # Fix sidebar navigation active state
    # We want to replace text-[#6D726D] hover:bg-[#E8E1D5] with bg-[#88A68B] text-white
    # but ONLY for the current file's nav link.
    
    # First, let's find all navigation links. They look like:
    # <a href="filename.html" 
    #    class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group text-[#6D726D] hover:bg-[#E8E1D5]">
    
    search_pattern = r'<a href="' + re.escape(f) + r'".*?class=".*?group text-\[#6D726D\] hover:bg-\[#E8E1D5\]".*?>'
    
    def replacer(match):
        text = match.group(0)
        # remove the inactive classes and add the active classes
        text = text.replace('text-[#6D726D] hover:bg-[#E8E1D5]', 'bg-[#88A68B] text-white shadow-md')
        return text

    content = re.sub(search_pattern, replacer, content, flags=re.DOTALL)
    
    # also replace the icon color inside the active link to white
    # the icon has: class="text-xl group-hover:text-[#4D6B53]" -> change to text-white
    
    # Let's just do a simpler replacement for the specific block.
    # To do this safely, we can just find the block that has href="f"
    
    blocks = re.split(r'(<a href="[^"]+".*?</a>)', content, flags=re.DOTALL)
    new_blocks = []
    for block in blocks:
        if block.startswith('<a href="' + f + '"'):
            # This is the active link block
            block = block.replace('text-[#6D726D] hover:bg-[#E8E1D5]', 'bg-[#88A68B] text-white shadow-md')
            block = block.replace('group-hover:text-[#4D6B53]', 'text-white group-hover:text-white')
        new_blocks.append(block)
    
    content = "".join(new_blocks)
            
    with open(path, 'w') as file:
        file.write(content)

print("Done fixing UI files")
