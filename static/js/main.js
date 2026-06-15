// iNuCom Global Client Logic

// Pleasant chime sound generator using Web Audio API
function playNotificationSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        // Short premium double-beep chime
        const osc1 = audioCtx.createOscillator();
        const osc2 = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(659.25, audioCtx.currentTime); // E5
        osc1.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.12); // A5
        
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880, audioCtx.currentTime + 0.12);
        osc2.frequency.exponentialRampToValueAtTime(1318.51, audioCtx.currentTime + 0.25); // E6
        
        gain.gain.setValueAtTime(0.0, audioCtx.currentTime);
        gain.gain.linearRampToValueAtTime(0.25, audioCtx.currentTime + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        
        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc1.start();
        osc1.stop(audioCtx.currentTime + 0.13);
        
        osc2.start(audioCtx.currentTime + 0.12);
        osc2.stop(audioCtx.currentTime + 0.35);
    } catch (e) {
        console.warn("Audio Context playback blocked or unsupported:", e);
    }
}

// Background Polling for Notifications
let lastUnreadCount = null;

function pollNotifications() {
    fetch('/api/notifications/unread_count')
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Unauthorized or offline');
        })
        .then(data => {
            const currentCount = data.unread_count;
            if (lastUnreadCount !== null && currentCount > lastUnreadCount) {
                // Play notification sound
                playNotificationSound();
                
                // Update badge if elements exist
                const badgeElements = document.querySelectorAll('.bell-badge, .sidebar-menu-badge');
                badgeElements.forEach(el => {
                    el.textContent = currentCount;
                    el.style.display = currentCount > 0 ? 'inline-block' : 'none';
                });
                
                // Optional: show a mini toast or reload dropdown if open
                console.log("New notifications received!");
            }
            lastUnreadCount = currentCount;
        })
        .catch(err => {
            console.debug("Polling error (normal when logged out):", err);
        });
}

// Initialize Polling and Audio Reminders
document.addEventListener('DOMContentLoaded', () => {
    // 1. Initial count check
    fetch('/api/notifications/unread_count')
        .then(res => res.json())
        .then(data => {
            lastUnreadCount = data.unread_count;
            // Play a soft reminder on load if unread notifications exist
            if (lastUnreadCount > 0) {
                // We attempt to play, browser might block until a click.
                // We'll queue it on first user click if blocked.
                const playOnInteraction = () => {
                    playNotificationSound();
                    document.removeEventListener('click', playOnInteraction);
                };
                document.addEventListener('click', playOnInteraction);
            }
        }).catch(e => {});

    // Check for alerts / warning banners on page load and trigger chime
    const hasAlerts = document.querySelectorAll('.alert-error, .alert-success, .deadline-warning-banner, .late-warning').length > 0;
    if (hasAlerts) {
        const playAlertSound = () => {
            playNotificationSound();
            document.removeEventListener('click', playAlertSound);
        };
        document.addEventListener('click', playAlertSound);
    }

    // Start polling every 30 seconds
    setInterval(pollNotifications, 30000);
});

// Modal Logic for Calendar Day Edits
function openEditModal(dateStr, clockInStr, clockOutStr) {
    const modal = document.getElementById('attendanceEditModal');
    if (!modal) return;
    
    // Format times into HH:MM (strip seconds if present)
    const formatTime = (timeStr) => {
        if (!timeStr) return '';
        const parts = timeStr.split(':');
        if (parts.length >= 2) {
            return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
        }
        return timeStr;
    };

    document.getElementById('modal-edit-date').value = dateStr;
    document.getElementById('modal-edit-date-display').textContent = dateStr;
    document.getElementById('modal-edit-clock-in').value = formatTime(clockInStr);
    document.getElementById('modal-edit-clock-out').value = formatTime(clockOutStr);
    document.getElementById('modal-edit-reason').value = '';
    
    modal.classList.add('active');
}

function closeEditModal() {
    const modal = document.getElementById('attendanceEditModal');
    if (modal) {
        modal.classList.remove('active');
    }
}
