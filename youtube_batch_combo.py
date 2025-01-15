#!/usr/bin/env python3
import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict

# Imports for official YouTube Data API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If you want to do local scraping fallback
import subprocess

# If you want single-video quick check
try:
    from pytube import YouTube
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False

#########################
# Configure your API key or environment variable
#########################
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "<YOUR_API_KEY_HERE>")

DATA_DIR = Path("data")
ETAG_CACHE_FILE = DATA_DIR / "etag_cache.json"

def load_etag_cache() -> Dict[str, str]:
    """
    Load a JSON that maps channelId -> eTag.
    This helps us avoid re-fetching the entire video list if eTag is unchanged.
    """
    if not ETAG_CACHE_FILE.exists():
        return {}
    with open(ETAG_CACHE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_etag_cache(etag_map: Dict[str, str]):
    with open(ETAG_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(etag_map, f, indent=2)

def get_channel_uploads_via_api(channel_id: str) -> List[Dict]:
    """
    Example: use the YouTube Data API to get the channel's latest uploads with eTag-based caching.
    Return a list of video metadata (IDs, titles, etc.).
    """
    # Initialize client
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # Load cached eTags
    etag_map = load_etag_cache()
    prev_etag = etag_map.get(channel_id)

    # We can pass If-None-Match header to avoid usage if eTag hasn't changed
    # googleapiclient doesn't provide a direct param for that, so we can use _requestBuilder
    # or we can just do a manual request. For brevity, let's do a manual request using requests lib:
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        "?part=snippet"
        f"&channelId={channel_id}"
        "&maxResults=10"
        "&order=date"
        f"&key={YOUTUBE_API_KEY}"
    )
    headers = {}
    if prev_etag:
        headers["If-None-Match"] = prev_etag

    resp = requests.get(url, headers=headers)

    # If status code is 304, it means Nothing changed => no new data => we can skip
    if resp.status_code == 304:
        print(f"[API] Channel {channel_id}: eTag unchanged. No new data.")
        return []

    if resp.status_code != 200:
        print(f"[API] Error fetching channel info: {resp.status_code}, {resp.text}")
        return []

    # If OK, parse JSON
    data = resp.json()
    new_etag = resp.headers.get("ETag")
    if new_etag:
        etag_map[channel_id] = new_etag
        save_etag_cache(etag_map)

    items = data.get("items", [])
    # Build a minimal list of video metadata
    videos = []
    for item in items:
        vid_id = item.get("id", {}).get("videoId")
        if not vid_id:
            # Possibly a channel or playlist result
            continue
        snippet = item.get("snippet", {})
        videos.append({
            "videoId": vid_id,
            "title": snippet.get("title"),
            "publishedAt": snippet.get("publishedAt"),
            "description": snippet.get("description"),
            "channelTitle": snippet.get("channelTitle"),
        })
    return videos

def fallback_scrape_with_ytdlp(url: str, output_dir: str):
    """
    Use yt-dlp to get .info.json if you want more details or if the Data API is insufficient.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--ignore-errors",
        "--output", f"{output_dir}/%(title)s [%(id)s].%(ext)s",
        url
    ]
    print(f"[yt-dlp] Running: {' '.join(command)}")
    subprocess.run(command, check=False)

def demo_single_video_pytube(video_url: str):
    """
    If we just need a quick single-video check, we can use pytube (optional).
    """
    if not PYTUBE_AVAILABLE:
        print("pytube not installed. Skipping.")
        return
    yt = YouTube(video_url)
    print(f"[pytube] Title: {yt.title}")
    print(f"[pytube] Channel URL: {yt.channel_url}")
    print(f"[pytube] Channel ID: {yt.channel_id}")
    print(f"[pytube] Description: {yt.description[:80]}...")
    print(f"[pytube] Publish Date: {yt.publish_date}")

def example_usage():
    """
    Example usage to show how you might tie everything together in one function.
    1. For certain channels, use YouTube Data API with eTag to get new videos.
    2. For each new video, do fallback scraping with yt-dlp if desired.
    3. For single direct links, maybe do pytube or also yt-dlp.
    """
    # Suppose we have a channel
    channel_id = "UCtdKiwN9vw961uho0lre4_A"
    new_uploads = get_channel_uploads_via_api(channel_id)
    if not new_uploads:
        print("No new uploads or eTag unchanged. Skipping.")
    else:
        print(f"New uploads found for channel {channel_id}: {len(new_uploads)}")
        # Possibly run each through yt-dlp or store in DB
        for vid in new_uploads:
            video_url = f"https://www.youtube.com/watch?v={vid['videoId']}"
            fallback_scrape_with_ytdlp(video_url, "data/output")

    # Single link case
    single_vid = "https://www.youtube.com/watch?v=5wQ9nAlO12E"
    print(f"\nUsing pytube on single video: {single_vid}")
    demo_single_video_pytube(single_vid)
    print("Done example usage.")

if __name__ == "__main__":
    # For demonstration, just call example_usage
    example_usage()
