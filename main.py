#!/usr/bin/env python3
"""
main.py

- Loads YOUTUBE_API_KEY from .env via python-dotenv
- Uses the YouTube Data API for channel links with eTag caching (skip if no changes).
- Falls back to yt-dlp if needed or if channel ID can't be parsed or if user doesn't use the API.
- Uses pytube for single-video quick fetching, if installed.
- Then optionally merges all metadata into a single JSON or CSV via parse_metadata.

Directory structure:
  ./data/
    input_links.txt
    channel_etags.json   (ETag cache)
  ./helpers/
    parse_metadata.py
  ./
    main.py
    requirements.txt
"""

import os
import re
import json
import argparse
import requests
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# For .env loading:
from dotenv import load_dotenv

# For official YouTube Data API
try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

# For single-video usage
try:
    from pytube import YouTube
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False

#######################
# ENV/CONFIG LOADING
#######################
load_dotenv()  # load variables from .env
YT_API_KEYS = os.getenv("YOUTUBE_API_KEY", "")  # could be comma-separated

# For demonstration, we'll just pick the first key if comma-separated
if "," in YT_API_KEYS:
    # e.g. "AIza...,..."
    YT_API_KEY = YT_API_KEYS.split(",")[0].strip()
else:
    YT_API_KEY = YT_API_KEYS.strip()

DATA_DIR = Path("data")
ETAG_JSON_PATH = DATA_DIR / "channel_etags.json"

def load_etag_cache() -> Dict[str, str]:
    """
    Load a JSON that maps channelId-> eTag to skip re-fetching if nothing changed.
    """
    if not ETAG_JSON_PATH.exists():
        return {}
    try:
        with open(ETAG_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_etag_cache(etags: Dict[str, str]):
    ETAG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ETAG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(etags, f, indent=2)
    print(f"[INFO] eTag cache updated at {ETAG_JSON_PATH}")

########################################
# 1) HELPER: SINGLE VS MULTI DETECTION
########################################

def is_single_video(url: str) -> bool:
    """
    Heuristic for single vs. multi:
      - "watch?v=" or "youtu.be/" => single
      - "/channel/", "/@", "list=", or "/playlist" => multi (channel/playlist)
      - default => multi
    """
    if "watch?v=" in url or "youtu.be/" in url:
        return True
    # if handle or channel or playlist
    if "/channel/" in url or "/@" in url or "list=" in url or "/playlist" in url:
        return False
    return False  # fallback

########################################
# 2) YOUTUBE DATA API + eTag
########################################

def fetch_channel_videos_api(channel_id: str, etags: Dict[str, str]) -> List[Dict]:
    """
    Use the YouTube Data API to fetch up to 10 or 50 items from channelId, respecting eTag.
    We'll do a manual request via `requests` to handle If-None-Match easily.
    Return a list of dict items with minimal keys.
    """
    if not YT_API_KEY:
        print("[WARN] YT_API_KEY not set. Skipping Data API usage.")
        return []

    prev_etag = etags.get(channel_id)
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&channelId={channel_id}&maxResults=10&order=date&key={YT_API_KEY}"
    )
    headers = {}
    if prev_etag:
        headers["If-None-Match"] = prev_etag
    resp = requests.get(url, headers=headers)

    if resp.status_code == 304:
        print(f"[API] Channel {channel_id}: eTag unchanged => no new data.")
        return []

    if resp.status_code != 200:
        print(f"[API] Error {resp.status_code} => {resp.text}")
        return []

    data = resp.json()
    new_etag = resp.headers.get("ETag")
    if new_etag:
        etags[channel_id] = new_etag

    items = data.get("items", [])
    results = []
    for it in items:
        if it["id"]["kind"] == "youtube#video":
            snippet = it.get("snippet", {})
            results.append({
                "videoId": it["id"]["videoId"],
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "publishedAt": snippet.get("publishedAt"),
                "channelId": snippet.get("channelId"),
                "channelTitle": snippet.get("channelTitle"),
                "source": "YouTubeDataAPI",
            })
    return results

########################################
# 3) YT-DLP AND PYTUBE
########################################

def run_yt_dlp_metadata_only(url: str, output_dir: str):
    """
    Use yt-dlp to fetch metadata without downloading video,
    calling it via `python -m yt_dlp` for cross-platform reliability.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,     # e.g. python.exe
        "-m", "yt_dlp",
        "--skip-download",
        "--write-info-json",
        "--ignore-errors",
        "--output", f"{output_dir}/%(title)s [%(id)s].%(ext)s",
        url
    ]
    print(f"[yt-dlp] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def fetch_single_video_pytube(url: str) -> Dict[str, Any]:
    """
    If pytube is installed, try to fetch single-video metadata quickly.
    """
    if not PYTUBE_AVAILABLE:
        print("[INFO] pytube not installed. Skipping single-video approach.")
        return {}
    try:
        yt = YouTube(url)
        return {
            "videoId": yt.video_id,
            "title": yt.title,
            "channelId": yt.channel_id,
            "channelTitle": getattr(yt, "channel_name", ""),  # channel_name is sometimes None
            "publishedAt": str(yt.publish_date) if yt.publish_date else None,
            "viewCount": yt.views,
            "description": yt.description[:300],
            "source": "pytube",
        }
    except Exception as ex:
        print(f"[pytube] Error: {ex}")
        return {}

########################################
# 4) MAIN
########################################

def main():
    parser = argparse.ArgumentParser(description="Combo YouTube data tool (API+etags + yt-dlp + pytube).")
    parser.add_argument("--input-file", default="data/input_links.txt", help="File with YouTube links.")
    parser.add_argument("--output-dir", default="data/output", help="Where to put yt-dlp .info.json.")
    parser.add_argument("--dump-json", default="", help="If set, merges all found metadata to a single JSON.")
    parser.add_argument("--dump-csv", default="", help="If set, merges all found metadata to CSV via parse_metadata.")
    parser.add_argument("--use-api", action="store_true", help="Use Data API for channel links if channel ID is found.")
    args = parser.parse_args()

    # Prepare
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return

    links = [line.strip() for line in input_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Load eTag cache
    etag_map = load_etag_cache()

    all_items: List[Dict] = []

    for url in links:
        print(f"\nProcessing link: {url}")

        if is_single_video(url):
            # SINGLE => try pytube
            meta = fetch_single_video_pytube(url)
            if meta and meta.get("videoId"):
                meta["originalUrl"] = url
                all_items.append(meta)
            else:
                # fallback to yt-dlp
                run_yt_dlp_metadata_only(url, args.output_dir)
            continue

        # MULTI => channel/playlist => if user wants to use Data API and we can parse channel
        if args.use_api and YT_API_KEY:
            # Try to parse channel from /channel/<ID>
            match = re.search(r"/channel/([^/]+)", url)
            channel_id = None
            if match:
                channel_id = match.group(1)
            else:
                # If using handle, we might do an extra step to convert handle->channelId. 
                # But for brevity, skip or fallback to yt-dlp.
                pass

            if channel_id:
                new_videos = fetch_channel_videos_api(channel_id, etag_map)
                if new_videos:
                    all_items.extend(new_videos)
                else:
                    print(f"[INFO] No new or eTag unchanged for channel {channel_id}")
            else:
                # fallback
                run_yt_dlp_metadata_only(url, args.output_dir)
        else:
            # fallback
            run_yt_dlp_metadata_only(url, args.output_dir)

    # Save updated eTag
    save_etag_cache(etag_map)

    # If user wants a combined JSON, we also parse any .info.json from output_dir
    if args.dump_json or args.dump_csv:
        combined_data = list(all_items)

        # Gather .info.json from yt-dlp
        outdir = Path(args.output_dir)
        json_files = list(outdir.glob("*.info.json"))
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    md = json.load(f)
                    # Minimal parse
                    item = {
                        "videoId": md.get("id"),
                        "title": md.get("title"),
                        "channelId": md.get("channel_id"),
                        "channelTitle": md.get("channel"),
                        "duration": md.get("duration"),
                        "viewCount": md.get("view_count"),
                        "likeCount": md.get("like_count"),
                        "publishedAt": md.get("upload_date"),
                        "description": (md.get("description") or "")[:200],
                        "source": "yt-dlp",
                    }
                    combined_data.append(item)
            except:
                pass

        # Dump JSON
        if args.dump_json:
            Path(args.dump_json).parent.mkdir(parents=True, exist_ok=True)
            with open(args.dump_json, "w", encoding="utf-8") as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Merged JSON saved: {args.dump_json}")

        # Dump CSV
        if args.dump_csv:
            from helpers.parse_metadata import parse_and_save_info_to_csv
            Path(args.dump_csv).parent.mkdir(parents=True, exist_ok=True)
            parse_and_save_info_to_csv(combined_data, args.dump_csv)

    print("\nDone. Exiting.")


if __name__ == "__main__":
    main()
