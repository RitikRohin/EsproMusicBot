import asyncio
import os
import re
from typing import Union, Optional, Dict, List, Tuple
import httpx
from pathlib import Path

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# Constants
API_BASE_URL = "https://youtubify.me"
API_KEY = "0122a3195bd84ac3ac90feaacbefd7a7"
ENABLE_STREAMING = True
MAX_DOWNLOAD_SIZE_MB = 48
STREAM_MODE_DURATION_THRESHOLD = 1200  # 20 minutes in seconds
DOWNLOAD_TIMEOUT = 600  # 10 minutes
REQUEST_TIMEOUT = 30  # 30 seconds
DOWNLOAD_CHUNK_SIZE = 1024 * 128  # 128KB chunks


def time_to_seconds(time_str: str) -> int:
    """Convert time string (MM:SS or HH:MM:SS) to seconds"""
    if not time_str or time_str.lower() == "none":
        return 0
    
    try:
        parts = time_str.split(":")
        if len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        else:  # SS
            return int(parts[0])
    except (ValueError, TypeError):
        return 0


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename"""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove multiple spaces and trim
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    # Limit length
    return sanitized[:100]


class YouTubeAPIError(Exception):
    """Custom exception for YouTube API errors"""
    pass


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self._client = None
        self._downloads_dir = Path("downloads")
        self._downloads_dir.mkdir(exist_ok=True)
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy client initialization"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=REQUEST_TIMEOUT,
                    write=10.0,
                    pool=10.0
                ),
                follow_redirects=True
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def _extract_video_id(self, link: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats"""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"v=([a-zA-Z0-9_-]{11})",
            r"/([a-zA-Z0-9_-]{11})(?:\?|$|/)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        return None
    
    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------
    async def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Make API request with error handling"""
        try:
            params["api_key"] = API_KEY
            url = f"{API_BASE_URL}/{endpoint}"
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.Timeout:
            raise YouTubeAPIError(f"Request to {endpoint} timed out")
        except httpx.HTTPStatusError as e:
            raise YouTubeAPIError(f"HTTP error {e.response.status_code} from {endpoint}")
        except Exception as e:
            raise YouTubeAPIError(f"Error accessing {endpoint}: {str(e)}")
    
    async def _search_first(self, query: str) -> Optional[Dict]:
        """
        Search for videos using the API
        Returns dict with {id, title, url} or None
        """
        try:
            data = await self._make_request("search", {"q": query})
            if not data or "id" not in data:
                return None
            
            return {
                "id": data.get("id"),
                "title": data.get("title") or data.get("id"),
                "url": data.get("url") or f"https://www.youtube.com/watch?v={data['id']}",
                "duration": data.get("duration")
            }
        except YouTubeAPIError:
            return None
    
    async def _info(self, video_id: str) -> Dict:
        """
        Get video metadata
        """
        try:
            data = await self._make_request("info", {"video_id": video_id})
            return data or {}
        except YouTubeAPIError:
            return {}
    
    async def _get_duration_seconds(self, video_id: str) -> int:
        """Get video duration in seconds"""
        try:
            info = await self._info(video_id)
            duration_str = info.get("duration")
            return time_to_seconds(duration_str) if duration_str else 0
        except:
            return 0
    
    # -------------------------------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        """Check if the link is a valid YouTube URL"""
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))
    
    async def url(self, message: Message) -> Optional[str]:
        """Extract URL from message entities"""
        messages_to_check = [message]
        if message.reply_to_message:
            messages_to_check.append(message.reply_to_message)
        
        for msg in messages_to_check:
            # Check text entities
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        text = msg.text or msg.caption or ""
                        return text[entity.offset:entity.offset + entity.length]
            
            # Check caption entities
            if msg.caption_entities:
                for entity in msg.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
                    elif entity.type == MessageEntityType.URL:
                        text = msg.caption or ""
                        return text[entity.offset:entity.offset + entity.length]
        
        return None
    
    # -------------------------------------------------------------------------
    # DETAILS
    # -------------------------------------------------------------------------
    async def details(self, link: str, videoid: Union[bool, str] = None) -> Tuple:
        """
        Returns: title, duration_min (str), duration_sec (int), thumbnail, vidid
        """
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        search = await self._search_first(link)
        if not search:
            return None, None, 0, None, None
        
        vidid = search["id"]
        info = await self._info(vidid)
        
        title = info.get("title") or search.get("title")
        duration_min = info.get("duration") or search.get("duration")
        duration_sec = time_to_seconds(duration_min) if duration_min else 0
        
        thumbnail = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
        
        return title, duration_min, duration_sec, thumbnail, vidid
    
    async def title(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        """Get video title"""
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        search = await self._search_first(link)
        if not search:
            return None
        
        info = await self._info(search["id"])
        return info.get("title") or search.get("title")
    
    async def duration(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        """Get video duration string"""
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        search = await self._search_first(link)
        if not search:
            return None
        
        info = await self._info(search["id"])
        return info.get("duration") or search.get("duration")
    
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        """Get video thumbnail URL"""
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        search = await self._search_first(link)
        if not search:
            return None
        
        vidid = search["id"]
        info = await self._info(vidid)
        return info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
    
    # -------------------------------------------------------------------------
    # TRACK
    # -------------------------------------------------------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Returns (track_details dict, vidid)
        """
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        search = await self._search_first(link)
        if not search:
            return None, None
        
        vidid = search["id"]
        info = await self._info(vidid)
        
        title = info.get("title") or search.get("title")
        duration_min = info.get("duration") or search.get("duration")
        thumb = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
        
        track_details = {
            "title": title,
            "link": search.get("url"),
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumb,
        }
        return track_details, vidid
    
    # -------------------------------------------------------------------------
    # SLIDER
    # -------------------------------------------------------------------------
    async def slider(self, link: str, query_type: str, videoid: Union[bool, str] = None) -> Tuple:
        """Get video details for slider"""
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        search = await self._search_first(link)
        if not search:
            return None, None, None, None
        
        vidid = search["id"]
        info = await self._info(vidid)
        
        title = info.get("title") or search.get("title")
        duration = info.get("duration") or search.get("duration")
        thumb = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
        
        return title, duration, thumb, vidid
    
    # -------------------------------------------------------------------------
    # STREAM / PLAYBACK URL BUILDERS
    # -------------------------------------------------------------------------
    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        """Get video stream URL"""
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        vid = self._extract_video_id(link)
        if not vid:
            return 0, ""
        
        stream_url = f"{API_BASE_URL}/download/video?video_id={vid}&mode=stream&max_res=720&api_key={API_KEY}"
        return 1, stream_url
    
    async def stream_url(self, link: str, videoid: bool = False, video: bool = False) -> str:
        """Get stream URL for audio or video"""
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        
        vid = self._extract_video_id(link)
        if not vid:
            return ""
        
        if video:
            return f"{API_BASE_URL}/download/video?video_id={vid}&max_res=720&api_key={API_KEY}"
        return f"{API_BASE_URL}/download/audio?video_id={vid}&api_key={API_KEY}"
    
    # -------------------------------------------------------------------------
    # PLAYLIST PARSE
    # -------------------------------------------------------------------------
    async def playlist(self, link: str, limit: int, user_id: int, videoid: bool = False) -> List[str]:
        """Get playlist video IDs"""
        if videoid:
            link = self.listbase + link
        link = link.split("&")[0]
        
        playlist_id = ""
        if "list=" in link:
            playlist_id = link.split("list=")[-1].split("&")[0]
        
        if not playlist_id:
            return []
        
        try:
            data = await self._make_request("playlist", {
                "playlist_id": playlist_id,
                "limit": limit
            })
            return data.get("video_ids", [])
        except YouTubeAPIError:
            return []
    
    # -------------------------------------------------------------------------
    # DOWNLOAD FUNCTION
    # -------------------------------------------------------------------------
    async def _download_file(self, url: str, params: Dict, extension: str) -> Optional[str]:
        """Download file from API"""
        try:
            # Get video info for filename
            video_id = params.get("video_id")
            info = await self._info(video_id) if video_id else {}
            title = info.get("title", video_id or "unknown")
            
            # Sanitize filename
            safe_title = sanitize_filename(title)
            filepath = self._downloads_dir / f"{safe_title}.{extension}"
            
            # Download file
            async with self.client.stream("GET", url, params=params, timeout=DOWNLOAD_TIMEOUT) as response:
                response.raise_for_status()
                
                with open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                
                # Check file size
                file_size_mb = filepath.stat().st_size / (1024 * 1024)
                if file_size_mb > MAX_DOWNLOAD_SIZE_MB:
                    filepath.unlink(missing_ok=True)
                    raise YouTubeAPIError(f"File too large ({file_size_mb:.1f}MB > {MAX_DOWNLOAD_SIZE_MB}MB)")
                
                return str(filepath)
        except Exception as e:
            raise YouTubeAPIError(f"Download failed: {str(e)}")
    
    async def download(
        self,
        link: str,
        mystic,
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: bool = False,
        title: bool = False,
    ) -> Union[str, Tuple[str, bool], None]:
        """
        Download video or audio
        Returns filepath or (filepath, True) for compatibility
        """
        if videoid:
            link = self.base + link
        
        vid = self._extract_video_id(link)
        if not vid:
            raise YouTubeAPIError("Could not extract video ID from link")
        
        # Check duration for streaming mode
        if ENABLE_STREAMING:
            duration_seconds = await self._get_duration_seconds(vid)
            if duration_seconds > STREAM_MODE_DURATION_THRESHOLD:
                return await self.stream_url(link, videoid, video)
        
        # Prepare download parameters
        download_params = {
            "video_id": vid,
            "mode": "download",
            "no_redirect": "1",
            "api_key": API_KEY,
        }
        
        # Choose download endpoint and file extension
        if video or songvideo:
            endpoint = "download/video"
            download_params["max_res"] = "720"
            extension = "mp4"
        else:
            endpoint = "download/audio"
            extension = "mp3"
        
        url = f"{API_BASE_URL}/{endpoint}"
        
        try:
            # Download file
            filepath = await self._download_file(url, download_params, extension)
            
            # Return format based on mode
            if songvideo or songaudio:
                return filepath
            else:
                return (filepath, True)
        except YouTubeAPIError as e:
            # Fallback to streaming if download fails
            if ENABLE_STREAMING:
                return await self.stream_url(link, videoid, video)
            raise
    
    async def cleanup_downloads(self, max_age_hours: int = 24):
        """Clean up old download files"""
        try:
            current_time = time.time()
            for file in self._downloads_dir.glob("*"):
                if file.is_file():
                    file_age = current_time - file.stat().st_mtime
                    if file_age > max_age_hours * 3600:
                        file.unlink()
        except Exception:
            pass
