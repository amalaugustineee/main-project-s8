document.addEventListener('DOMContentLoaded', async () => {
    // Only run on dashboard
    if (!window.location.pathname.endsWith('index.html') && window.location.pathname !== '/' && !window.location.pathname.endsWith('frontend/')) {
        return;
    }

    const base = localStorage.getItem('apiBase') || 'http://127.0.0.1:8000';
    
    // 1. Fetch upcoming reminders
    try {
        const res = await fetch(`${base}/reminders/upcoming`);
        if (res.ok) {
            const reminders = await res.json();
            const container = document.querySelector('.space-y-2'); // Medicine list container
            
            if (container && reminders.length > 0) {
                container.innerHTML = '';
                reminders.slice(0, 3).forEach(med => {
                    container.innerHTML += `
                    <div class="bg-[#F5EFE6] rounded-2xl p-2.5 flex items-center gap-2">
                        <div class="w-8 h-8 bg-[#88A68B]/20 rounded-lg flex items-center justify-center flex-shrink-0">
                            <iconify-icon icon="lucide:pill" class="text-sm text-[#88A68B]"></iconify-icon>
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-xs font-medium text-[#4D6B53] truncate">${med.medicine}</p>
                            <p class="text-xs text-[#6D726D]">${med.time} - ${med.instruction}</p>
                        </div>
                    </div>`;
                });
            } else if (container) {
                 container.innerHTML = '<p class="text-xs text-[#6D726D]">No upcoming medicines.</p>';
            }
        }
    } catch(e) { console.error("Could not load reminders", e); }
    
});
