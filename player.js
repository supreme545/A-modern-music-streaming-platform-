let player = {
    audio: new Audio(),
    currentTrack: null,
    isPlaying: false,
    progressInterval: null,

    init: function() {
        this.setupEventListeners();
    },
    
    setupEventListeners: function() {
        // Play/Pause button
        const playPauseBtn = document.querySelector('.play-pause-btn');
        playPauseBtn.addEventListener('click', () => {
            if (this.isPlaying) {
                this.pause();
            } else {
                this.play();
            }
        });

        // Previous and Next buttons
        document.querySelector('.previous-btn').addEventListener('click', () => {
            // Implement previous functionality
            console.log('Previous clicked');
        });

        document.querySelector('.next-btn').addEventListener('click', () => {
            // Implement next functionality
            console.log('Next clicked');
        });

        // Close button
        document.querySelector('.close-btn').addEventListener('click', () => {
            window.close();
        });
        
        // Progress bar
        const progressContainer = document.querySelector('.progress-container');
        progressContainer.addEventListener('click', (e) => {
            const clickPosition = (e.clientX - progressContainer.getBoundingClientRect().left) / progressContainer.offsetWidth;
            const timeToSeek = clickPosition * this.audio.duration;
            this.audio.currentTime = timeToSeek;
        });

        // Volume slider
        const volumeSlider = document.querySelector('.volume-slider');
        volumeSlider.addEventListener('click', (e) => {
            const rect = volumeSlider.getBoundingClientRect();
            const volumeLevel = (e.clientX - rect.left) / rect.width;
            this.audio.volume = Math.max(0, Math.min(1, volumeLevel));
            document.querySelector('.volume-progress').style.width = (volumeLevel * 100) + '%';
        });
        
        // Audio event listeners
        this.audio.addEventListener('timeupdate', () => {
            this.updateProgress();
        });
        
        this.audio.addEventListener('error', (e) => {
            console.error('Audio error:', e);
            this.showError('Error playing audio. Please try again.');
        });
    },
    
    loadTrack: async function(track) {
        try {
            console.log('Loading track:', track);
            
            // Show loading state
            this.showMessage('Loading track...');
            
            const response = await fetch(`/youtube/audio/${track.videoId}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `Server error: ${response.status}`);
            }
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (!data.audio_url) {
                throw new Error('No audio URL received');
            }
            
            // Clear any previous errors
            this.clearError();
            
            // Reset audio element before loading new track
            this.audio.pause();
            this.audio.currentTime = 0;
            this.audio.src = '';

            // Set the audio source and load it
            this.audio.src = data.audio_url;
            this.audio.load();
            
            // Update track info
            this.currentTrack = track;
            this.updateTrackInfo(track);
            
            // Show success message
            this.showMessage('Track loaded successfully');
            
        } catch (error) {
            console.error('Error loading track:', error);
            this.showError(`Failed to load track: ${error.message}`);
            throw error;
        }
    },
    
    updateProgress: function() {
        const progressBar = document.querySelector('.progress-bar');
        const currentTime = document.querySelector('.current-time');
        const totalTime = document.querySelector('.total-time');
        
        const percent = (this.audio.currentTime / this.audio.duration) * 100;
        progressBar.style.width = percent + '%';
        
        currentTime.textContent = this.formatTime(this.audio.currentTime);
        totalTime.textContent = this.formatTime(this.audio.duration);
    },
    
    formatTime: function(seconds) {
        if (isNaN(seconds)) return '0:00';
        const minutes = Math.floor(seconds / 60);
        seconds = Math.floor(seconds % 60);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    },
    
    play: function() {
        this.audio.play()
            .then(() => {
                this.isPlaying = true;
                document.querySelector('.play-pause-btn i').className = 'fas fa-pause';
            })
            .catch(error => {
                console.error('Playback error:', error);
                this.showError('Failed to start playback. Please try again.');
            });
    },
    
    pause: function() {
        this.audio.pause();
        this.isPlaying = false;
        document.querySelector('.play-pause-btn i').className = 'fas fa-play';
    },
    
    updateTrackInfo: function(track) {
        document.querySelector('.song-title').textContent = track.title;
        document.querySelector('.artist-name').textContent = track.artist;
        document.querySelector('.song-thumbnail').src = track.thumbnail;
    },

    showError: function(message) {
        const messageElement = document.getElementById('player-message') || this.createMessageElement();
        messageElement.textContent = message;
        messageElement.style.color = '#f44336';
        messageElement.style.display = 'block';
    },
    
    showMessage: function(message) {
        const messageElement = document.getElementById('player-message') || this.createMessageElement();
        messageElement.textContent = message;
        messageElement.style.color = '#4CAF50';
        messageElement.style.display = 'block';
        setTimeout(() => messageElement.style.display = 'none', 3000);
    },
    
    clearError: function() {
        const messageElement = document.getElementById('player-message');
        if (messageElement) {
            messageElement.style.display = 'none';
        }
    },
    
    createMessageElement: function() {
        const messageElement = document.createElement('div');
        messageElement.id = 'player-message';
        messageElement.style.position = 'fixed';
        messageElement.style.bottom = '20px';
        messageElement.style.left = '50%';
        messageElement.style.transform = 'translateX(-50%)';
        messageElement.style.padding = '10px 20px';
        messageElement.style.backgroundColor = '#333';
        messageElement.style.color = '#fff';
        messageElement.style.borderRadius = '5px';
        messageElement.style.zIndex = '1000';
        document.body.appendChild(messageElement);
        return messageElement;
    }
};

// Listen for messages from the parent window
window.addEventListener('message', async (event) => {
    try {
        const { type, song } = event.data;
        
        switch (type) {
            case 'PLAY_SONG':
                player.currentTrack = song;
                player.updateTrackInfo(song);
                await player.loadTrack(song);
                break;

            case 'STOP_PLAYBACK':
                player.pause();
                player.audio.currentTime = 0;
                break;

            default:
                console.log('Unknown message type:', type);
        }
    } catch (error) {
        console.error('Error handling message:', error);
        player.showError('Failed to process the request. Please try again.');
    }
});

// Update UI elements when track ends
player.audio.addEventListener('ended', () => {
    player.pause();
});

// Initialize player when document is ready
document.addEventListener('DOMContentLoaded', () => {
    player.init();

    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('videoId');
    const title = urlParams.get('title');
    const thumbnail = urlParams.get('thumbnail');

    // Set song info
    if (title) {
        document.querySelector('.song-title').textContent = title;
    }
    if (thumbnail) {
        document.querySelector('.song-thumbnail').src = thumbnail;
    }

    // Start playing if we have a video ID
    if (videoId) {
        player.loadTrack({ videoId, title, thumbnail });
    }
});
