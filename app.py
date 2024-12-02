from flask import Flask, request, jsonify, send_from_directory, send_file, Response
from flask_cors import CORS
import requests
import os
import yt_dlp
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_service import YouTubeService
import time

# Get the absolute path to the current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(CURRENT_DIR, 'ffmpeg', 'ffmpeg-master-latest-win64-gpl', 'bin', 'ffmpeg.exe')

# Add FFmpeg to environment PATH
os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(FFMPEG_PATH)

# Initialize Flask app with static folder configuration
app = Flask(__name__, 
    static_url_path='',
    static_folder=CURRENT_DIR)
CORS(app)

# Load environment variables
load_dotenv(override=True)  # Force reload environment variables

# YouTube API configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    raise ValueError("YouTube API key not found in environment variables. Please set YOUTUBE_API_KEY in the .env file.")

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Initialize YouTube service
youtube_service = None

def init_youtube_service():
    global youtube_service
    if youtube_service is not None:
        return True
        
    try:
        youtube_service = YouTubeService(YOUTUBE_API_KEY)
        app.logger.info(f"YouTube service initialized successfully with key {YOUTUBE_API_KEY[:10]}...")
        return True
    except Exception as e:
        app.logger.error(f"Failed to initialize YouTube service: {e}")
        return False

# Initialize YouTube service
if not init_youtube_service():
    app.logger.error("WARNING: YouTube service failed to initialize. Some features may not work.")

# Create necessary directories
AUDIO_CACHE_DIR = os.path.join(CURRENT_DIR, 'audio_cache')
if not os.path.exists(AUDIO_CACHE_DIR):
    os.makedirs(AUDIO_CACHE_DIR)

app.config['TEMP_FOLDER'] = AUDIO_CACHE_DIR

# API configuration
NAPSTER_API_KEY = "ZTk2YjY4MjMtMDAzYy00MTg4LWE2MjYtZDIzNjJmMmM0YTdm"
NAPSTER_API_URL = "https://api.napster.com/v2.2"

# Cache configuration
CACHE_DURATION = 3600  # 1 hour in seconds
CACHE_SIZE_LIMIT = 500 * 1024 * 1024  # 500MB in bytes

def get_cache_info():
    """Get information about cached files"""
    cache_size = 0
    cached_files = []
    
    for file in os.listdir(app.config['TEMP_FOLDER']):
        if file.endswith('.mp3'):
            file_path = os.path.join(app.config['TEMP_FOLDER'], file)
            file_stat = os.stat(file_path)
            cache_size += file_stat.st_size
            cached_files.append({
                'path': file_path,
                'size': file_stat.st_size,
                'accessed': file_stat.st_atime
            })
    
    return cache_size, cached_files

def cleanup_old_cache():
    """Remove old cached files if total size exceeds limit"""
    cache_size, cached_files = get_cache_info()
    
    if cache_size > CACHE_SIZE_LIMIT:
        # Sort by last access time, oldest first
        cached_files.sort(key=lambda x: x['accessed'])
        
        # Remove old files until we're under the limit
        for file_info in cached_files:
            try:
                os.remove(file_info['path'])
                cache_size -= file_info['size']
                print(f"Removed old cache file: {file_info['path']}")
                if cache_size <= CACHE_SIZE_LIMIT:
                    break
            except Exception as e:
                print(f"Error removing cache file: {e}")

ydl_opts = {
    'format': 'bestaudio/best',
    'nocheckcertificate': True,
    'no_warnings': True,
    'quiet': True,
    'extract_flat': False,
    'force_generic_extractor': False,
    'cookiefile': 'cookies.txt',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'extractor_args': {
        'youtube': {
            'skip_download': True,
            'nocheckcertificate': True,
            'no_warnings': True,
            'quiet': True
        }
    }
}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/search')
def search_page():
    return send_from_directory('.', 'search.html')

@app.route('/player')
def player_page():
    return send_from_directory('.', 'player.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(CURRENT_DIR, filename)

# Serve cached audio files
@app.route('/audio_cache/<path:filename>')
def serve_audio(filename):
    try:
        return send_from_directory(
            AUDIO_CACHE_DIR, 
            filename, 
            mimetype='audio/mpeg',
            as_attachment=False
        )
    except Exception as e:
        app.logger.error(f"Error serving audio file {filename}: {str(e)}")
        return jsonify({'error': 'Audio file not found'}), 404

# Napster API endpoints
@app.route('/search')
def search():
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'track,artist,album')
    
    try:
        # Search tracks
        track_response = requests.get(
            f"{NAPSTER_API_URL}/search/verbose",
            params={
                "apikey": NAPSTER_API_KEY,
                "query": query,
                "type": "track",
                "per_type_limit": 10
            }
        )
        track_response.raise_for_status()
        track_data = track_response.json()
        
        # Search artists
        artist_response = requests.get(
            f"{NAPSTER_API_URL}/search/verbose",
            params={
                "apikey": NAPSTER_API_KEY,
                "query": query,
                "type": "artist",
                "per_type_limit": 10
            }
        )
        artist_response.raise_for_status()
        artist_data = artist_response.json()
        
        # Search albums
        album_response = requests.get(
            f"{NAPSTER_API_URL}/search/verbose",
            params={
                "apikey": NAPSTER_API_KEY,
                "query": query,
                "type": "album",
                "per_type_limit": 10
            }
        )
        album_response.raise_for_status()
        album_data = album_response.json()

        # Extract data from response
        tracks = track_data.get("search", {}).get("data", {}).get("tracks", [])
        artists = artist_data.get("search", {}).get("data", {}).get("artists", [])
        albums = album_data.get("search", {}).get("data", {}).get("albums", [])

        # Process track data to include required fields
        processed_tracks = []
        for track in tracks:
            processed_tracks.append({
                "id": track.get("id"),
                "name": track.get("name"),
                "artistName": track.get("artistName"),
                "albumId": track.get("albumId"),
                "albumName": track.get("albumName"),
                "previewURL": track.get("previewURL")
            })

        # Process artist data
        processed_artists = []
        for artist in artists:
            processed_artists.append({
                "id": artist.get("id"),
                "name": artist.get("name"),
                "imageUrl": f"https://api.napster.com/imageserver/v2/artists/{artist.get('id')}/images/200x200.jpg"
            })

        # Process album data
        processed_albums = []
        for album in albums:
            processed_albums.append({
                "id": album.get("id"),
                "name": album.get("name"),
                "artistName": album.get("artistName"),
                "imageUrl": f"https://api.napster.com/imageserver/v2/albums/{album.get('id')}/images/200x200.jpg"
            })
        
        return jsonify({
            "tracks": processed_tracks,
            "artists": processed_artists,
            "albums": processed_albums
        })
    except requests.RequestException as e:
        print(f"Search error: {str(e)}")  # Debug logging
        return jsonify({"error": str(e)}), 500

@app.route('/track/<track_id>')
def get_track(track_id):
    try:
        response = requests.get(
            f"{NAPSTER_API_URL}/tracks/{track_id}",
            params={"apikey": NAPSTER_API_KEY}
        )
        response.raise_for_status()
        track_data = response.json()
        if 'tracks' in track_data and len(track_data['tracks']) > 0:
            return jsonify(track_data['tracks'][0])
        return jsonify({"error": "Track not found"}), 404
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/track/<track_id>/stream')
def get_track_stream(track_id):
    try:
        # Get track info first
        response = requests.get(
            f"{NAPSTER_API_URL}/tracks/{track_id}",
            params={"apikey": NAPSTER_API_KEY}
        )
        response.raise_for_status()
        track_data = response.json()
        
        if 'tracks' in track_data and len(track_data['tracks']) > 0:
            track = track_data['tracks'][0]
            # Get the streaming URL
            stream_response = requests.get(
                f"{NAPSTER_API_URL}/tracks/{track_id}/streams",
                params={"apikey": NAPSTER_API_KEY}
            )
            stream_response.raise_for_status()
            stream_data = stream_response.json()
            
            if 'streams' in stream_data and len(stream_data['streams']) > 0:
                return jsonify({
                    "streamUrl": stream_data['streams'][0]['url'],
                    "previewURL": track.get('previewURL')
                })
            
            # Fallback to preview URL if streaming is not available
            preview_url = track.get('previewURL')
            if preview_url:
                return jsonify({
                    "streamUrl": f"https://listen.hs.llnwd.net/g3/prvw/4/{preview_url}",
                    "previewURL": preview_url
                })
            
            return jsonify({"error": "No stream available"}), 404
        
        return jsonify({"error": "Track not found"}), 404
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trending')
def get_trending():
    try:
        # Get top tracks
        response = requests.get(
            f"{NAPSTER_API_URL}/tracks/top",
            params={
                "apikey": NAPSTER_API_KEY,
                "limit": 10
            }
        )
        response.raise_for_status()
        data = response.json()
        
        return jsonify({
            "tracks": data.get('tracks', [])
        })
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

# YouTube API endpoints
@app.route('/youtube/search')
def youtube_search():
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'error': 'No search query provided'}), 400

        # Perform YouTube search
        search_response = youtube.search().list(
            q=query,
            part='snippet',
            maxResults=10,
            type='video',
            videoCategoryId='10'  # Music category
        ).execute()

        return jsonify(search_response)

    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({'error': 'Failed to perform search'}), 500

@app.route('/youtube/audio/<video_id>')
def get_audio_url(video_id):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if 'url' in info:
                return jsonify({'audio_url': info['url']})
            elif 'formats' in info and len(info['formats']) > 0:
                return jsonify({'audio_url': info['formats'][0]['url']})
            else:
                return jsonify({'error': 'No audio URL found'}), 404
    except Exception as e:
        print(f"Error extracting audio URL: {str(e)}")
        return jsonify({'error': f'Failed to get audio URL: {str(e)}'}), 500

@app.route('/prepare_audio/<video_id>', methods=['POST'])
def prepare_audio(video_id):
    """Pre-download and convert audio in the background"""
    try:
        print(f"Pre-downloading audio for video ID: {video_id}")
        
        # Create a unique filename for this video
        filename = f"temp_{video_id}.mp3"
        temp_path = os.path.join(app.config['TEMP_FOLDER'], filename)
        
        # If file already exists and is recent, return success
        if os.path.exists(temp_path):
            file_age = time.time() - os.path.getmtime(temp_path)
            if file_age < CACHE_DURATION:
                return jsonify({'status': 'ready', 'message': 'Audio already cached'})
        
        # Clean up any existing temporary files
        cleanup_temp_files(video_id)
        
        # Clean up old cache if needed
        cleanup_old_cache()

        # Base yt-dlp options
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': False,
            'extract_flat': True,
            'ffmpeg_location': os.path.dirname(FFMPEG_PATH),
            'concurrent_fragments': 5,  # Download multiple fragments concurrently
            'buffersize': 4096,  # Increased buffer size
            'http_chunk_size': 20971520,  # 20MB chunks
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'overwrites': True
        }

        # First try to get the best pre-converted format
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            format_id, ext = get_best_audio_format(ydl, video_id)
            
            if format_id:
                print(f"Found optimal format: {format_id} ({ext})")
                ydl_opts.update({
                    'format': format_id,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',  # Lower quality for faster conversion
                    }],
                    'postprocessor_args': {
                        'FFmpegExtractAudio': [
                            '-threads', '4',  # Use 4 threads
                            '-preset', 'ultrafast',  # Fastest conversion
                            '-movflags', '+faststart',
                            '-ac', '2',  # Force stereo
                            '-ar', '44100',  # Standard sample rate
                            '-y'  # Overwrite files
                        ]
                    }
                })
                
                # Download with optimized settings
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                
                return jsonify({'status': 'success', 'message': 'Audio prepared successfully'})
            else:
                return jsonify({'status': 'error', 'message': 'No suitable audio format found'}), 400
                
    except Exception as e:
        print(f"Error preparing audio: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_audio/<video_id>')
def get_audio(video_id):
    try:
        print(f"Received request for video ID: {video_id}")
        
        # Create a unique filename for this video
        filename = f"temp_{video_id}.mp3"
        temp_path = os.path.join(app.config['TEMP_FOLDER'], filename)
        
        if not os.path.exists(temp_path):
            # If file doesn't exist, try to prepare it quickly
            prepare_audio(video_id)
            
            if not os.path.exists(temp_path):
                return jsonify({'error': 'Failed to prepare audio'}), 500
        
        # Stream the file in chunks for better performance
        def generate():
            with open(temp_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    yield chunk
        
        return Response(
            generate(),
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        print(f"Error serving audio: {str(e)}")
        return jsonify({
            'error': f'Server error: {str(e)}'
        }), 500

def cleanup_temp_files(video_id):
    """Clean up any temporary files that might be locked"""
    base_path = os.path.join(app.config['TEMP_FOLDER'], f'temp_{video_id}')
    files_to_cleanup = [
        f"{base_path}.part",
        f"{base_path}.mp3",
        f"{base_path}.webm",
        f"{base_path}.m4a"
    ]
    
    for file_path in files_to_cleanup:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Cleaned up: {file_path}")
        except Exception as e:
            print(f"Failed to cleanup {file_path}: {str(e)}")

def get_best_audio_format(ydl, video_id):
    """Get the best available pre-converted audio format to minimize processing"""
    try:
        info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
        formats = info.get('formats', [])
        
        # First priority: pre-converted m4a audio (usually the fastest)
        m4a_formats = [f for f in formats if f.get('ext') == 'm4a' and f.get('acodec') != 'none']
        if m4a_formats:
            best_m4a = max(m4a_formats, key=lambda f: f.get('abr', 0))
            return best_m4a.get('format_id'), 'm4a'
            
        # Second priority: pre-converted mp3
        mp3_formats = [f for f in formats if f.get('ext') == 'mp3' and f.get('acodec') != 'none']
        if mp3_formats:
            best_mp3 = max(mp3_formats, key=lambda f: f.get('abr', 0))
            return best_mp3.get('format_id'), 'mp3'
            
        # Fallback: best audio format
        audio_formats = [f for f in formats if f.get('acodec') != 'none']
        if audio_formats:
            best_audio = max(audio_formats, key=lambda f: f.get('abr', 0))
            return best_audio.get('format_id'), best_audio.get('ext')
            
        return None, None
    except Exception as e:
        print(f"Error getting format info: {e}")
        return None, None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
