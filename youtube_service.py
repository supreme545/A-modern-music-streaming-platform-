import os
import time
import logging
from socket import timeout as SocketTimeoutError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import yt_dlp

class YouTubeService:
    def __init__(self, api_keys=None):
        self.logger = logging.getLogger(__name__)
        self.api_keys = api_keys or self._load_api_keys()
        self.current_key_index = 0
        self.youtube = None
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        self.initialize_service()

        # Set up logging
        logging.basicConfig(level=logging.INFO)

        # Get FFmpeg path
        ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe')
        
        # Configure yt-dlp options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'audio_cache/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'force_generic_extractor': False,
            'ffmpeg_location': ffmpeg_path
        }

    def _load_api_keys(self):
        """Load all available YouTube API keys from environment variables"""
        api_keys = []
        i = 1
        while True:
            key = os.getenv(f'YOUTUBE_API_KEY_{i}')
            if not key:
                break
            api_keys.append(key)
            i += 1
        
        if not api_keys:
            raise ValueError("No YouTube API keys found in environment variables")
        
        self.logger.info(f"Loaded {len(api_keys)} YouTube API keys")
        return api_keys

    def initialize_service(self):
        """Initialize the YouTube service with the current API key"""
        try:
            self.youtube = build('youtube', 'v3', 
                               developerKey=self.api_keys[self.current_key_index],
                               cache_discovery=False)
            self.logger.info(f"Initialized YouTube service with API key {self.current_key_index + 1}")
        except Exception as e:
            self.logger.error(f"Error initializing YouTube service: {str(e)}")
            raise

    def switch_api_key(self):
        """Switch to the next available API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.logger.info(f"Switching to API key {self.current_key_index + 1}")
        self.initialize_service()

    def handle_api_error(self, error):
        """Handle API errors and switch keys if necessary"""
        if isinstance(error, HttpError):
            if error.resp.status in [403, 429]:  # Quota exceeded or rate limit
                if self.current_key_index < len(self.api_keys) - 1:
                    self.logger.warning(f"API key {self.current_key_index + 1} quota exceeded, switching to next key")
                    self.switch_api_key()
                    return True
                else:
                    self.logger.error("All API keys have exceeded their quota")
                    return False
        return False

    def _throttle_request(self):
        """Ensure minimum time between API requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    def search_videos(self, query, retries=2, search_type='song'):
        """Search for YouTube videos with retry logic and API key rotation"""
        try:
            if not query:
                raise ValueError("Search query cannot be empty")

            self._throttle_request()

            # Modify query based on search type
            if search_type == 'song':
                search_query = f"{query} official audio"
                max_results = 25
            elif search_type == 'artist':
                search_query = f"{query} official music video"
                max_results = 30
            elif search_type == 'genre':
                search_query = f"best {query} official songs"
                max_results = 35
            else:
                search_query = f"{query} official music"
                max_results = 25

            try:
                search_response = self.youtube.search().list(
                    q=search_query,
                    part='snippet',
                    maxResults=max_results,
                    type='video',
                    videoCategoryId='10',  # Music category
                    fields='items(id(videoId),snippet(title,channelTitle,thumbnails))'
                ).execute()
            except (HttpError, SocketTimeoutError) as e:
                if isinstance(e, HttpError) and self.handle_api_error(e):
                    if retries > 0:
                        self.logger.info("Retrying search with new API key")
                        return self.search_videos(query, retries - 1, search_type)
                elif isinstance(e, SocketTimeoutError) and retries > 0:
                    self.logger.warning("Request timed out, retrying...")
                    time.sleep(1)
                    return self.search_videos(query, retries - 1, search_type)
                raise ValueError("Search failed. Please try again.")

            # Process search results
            if search_type == 'song':
                best_match = self._get_best_match(query, search_response.get('items', []))
                return [best_match] if best_match else []
            else:
                return self._filter_results(search_response.get('items', []), search_type)

        except Exception as e:
            self.logger.error(f"Error searching YouTube videos: {str(e)}")
            raise ValueError(f"Failed to search YouTube: {str(e)}")

    def _filter_results(self, items, search_type):
        """Filter and clean search results"""
        filtered_results = []
        seen_titles = set()
        seen_artists = set()

        for item in items:
            if not self._is_valid_result(item):
                continue

            title = item['snippet']['title']
            channel = item['snippet']['channelTitle']
            
            # Skip non-official content
            if not self._is_official_channel(channel):
                continue

            # Clean the title
            clean_title = self._clean_title(title)
            
            # For genre searches, ensure artist variety
            if search_type == 'genre':
                artist_lower = channel.lower()
                if artist_lower in seen_artists:
                    continue
                seen_artists.add(artist_lower)

            # Avoid duplicates
            if clean_title.lower() in seen_titles:
                continue
            seen_titles.add(clean_title.lower())

            filtered_results.append(item)
            if len(filtered_results) >= 10:  # Limit to 10 results
                break

        return filtered_results

    def _is_valid_result(self, item):
        """Check if a search result is valid"""
        return (
            'id' in item and 
            'videoId' in item['id'] and 
            'snippet' in item and 
            'title' in item['snippet'] and 
            'channelTitle' in item['snippet'] and 
            'thumbnails' in item['snippet']
        )

    def _get_best_match(self, query, search_results):
        """Get the best matching song from search results"""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Clean up query
        query_clean = ''.join(c for c in query_lower if c.isalnum() or c.isspace()).strip()
        
        best_match = None
        highest_score = -1
        
        for item in search_results:
            title = item['snippet']['title']
            channel = item['snippet']['channelTitle']
            
            # Parse title
            title_parts = self._parse_title(title, channel)
            song_title = title_parts['song']
            artist = title_parts['artist'] or channel
            
            # Skip if not from official channel
            if not self._is_official_channel(channel, artist):
                continue
                
            # Skip non-original versions
            skip_keywords = [
                'cover', 'karaoke', 'instrumental', 'remix', 'live', 'concert',
                'reaction', 'review', 'tutorial', 'lesson', 'how to', 'behind the scenes',
                'acoustic', 'piano version', 'guitar version', 'drum cover', 'bass cover',
                'extended', 'edit', 'mix', 'mashup', 'medley', 'tribute'
            ]
            if any(keyword in title.lower() for keyword in skip_keywords):
                continue
            
            # Clean up song title for comparison
            song_clean = ''.join(c for c in song_title.lower() if c.isalnum() or c.isspace()).strip()
            
            # Calculate match score
            score = 0
            
            # Exact match gets highest score
            if song_clean == query_clean:
                score = 100
            else:
                # Check word overlap
                song_words = set(song_clean.split())
                common_words = query_words & song_words
                score = len(common_words) * 10
                
                # Bonus points for word order matching
                if query_clean in song_clean or song_clean in query_clean:
                    score += 20
                
                # Bonus points for VEVO or official artist channel
                if 'vevo' in channel.lower():
                    score += 15
                elif 'official' in channel.lower():
                    score += 10
                    
                # Bonus points for "official audio" or "official music video"
                if 'official audio' in title.lower():
                    score += 5
                elif 'official music video' in title.lower():
                    score += 3
            
            # Update best match if score is higher
            if score > highest_score:
                highest_score = score
                best_match = item
        
        return best_match

    def _is_official_channel(self, channel_title, artist_name=None):
        """Check if the channel is likely an official music channel"""
        channel_lower = channel_title.lower()
        
        # List of known official music channel keywords
        official_keywords = [
            'official', 'vevo', 'records', 'music', 
            'entertainment', 'label', 'studio'
        ]
        
        # Check for VEVO channels
        if 'vevo' in channel_lower:
            return True
            
        # Check for verified music labels and studios
        if any(keyword in channel_lower for keyword in ['records', 'music', 'entertainment', 'label', 'studio']):
            return True
            
        # Check if channel name contains "official"
        if 'official' in channel_lower:
            return True
            
        # If we have an artist name, check if it matches the channel
        if artist_name:
            artist_lower = artist_name.lower()
            # Remove special characters and extra spaces
            artist_lower = ''.join(c for c in artist_lower if c.isalnum() or c.isspace()).strip()
            channel_clean = ''.join(c for c in channel_lower if c.isalnum() or c.isspace()).strip()
            
            # Check if artist name is in channel name
            if artist_lower in channel_clean:
                return True
            
            # Check if channel name is in artist name
            if channel_clean in artist_lower:
                return True
        
        return False
from googleapiclient.discovery import build
import yt_dlp
import os
import logging

class YouTubeService:
    def __init__(self, api_key):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Get FFmpeg path
        ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe')
        
        # Configure yt-dlp options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'audio_cache/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'force_generic_extractor': False,
            'ffmpeg_location': ffmpeg_path
        }

    def search_videos(self, query):
        """Search for YouTube videos"""
        try:
            if not query:
                raise ValueError("Search query cannot be empty")

            # Search for music videos only
            search_response = self.youtube.search().list(
                q=query + " song",  # Add "song" to get better music results
                part='snippet',
                maxResults=10,
                type='video',
                videoCategoryId='10',  # Music category
                fields='items(id(videoId),snippet(title,channelTitle,thumbnails))'
            ).execute()

            # Extract relevant information
            videos = []
            for item in search_response.get('items', []):
                if 'id' not in item or 'videoId' not in item['id']:
                    continue
                video_data = {
                    'id': {'videoId': item['id']['videoId']},
                    'snippet': {
                        'title': item['snippet']['title'],
                        'channelTitle': item['snippet']['channelTitle'],
                        'thumbnails': {
                            'medium': {
                                'url': item['snippet']['thumbnails']['medium']['url']
                            }
                        }
                    }
                }
                videos.append(video_data)

            self.logger.info(f"Found {len(videos)} videos for query: {query}")
            return videos

        except Exception as e:
            error_message = str(e)
            if "quota" in error_message.lower():
                raise ValueError(
                    "YouTube API quota exceeded. Please try again tomorrow or use a different API key. "
                    "To fix this:\n"
                    "1. Create a new project in Google Cloud Console\n"
                    "2. Enable YouTube Data API v3\n"
                    "3. Create new API credentials\n"
                    "4. Update the YOUTUBE_API_KEY in app.py"
                )
            self.logger.error(f"Error searching YouTube videos: {error_message}")
            raise ValueError(f"Failed to search YouTube: {error_message}")

    def get_audio(self, video_id):
        """Download and extract audio from YouTube video using yt-dlp"""
        try:
            # Create output path
            output_filename = f"{video_id}.mp3"
            output_path = os.path.join('audio_cache', output_filename)
            
            # Return cached version if exists
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.logger.info(f"Using cached audio for video {video_id}")
                return output_path

            self.logger.info(f"Downloading audio for video {video_id}")
            
            # Configure output template for this video
            self.ydl_opts['outtmpl'] = os.path.join('audio_cache', f'{video_id}.%(ext)s')
            
            # Download and extract audio
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                try:
                    # Get video info first
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    if info.get('is_live'):
                        raise Exception("Live streams are not supported")
                    
                    # Download and convert
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                    
                    # Verify the output file exists
                    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                        raise Exception("Failed to create audio file")
                    
                    self.logger.info(f"Successfully downloaded and converted video {video_id}")
                    return output_path
                    
                except Exception as e:
                    self.logger.error(f"Error downloading video {video_id}: {str(e)}")
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    raise
                    
        except Exception as e:
            self.logger.error(f"Error processing video {video_id}: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)
            raise Exception(f"Failed to process video: {str(e)}")

    def _clean_title(self, title):
        """Clean up video title"""
        replacements = [
            '(Official Video)', '(Official Music Video)', '(Official Audio)',
            '[Official Video]', '[Official Music Video]', '[Official Audio]',
            '(Audio)', '[Audio]', '(Lyrics)', '[Lyrics]',
            '(Official Lyric Video)', '[Official Lyric Video]',
            '(Official Visualizer)', '[Official Visualizer]',
            '(Official)', '[Official]', '(HD)', '[HD]',
            '(HQ)', '[HQ]', '(4K)', '[4K]'
        ]
        
        for text in replacements:
            title = title.replace(text, '')
        
        return title.strip()

    def _parse_title(self, title, channel):
        """Parse video title to extract song and artist information"""
        # Common separators in music titles
        separators = [' - ', ' – ', ' — ', ' | ', ' // ', ' ~ ']
        
        # Try to split by separators
        for separator in separators:
            if separator in title:
                parts = title.split(separator, 1)
                # Check if it's "Artist - Song" or "Song - Artist" format
                if len(parts) == 2:
                    artist, song = parts
                    # If channel name matches one of the parts, assume it's the artist
                    if channel.lower() in artist.lower():
                        return {'artist': artist.strip(), 'song': song.strip()}
                    elif channel.lower() in song.lower():
                        return {'artist': song.strip(), 'song': artist.strip()}
                    # Otherwise, assume "Artist - Song" format
                    return {'artist': artist.strip(), 'song': song.strip()}

        # If no separator found, try to extract from channel name
        if channel.lower() in title.lower():
            return {'artist': channel, 'song': title.replace(channel, '').strip()}
        
        # If all else fails, return cleaned title as song name
        return {'song': title, 'artist': None}

    def get_audio(self, video_id):
        """Download and extract audio from YouTube video using yt-dlp"""
        try:
            # Create output path
            output_filename = f"{video_id}.mp3"
            output_path = os.path.join('audio_cache', output_filename)
            
            # Return cached version if exists
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.logger.info(f"Using cached audio for video {video_id}")
                return output_path

            self.logger.info(f"Downloading audio for video {video_id}")
            
            # Configure output template for this video
            self.ydl_opts['outtmpl'] = os.path.join('audio_cache', f'{video_id}.%(ext)s')
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            if os.path.exists(output_path):
                self.logger.info(f"Successfully downloaded and converted audio for {video_id}")
                return output_path
            else:
                raise ValueError("Failed to find converted audio file")
                
        except Exception as e:
            self.logger.error(f"Error downloading audio: {str(e)}")
            raise ValueError(f"Failed to download audio: {str(e)}")
