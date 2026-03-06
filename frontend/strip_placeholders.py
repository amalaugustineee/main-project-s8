import re
import os

files = ["index.html", "prescription.html", "labreports.html", "diet.html", "trends.html"]

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    # Simple regex to replace Vue mustache bindings with static text
    # Dashboard stats
    content = content.replace('{{ medicationAdherence }}%', '95%')
    content = content.replace('{{ waterGlasses }}/5', '3/5')
    content = content.replace('{{ dailySteps }}/10000', '6,500/10000')
    content = content.replace('{{ sleepHours }}h • {{ sleepQuality }} rated', '7.5h • Good rated')
    content = content.replace('{{ medicationStreak }} Day Streak!', '14 Day Streak!')
    
    # Appointments
    content = content.replace('{{ doctorName }}', 'Dr. Sarah Mitchell')
    content = content.replace('{{ appointmentDate }}', 'Mar 15, 2:30 PM')
    content = content.replace('{{ labTestName }}', 'Annual Checkup')
    content = content.replace('{{ labTestDate }}', 'Mar 22, 10:00 AM')
    
    # Medicines
    content = content.replace('{{ medicine1Name }}', 'Metformin')
    content = content.replace('{{ medicine1Time }}', '12:00 PM')
    content = content.replace('{{ medicine2Name }}', 'Lisinopril')
    content = content.replace('{{ medicine2Time }}', '6:30 PM')
    content = content.replace('{{ medicine3Name }}', 'Vitamin D')
    content = content.replace('{{ medicine3Time }}', '8:00 PM')
    
    # Tips
    content = content.replace('{{ tip1 }}', 'A 20-minute walk in the morning boosts Vitamin D and mental clarity naturally.')
    content = content.replace('{{ tip2 }}', 'Drink water before meals to improve digestion and reduce overeating.')
    content = content.replace('{{ tip3 }}', 'Practice deep breathing for 5 minutes daily to reduce stress.')
    
    # Profile
    content = content.replace('{{ userName }}', 'Sarah')
    
    # Any other remaining {{ }} syntax that might crash Petite-Vue
    content = re.sub(r'\{\{.*?\}\}', '...', content)
    
    # Remove all :class binding which are useless now
    content = re.sub(r':class=".*?"', '', content)
    
    # Assign the correct active class statically to sidebars based on filename
    sidebar_mapping = {
        "index.html": 'href="index.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           ',
        "prescription.html": 'href="prescription.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           ',
        "labreports.html": 'href="labreports.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           ',
        "diet.html": 'href="diet.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           ',
        "trends.html": 'href="trends.html"\n           class="flex items-center gap-4 px-4 py-3 rounded-2xl transition-all group"\n           '
    }
    
    for filename, search_str in sidebar_mapping.items():
        if f == filename:
             content = content.replace(search_str, search_str[:-13] + ' bg-[#88A68B] text-white"') 
             
    with open(f, 'w') as file:
        file.write(content)

print("Done stripping placeholders")
