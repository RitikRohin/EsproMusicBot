import asyncio
import os
import re
import logging
import json
from typing import Union, Optional, Dict, List, Tuple, Any
import httpx
from pathlib import Path
from datetime import datetime

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
API_BASE_URL = "https://youtubify.me"
API_KEY = "0122a3195bd84ac3ac90feaacbefd7a7"
ENABLE_STREAMING = True
MAX_DOWNLOAD_SIZE_MB = 48
STREAM_MODE_DURATION_THRESHOLD = 1200  # 20 minutes
DOWNLOAD_TIMEOUT = 600
REQUEST_TIMEOUT = 30
DOWNLOAD_CHUNK_SIZE = 1024 * 128

# Fallback APIs if primary fails (optional)
FALLBACK_APIS = [
    "https://youtube.fandom.dev",
    "https://ytapi.cyclic.app"
]


def time_to_seconds(time_str: str) -> int:
    """Convert time string to seconds"""
    if not time_str or time_str.lower() == "none":
        return 0
    
    try:
        parts = time_str.split(":")
        seconds = 0
        multipliers = [1, 60, 3600]  # seconds, minutes, hours
        
        # Reverse parts to handle variable length
        parts = parts[::-1]
        for i, part in enumerate(parts[:3]):
            seconds += int(part) * multipliers[i]
        
        return seconds
    except (ValueError, TypeError, IndexError):
        return 0


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem use"""
    # Remove invalid characters and truncate
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized[:100] or "unknown"


class YouTubeAPIError(Exception):
    """Custom exception for YouTube API errors"""
    pass


class QueryProcessingError(YouTubeAPIError):
    """Specific error for query processing failures"""
    pass


class YouTubeAPI:
    def __init__(self, use_fallback: bool = True):
        self.base_url = "https://www.youtube.com/watch?v="
        self.youtube_regex = r"(?:youtube\.com|youtu\.be)"
        self.playlist_base = "https://youtube.com/playlist?list="
        self.use_fallback = use_fallback
        self._client = None
        self._downloads_dir = Path("downloads")
        self._downloads_dir.mkdir(exist_ok=True)
        self.request_count = 0
        self.error_count = 0
        
        # Cache for frequently accessed data
        self._cache = {
            "info": {},
            "search": {}
        }
        self.cache_ttl = 300  # 5 minutes
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=REQUEST_TIMEOUT,
                    write=10.0,
                    pool=10.0
                ),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }
            )
        return self._client
    
    async def close(self):
        """Cleanup resources"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def _extract_video_id(self, link: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats"""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"v=([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
            r"/([a-zA-Z0-9_-]{11})(?:\?|$|/)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        
        # Check if it's already a video ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', link):
            return link
        
        return None
    
    def _extract_playlist_id(self, link: str) -> Optional[str]:
        """Extract playlist ID from URL"""
        patterns = [
            r"list=([a-zA-Z0-9_-]+)",
            r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        
        # Check if it's already a playlist ID
        if re.match(r'^[a-zA-Z0-9_-]+$', link) and len(link) > 11:
            return link
        
        return None
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key"""
        return f"{endpoint}:{json.dumps(params, sort_keys=True)}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get data from cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return data
            else:
                del self._cache[key]
        return None
    
    def _set_to_cache(self, key: str, data: Dict):
        """Store data in cache"""
        self._cache[key] = (data, time.time())
    
    async def _make_request(self, endpoint: str, params: Dict, base_url: str = None) -> Optional[Dict]:
        """Make API request with retry and fallback logic"""
        self.request_count += 1
        base_url = base_url or API_BASE_URL
        url = f"{base_url}/{endpoint}"
        params["api_key"] = API_KEY
        
        logger.debug(f"Making request to {url} with params: {params}")
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for error in response
            if isinstance(data, dict) and data.get("error"):
                logger.error(f"API returned error: {data.get('error')}")
                raise YouTubeAPIError(data.get("error"))
            
            logger.debug(f"Response from {url}: {data}")
            return data
            
        except httpx.Timeout:
            self.error_count += 1
            logger.error(f"Timeout accessing {url}")
            raise QueryProcessingError(f"Request timeout for {endpoint}")
            
        except httpx.HTTPStatusError as e:
            self.error_count += 1
            logger.error(f"HTTP error {e.response.status_code} from {url}")
            
            if e.response.status_code == 404:
                raise QueryProcessingError(f"Resource not found: {endpoint}")
            elif e.response.status_code == 429:
                raise QueryProcessingError("Rate limited. Please try again later.")
            elif e.response.status_code >= 500:
                raise QueryProcessingError("Server error. Please try again.")
            else:
                raise QueryProcessingError(f"HTTP error: {e.response.status_code}")
                
        except json.JSONDecodeError:
            self.error_count += 1
            logger.error(f"Invalid JSON response from {url}")
            raise QueryProcessingError("Invalid response from server")
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Unexpected error accessing {url}: {str(e)}")
            raise QueryProcessingError(f"Failed to process request: {str(e)}")
    
    async def _try_fallback(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Try fallback APIs if primary fails"""
        if not self.use_fallback:
            return None
        
        for fallback_url in FALLBACK_APIS:
            try:
                logger.info(f"Trying fallback API: {fallback_url}")
                return await self._make_request(endpoint, params, fallback_url)
            except Exception as e:
                logger.warning(f"Fallback {fallback_url} failed: {str(e)}")
                continue
        
        return None
    
    async def _search_first(self, query: str) -> Optional[Dict]:
        """Search for video with caching and fallback"""
        cache_key = self._get_cache_key("search", {"q": query})
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            # First try primary API
            data = await self._make_request("search", {"q": query})
            
            if not data or "id" not in data:
                # Try fallback
                data = await self._try_fallback("search", {"q": query})
                if not data:
                    return None
            
            result = {
                "id": data.get("id"),
                "title": data.get("title") or data.get("id", "Unknown"),
                "url": data.get("url") or f"https://www.youtube.com/watch?v={data['id']}",
                "duration": data.get("duration"),
                "thumbnail": data.get("thumbnail")
            }
            
            # Cache the result
            self._set_to_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return None
    
    async def _info(self, video_id: str) -> Dict:
        """Get video info with caching"""
        cache_key = self._get_cache_key("info", {"video_id": video_id})
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            data = await self._make_request("info", {"video_id": video_id})
            
            if not data:
                # Try fallback
                data = await self._try_fallback("info", {"video_id": video_id}) or {}
            
            # Cache the result
            self._set_to_cache(cache_key, data)
            return data
            
        except Exception as e:
            logger.error(f"Info failed for video {video_id}: {str(e)}")
            return {}
    
    async def _get_duration_seconds(self, video_id: str) -> int:
        """Get video duration in seconds"""
        info = await self._info(video_id)
        duration_str = info.get("duration")
        return time_to_seconds(duration_str) if duration_str else 0
    
    # -------------------------------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------------------------------
    
    async def validate_link(self, link: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate YouTube link and return (is_valid, video_id, playlist_id)
        """
        # Check if it's a video
        video_id = self._extract_video_id(link)
        if video_id:
            return True, video_id, None
        
        # Check if it's a playlist
        playlist_id = self._extract_playlist_id(link)
        if playlist_id:
            return True, None, playlist_id
        
        # Check if it matches YouTube URL pattern
        if re.search(self.youtube_regex, link):
            return True, None, None
        
        return False, None, None
    
    async def details(self, link: str, videoid: Union[bool, str] = None) -> Tuple:
        """
        Get video details
        Returns: (title, duration_str, duration_sec, thumbnail, video_id)
        """
        try:
            if videoid:
                link = self.base_url + str(link)
            
            # Clean the link
            link = link.split("&")[0].split("?")[0]
            
            search_result = await self._search_first(link)
            if not search_result:
                raise QueryProcessingError("No results found for the query")
            
            video_id = search_result["id"]
            info = await self._info(video_id)
            
            title = info.get("title") or search_result.get("title", "Unknown")
            duration_str = info.get("duration") or search_result.get("duration")
            duration_sec = time_to_seconds(duration_str) if duration_str else 0
            
            thumbnail = info.get("thumbnail") or search_result.get("thumbnail") or \
                       f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            
            return title, duration_str, duration_sec, thumbnail, video_id
            
        except Exception as e:
            logger.error(f"Failed to get details for {link}: {str(e)}")
            raise QueryProcessingError(f"Failed to get video details: {str(e)}")
    
    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Get track information for playback"""
        try:
            title, duration_str, duration_sec, thumbnail, video_id = await self.details(link, videoid)
            
            track_details = {
                "title": title,
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "vidid": video_id,
                "duration_min": duration_str,
                "duration_sec": duration_sec,
                "thumb": thumbnail,
                "query": link
            }
            
            return track_details, video_id
            
        except Exception as e:
            logger.error(f"Failed to get track for {link}: {str(e)}")
            return None, None
    
    async def download(
        self,
        link: str,
        mystic = None,
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: bool = False,
        title: bool = False,
    ) -> Union[str, Tuple[str, bool], None]:
        """
        Download video/audio with robust error handling
        """
        try:
            if videoid:
                link = self.base_url + str(link)
            
            # Get video ID
            video_id = self._extract_video_id(link)
            if not video_id:
                # Try to search for the query
                search_result = await self._search_first(link)
                if not search_result:
                    raise QueryProcessingError(f"No results found for: {link}")
                video_id = search_result["id"]
            
            # Check if we should stream instead of download
            if ENABLE_STREAMING:
                duration_sec = await self._get_duration_seconds(video_id)
                if duration_sec > STREAM_MODE_DURATION_THRESHOLD:
                    logger.info(f"Using stream mode for {video_id} (duration: {duration_sec}s)")
                    if video or songvideo:
                        return f"{API_BASE_URL}/download/video?video_id={video_id}&max_res=720&api_key={API_KEY}"
                    else:
                        return f"{API_BASE_URL}/download/audio?video_id={video_id}&api_key={API_KEY}"
            
            # Prepare download
            endpoint = "download/video" if (video or songvideo) else "download/audio"
            params = {
                "video_id": video_id,
                "mode": "download",
                "no_redirect": "1",
                "api_key": API_KEY,
            }
            
            if video or songvideo:
                params["max_res"] = "720"
            
            # Get video info for filename
            info = await self._info(video_id)
            video_title = info.get("title", video_id)
            safe_title = sanitize_filename(video_title)
            
            # Determine file extension
            extension = "mp4" if (video or songvideo) else "mp3"
            filename = f"{safe_title}.{extension}"
            filepath = self._downloads_dir / filename
            
            # Check if file already exists
            if filepath.exists():
                logger.info(f"File already exists: {filename}")
                if songvideo or songaudio:
                    return str(filepath)
                return (str(filepath), True)
            
            logger.info(f"Downloading {filename}...")
            
            # Download file
            url = f"{API_BASE_URL}/{endpoint}"
            async with self.client.stream("GET", url, params=params, timeout=DOWNLOAD_TIMEOUT) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress if mystic is provided
                        if mystic and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            # You can update progress here if mystic supports it
            
            # Verify download
            if not filepath.exists() or filepath.stat().st_size == 0:
                filepath.unlink(missing_ok=True)
                raise QueryProcessingError("Download failed: empty file")
            
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            if file_size_mb > MAX_DOWNLOAD_SIZE_MB:
                filepath.unlink(missing_ok=True)
                raise QueryProcessingError(f"File too large ({file_size_mb:.1f}MB)")
            
            logger.info(f"Download completed: {filename} ({file_size_mb:.1f}MB)")
            
            # Return based on mode
            if songvideo or songaudio:
                return str(filepath)
            return (str(filepath), True)
            
        except Exception as e:
            logger.error(f"Download failed for {link}: {str(e)}")
            
            # Provide user-friendly error message
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                raise QueryProcessingError("Download timeout. The video might be too long. Try streaming instead.")
            elif "not found" in error_msg.lower():
                raise QueryProcessingError("Video not found. It might be private or deleted.")
            elif "too large" in error_msg.lower():
                raise QueryProcessingError(f"Video is too large (max {MAX_DOWNLOAD_SIZE_MB}MB). Try streaming instead.")
            else:
                raise QueryProcessingError(f"Download failed: {error_msg}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            "requests": self.request_count,
            "errors": self.error_count,
            "success_rate": ((self.request_count - self.error_count) / self.request_count * 100 
                            if self.request_count > 0 else 100),
            "cache_size": len(self._cache),
            "downloads_dir": str(self._downloads_dir),
            "downloads_count": len(list(self._downloads_dir.glob("*"))) if self._downloads_dir.exists() else 0
        }
    
    async def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old download files"""
        try:
            current_time = time.time()
            deleted = 0
            
            for file in self._downloads_dir.glob("*"):
                if file.is_file():
                    file_age = current_time - file.stat().st_mtime
                    if file_age > max_age_hours * 3600:
                        try:
                            file.unlink()
                            deleted += 1
                            logger.info(f"Deleted old file: {file.name}")
    
