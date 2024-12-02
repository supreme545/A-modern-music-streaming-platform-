document.addEventListener('DOMContentLoaded', () => {
    const playPauseBtn = document.getElementById('play-pause');
    const prevBtn = document.getElementById('prev');
    const nextBtn = document.getElementById('next');
    const volumeSlider = document.getElementById('volume');
    const progressBar = document.querySelector('.progress');
    const currentTimeSpan = document.getElementById('current-time');
    const durationSpan = document.getElementById('duration');

    let isPlaying = false;

    // Toggle play/pause
    playPauseBtn.addEventListener('click', () => {
        isPlaying = !isPlaying;
        if (isPlaying) {
            playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
            // Add actual play logic here
        } else {
            playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
            // Add actual pause logic here
        }
    });

    // Previous track
    prevBtn.addEventListener('click', () => {
        // Add previous track logic here
    });

    // Next track
    nextBtn.addEventListener('click', () => {
        // Add next track logic here
    });

    // Volume control
    volumeSlider.addEventListener('input', (e) => {
        const volume = e.target.value / 100;
        // Add volume control logic here
    });

    // Progress bar click handling
    document.querySelector('.progress-bar').addEventListener('click', (e) => {
        const progressBar = e.currentTarget;
        const clickPosition = e.offsetX;
        const progressBarWidth = progressBar.offsetWidth;
        const percentage = (clickPosition / progressBarWidth) * 100;
        
        document.querySelector('.progress').style.width = `${percentage}%`;
        // Add seek logic here
    });

    // Demo function to update progress (remove this in production)
    function demoProgress() {
        let width = 0;
        setInterval(() => {
            if (width >= 100) width = 0;
            width += 0.1;
            progressBar.style.width = `${width}%`;
            
            // Update time displays
            const currentSeconds = Math.floor((width / 100) * 300); // Assuming 5-minute song
            const totalSeconds = 300;
            
            currentTimeSpan.textContent = formatTime(currentSeconds);
            durationSpan.textContent = formatTime(totalSeconds);
        }, 100);
    }

    // Format time in MM:SS
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    // Start demo progress (remove in production)
    demoProgress();
});
