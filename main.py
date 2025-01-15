#!/usr/bin/env python3
"""
main.py

Combines:
  - YouTube Data API (for channel listing, ETag caching)
  - yt-dlp (for deeper multi-video scraping if needed)
  - pytube (for single-video quick metadata)

Directory structure:
  ./data/
    input_links.txt
    channel_etags.json   (ETag cache)
  ./helpers/
    parse_metadata.py
  ./
    main.py
    youtube_batch_combo.py
    requirements.txt
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

from typing import Optional, Dict, Any
import re

# Attempt to load optional libraries for each approach
try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

try:
    from pytube import YouTube
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False

########################################
# 1) HELPER: SINGLE VS MULTI DETECTION #
########################################

def is_single_video(url: str) -> bool:
    """
    Heuristic to decide if `url` is likely a single video vs. channel/playlist.
    We'll do a simple check:
      - If "watch?v=" or "youtu.be/" => single
      - If "/channel/" or "list=" or "playlist" => multi
      - If "/@something" => often a channel handle => treat as channel
    You can refine as needed.
    """
    # Single
    if ("watch?v=" in url) or ("youtu.be/" in url):
        return True

    # Multi
    if ("/channel/" in url) or ("list=" in url) or ("/playlist" in url):
        return False
    
    # Handles (e.g. https://www.youtube.com/@somechannel) we treat as multi (channel).
    if "/@" in url:
        return False

    # Default guess: multi
    return False


########################################
# 2) YOUTUBE DATA API LOGIC (with ETag)
########################################

def load_api_key() -> Optional[str]:
    """
    In a real environment, you might load from env var or a config file.
    For demonstration, we look for an environment variable YT_API_KEY.
    """
    return os.environ.get("YT_API_KEY", None)

def load_etags_cache(cache_path: str = "data/channel_etags.json") -> Dict[str, str]:
    """
    Load the known { channelId: eTag } from local JSON, if any.
    """
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_etags_cache(etags: Dict[str, str], cache_path: str = "data/channel_etags.json"):
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(etags, f, indent=2)
    print(f"ETag cache updated at {cache_path}")

def fetch_channel_videos_youtube_api(channel_id: str, api_key: str, etags_cache: Dict[str, str]) -> Dict[str, Any]:
    """
    Demonstration: Using YouTube Data API to get the channel's uploads or metadata,
    while leveraging ETag to skip if unchanged.

    If the ETag matches what's in our cache => we might skip or short-circuit.
    Here we do a search() for the channel's 50 latest videos (as an example).
    Real usage: you might do pagination or a playlistItems approach.

    Returns a dictionary:
      {
         'channelId': str,
         'etag_used': str,
         'etag_new': str or None,
         'videos': [ {videoId, title, ...}, ... ],
         'unchanged': True/False,
      }
    """
    if build is None:
        print("googleapiclient is not installed. Please install or skip.")
        return {"channelId": channel_id, "videos": [], "unchanged": False}

    youtube = build("youtube", "v3", developerKey=api_key)

    # Attempt to pass the known eTag to skip if not changed:
    # The python googleapiclient library does not provide a direct "If-None-Match" param,
    # so we must do a raw http call or a workaround. For demonstration, we’ll just do a normal request:
    # If you want advanced usage with eTag, you'd intercept the request's http headers or use a
    # lower-level approach with google-auth-httplib2. We'll do a minimal approach here.

    # Step 1) fetch the channel's "uploads" using 'search.list' or 'channels.list' + 'playlistItems.list'.
    # We'll do a simplified approach:
    resp = (
        youtube.search()
        .list(part="snippet", channelId=channel_id, maxResults=50, order="date")
        .execute()
    )

    new_etag = resp.get("etag")
    old_etag = etags_cache.get(channel_id)

    if new_etag and old_etag and new_etag == old_etag:
        # The data is unchanged
        return {
            "channelId": channel_id,
            "etag_used": old_etag,
            "etag_new": None,
            "videos": [],
            "unchanged": True,
        }

    # Otherwise parse out the items => store them
    videos_info = []
    items = resp.get("items", [])
    for it in items:
        if it["id"]["kind"] == "youtube#video":
            vid_id = it["id"]["videoId"]
            snippet = it["snippet"]
            videos_info.append({
                "videoId": vid_id,
                "publishedAt": snippet.get("publishedAt"),
                "channelId": snippet.get("channelId"),
                "title": snippet.get("title"),
                "description": snippet.get("description"),
            })

    # Update cache
    if new_etag:
        etags_cache[channel_id] = new_etag

    return {
        "channelId": channel_id,
        "etag_used": old_etag,
        "etag_new": new_etag,
        "videos": videos_info,
        "unchanged": False,
    }

########################################
# 3) YT-DLP AND PYTUBE LOGIC
########################################

def run_yt_dlp_metadata_only(url: str, output_dir: str):
    """
    Use yt-dlp to fetch metadata. 
    Creates .info.json in output_dir.
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
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, check=False)

def fetch_single_video_pytube(url: str) -> Dict[str, Any]:
    """
    If Pytube is installed, fetch single video metadata quickly.
    """
    if not PYTUBE_AVAILABLE:
        print("pytube not installed. Skipping single-video approach.")
        return {}
    yt = YouTube(url)
    data = {
        "videoId": yt.video_id,
        "title": yt.title,
        "channel_url": yt.channel_url,
        "channel_id": yt.channel_id,
        "publish_date": str(yt.publish_date) if yt.publish_date else None,
        "views": yt.views,
        "description": yt.description[:200],
    }
    return data


########################################
# 4) MAIN LOGIC
########################################

def main():
    parser = argparse.ArgumentParser(description="YouTube Combo (yt-dlp + pytube + Data API) with ETag caching.")
    parser.add_argument("--input", default="data/input_links.txt", help="File with one YouTube link per line.")
    parser.add_argument("--output-dir", default="data/output", help="Where to put .info.json from yt-dlp.")
    parser.add_argument("--use-api", action="store_true", help="Use YouTube Data API for channels if possible.")
    parser.add_argument("--etags-json", default="data/channel_etags.json", help="ETag cache file (for channel updates).")
    parser.add_argument("--dump-json", default="", help="If set, path to combined JSON of processed data.")
    args = parser.parse_args()

    # Prepare output dir
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # Possibly load an API key
    api_key = load_api_key()

    # Load ETag cache
    etags_cache = load_etags_cache(args.etags_json)

    # Read input lines
    with open(args.input, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    all_metadata = []  # we’ll store dict results here

    for url in links:
        print(f"\nProcessing link: {url}")

        if is_single_video(url):
            # Single => prefer pytube
            data = fetch_single_video_pytube(url)
            if data:
                data["source"] = "pytube"
                data["original_url"] = url
                all_metadata.append(data)
            else:
                # fallback: use yt-dlp
                run_yt_dlp_metadata_only(url, args.output_dir)
                # we can load the resulting .info.json if needed ...
            continue

        # Else => channel/playlist => if channel and user wants to use YouTube Data API:
        if args.use_api and api_key:
            # We try to parse out the channelId from URL if possible
            # e.g. https://www.youtube.com/channel/UCxxxxx => extract after /channel/
            # or handle https://www.youtube.com/@someHandle => call an extra step to find channelId
            # This is just a demonstration approach:
            channel_id = None
            match = re.search(r"/channel/([^/]+)", url)
            if match:
                channel_id = match.group(1)
            else:
                # Possibly it's a handle => we won't do it thoroughly, just skip for now
                pass

            if channel_id:
                resp = fetch_channel_videos_youtube_api(channel_id, api_key, etags_cache)
                if resp["unchanged"]:
                    print(f"Channel ID {channel_id} is unchanged (ETag). Skipping deeper fetch.")
                else:
                    for vid in resp["videos"]:
                        item = {
                            "videoId": vid["videoId"],
                            "title": vid["title"],
                            "description": vid["description"],
                            "channelId": channel_id,
                            "source": "YouTubeDataAPI"
                        }
                        all_metadata.append(item)
            else:
                # fallback to yt-dlp if we can’t parse channelId
                run_yt_dlp_metadata_only(url, args.output_dir)
        else:
            # fallback: just do yt-dlp
            run_yt_dlp_metadata_only(url, args.output_dir)

    # Save updated ETag cache
    save_etags_cache(etags_cache, args.etags_json)

    # If --dump-json is set, gather any .info.json from disk plus the Data API / pytube data
    # to produce a single consolidated JSON.
    if args.dump_json:
        # 1) load *.info.json from output_dir
        combined_data = list(all_metadata)
        info_files = list(Path(args.output_dir).glob("*.info.json"))
        for fpath in info_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    combined_data.append({
                        "videoId": metadata.get("id"),
                        "title": metadata.get("title"),
                        "channel_id": metadata.get("channel_id"),
                        "view_count": metadata.get("view_count"),
                        "like_count": metadata.get("like_count"),
                        "duration": metadata.get("duration"),
                        "webpage_url": metadata.get("webpage_url"),
                        "description": (metadata.get("description") or "")[:200],
                        "source": "yt-dlp",
                    })
            except:
                pass

        # Write final JSON
        out_path = Path(args.dump_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        print(f"Dumped consolidated results to {out_path}")

    print("\nAll done. Exiting.")


if __name__ == "__main__":
    main()
