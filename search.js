let playerWindow = null;
let currentSong = null;

document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.querySelector('#search-form');
    const searchInput = document.querySelector('#search-input');
    const resultsContainer = document.querySelector('#results-container');
    const loadingSpinner = document.querySelector('.loading-spinner');

    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = searchInput.value.trim();
        
        if (!query) {
            showError('Please enter a search term');
            return;
        }

        try {
            loadingSpinner.style.display = 'block';
            resultsContainer.innerHTML = '';

            const response = await fetch(`/youtube/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) {
                throw new Error('Search failed');
            }

            const data = await response.json();
            displayResults(data.items);

        } catch (error) {
            console.error('Search error:', error);
            showError('Failed to perform search. Please try again.');
        } finally {
            loadingSpinner.style.display = 'none';
        }
    });
});

function displayResults(items) {
    const resultsContainer = document.querySelector('#results-container');
    resultsContainer.innerHTML = '';

    items.forEach(item => {
        const resultCard = createResultCard(item);
        resultsContainer.appendChild(resultCard);
    });
}

function createResultCard(item) {
    const card = document.createElement('div');
    card.className = 'result-card';
    
    const song = {
        videoId: item.id.videoId,
        title: item.snippet.title,
        artist: item.snippet.channelTitle,
        thumbnail: item.snippet.thumbnails.medium.url
    };

    card.innerHTML = `
        <img src="${song.thumbnail}" alt="${song.title}" class="song-thumbnail">
        <div class="song-info">
            <h3 class="song-title">${song.title}</h3>
            <p class="artist-name">${song.artist}</p>
        </div>
        <button class="play-btn">
            <i class="fas fa-play"></i>
        </button>
    `;

    card.querySelector('.play-btn').addEventListener('click', () => {
        playSong(song);
    });

    return card;
}

function playSong(song) {
    console.log('Playing song:', song);

    const modal = document.getElementById('player-modal');
    const playerFrame = document.getElementById('player-frame');
    const closeBtn = document.querySelector('.close-btn');

    if (!modal || !playerFrame || !closeBtn) {
        console.error('Modal elements not found:', {
            modal: !!modal,
            playerFrame: !!playerFrame,
            closeBtn: !!closeBtn
        });
        return;
    }

    console.log('Setting player frame src with videoId:', song.videoId);
    playerFrame.src = `player.html?videoId=${song.videoId}&title=${encodeURIComponent(song.title)}&thumbnail=${encodeURIComponent(song.thumbnail)}`;

    modal.style.display = 'block';
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);
    document.body.style.overflow = 'hidden'; // Prevent background scrolling

    closeBtn.onclick = () => {
        closePlayer();
    };

    modal.onclick = (e) => {
        if (e.target === modal) {
            closePlayer();
        }
    };

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closePlayer();
        }
    });
}

function closePlayer() {
    const modal = document.getElementById('player-modal');
    const playerFrame = document.getElementById('player-frame');

    if (!modal || !playerFrame) {
        console.error('Modal elements not found during close');
        return;
    }

    modal.classList.remove('show');
    document.body.style.overflow = ''; // Restore scrolling

    setTimeout(() => {
        modal.style.display = 'none';
        playerFrame.src = 'about:blank';
    }, 300);
}

function showError(message) {
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.textContent = message;
    
    document.body.appendChild(errorElement);
    
    setTimeout(() => {
        errorElement.remove();
    }, 3000);
}
