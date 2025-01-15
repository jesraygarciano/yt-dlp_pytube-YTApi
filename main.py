#!/usr/bin/env python3
"""
main.py

- Loads:
    - YOUTUBE_API_KEY from .env
    - PROXIES (comma-separated) from .env
- Reads "input_links.json" with { "urls": [...] } instead of a plain text file.
- Uses the YouTube Data API for channel links (with eTag caching),
- Falls back to yt-dlp if needed (channel ID not found or user not using API).
- Uses pytube for single-video quick fetching, if installed.
- Integrates random proxy usage for both requests & yt-dlp calls.

Directory structure:
  ./data/
    input_links.json   <-- { "urls": [... ] }
    etag_cache.json    <-- eTag cache for channels
  ./helpers/
    parse_metadata.py
  ./.env
  ./main.py
  ./requirements.txt
"""

import os
import re
import json
import sys
import random
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

# Attempt to load googleapiclient
try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

# Attempt to load pytube
try:
    from pytube import YouTube
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False

#######################
# 0) ENV/CONFIG LOADING
#######################
load_dotenv()  # load variables from .env

YT_API_KEYS = os.getenv("YOUTUBE_API_KEY", "")  # could be comma-separated
if "," in YT_API_KEYS:
    YT_API_KEY = YT_API_KEYS.split(",")[0].strip()
else:
    YT_API_KEY = YT_API_KEYS.strip()

# PROXIES env could be: "http://1.2.3.4:8888, http://user:pass@5.6.7.8:9999, ..."
PROXIES_RAW = os.getenv("PROXIES", "").strip()
PROXY_LIST: List[str] = []
if PROXIES_RAW:
    # split by comma, strip each
    PROXY_LIST = [p.strip() for p in PROXIES_RAW.split(",") if p.strip()]

DATA_DIR = Path("data")
ETAG_JSON_PATH = DATA_DIR / "etag_cache.json"

#######################
# PROXY HELPER
#######################
def get_random_proxy() -> Optional[str]:
    """
    Returns a random proxy string from PROXY_LIST, e.g. "http://1.2.3.4:8888".
    If PROXY_LIST is empty, returns None.
    """
    if not PROXY_LIST:
        return None
    return random.choice(PROXY_LIST)

def requests_with_proxy(url: str, **kwargs) -> requests.Response:
    """
    A small wrapper around requests.get, randomly picking a proxy if available.
    """
    proxy = get_random_proxy()
    if proxy:
        # We apply it to both http and https
        proxies = {"http": proxy, "https": proxy}
        return requests.get(url, proxies=proxies, **kwargs)
    else:
        return requests.get(url, **kwargs)

#######################
# ETag Cache Load/Save
#######################
def load_etag_cache() -> Dict[str, str]:
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

########################
# 1) SINGLE VS MULTI DETECTION
########################
def is_single_video(url: str) -> bool:
    """
    Heuristic for single vs. multi:
      - "watch?v=" or "youtu.be/" => single
      - "/channel/", "/@", "list=", or "/playlist" => multi
    """
    if "watch?v=" in url or "youtu.be/" in url:
        return True
    if "/channel/" in url or "/@" in url or "list=" in url or "/playlist" in url:
        return False
    return False

########################
# 2) YOUTUBE DATA API
########################
def fetch_channel_videos_api(channel_id: str, etags: Dict[str, str]) -> List[Dict]:
    """
    Use YouTube Data API to fetch up to 10 items from the channelId, respecting eTag.
    Manually pass "If-None-Match" and parse the 304 or 200 response.

    Returns a list of minimal dicts with 'videoId', 'title', etc.
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

    resp = requests_with_proxy(url, headers=headers)
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

########################
# 3) YT-DLP AND PYTUBE
########################
def run_yt_dlp_metadata_only(url: str, output_dir: str):
    """
    Calls yt-dlp as a subprocess:
      python -m yt_dlp --skip-download ...
    Includes proxy if available.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m", "yt_dlp",
        "--skip-download",
        "--write-info-json",
        "--ignore-errors",
        "--output", f"{output_dir}/%(title)s [%(id)s].%(ext)s",
    ]
    # If we have a random proxy, pass `--proxy=<proxy>`
    proxy = get_random_proxy()
    if proxy:
        cmd.append(f"--proxy={proxy}")

    cmd.append(url)
    print(f"[yt-dlp] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=False)

def fetch_single_video_pytube(url: str) -> Dict[str, Any]:
    """
    Quick single-video metadata fetch with pytube (if installed).
    Note that pytube doesn't have a built-in 'proxy rotation' mechanism.
    Some advanced usage can pass a proxy param to YouTube() but it's not fully stable.
    """
    if not PYTUBE_AVAILABLE:
        print("[INFO] pytube not installed. Skipping single-video approach.")
        return {}
    try:
        yt = YouTube(url)  # For advanced usage, YouTube(url, proxies=...) might be possible
        return {
            "videoId": yt.video_id,
            "title": yt.title,
            "channelId": yt.channel_id,
            "channelTitle": getattr(yt, "channel_name", ""),
            "publishedAt": str(yt.publish_date) if yt.publish_date else None,
            "viewCount": yt.views,
            "description": yt.description[:300],
            "source": "pytube",
        }
    except Exception as ex:
        print(f"[pytube] Error: {ex}")
        return {}

########################
# 4) MAIN
########################
def main():
    parser = argparse.ArgumentParser(description="Combo YouTube tool (API + yt-dlp + pytube) + Proxy rotation.")
    parser.add_argument("--input-json", default="data/input_links.json", help="JSON file with {urls: [...]}.")
    parser.add_argument("--output-dir", default="data/output", help="Output dir for .info.json from yt-dlp.")
    parser.add_argument("--dump-json", default="", help="Merge all metadata into single JSON file.")
    parser.add_argument("--dump-csv", default="", help="Merge all metadata into single CSV.")
    parser.add_argument("--use-api", action="store_true", help="Use the YouTube Data API for channels if possible.")
    args = parser.parse_args()

    # 1) Load input links from JSON
    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"[ERROR] JSON file not found: {input_path}")
        sys.exit(1)
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    urls = data.get("urls", [])
    if not isinstance(urls, list) or not urls:
        print(f"[ERROR] No 'urls' array found in {input_path}")
        sys.exit(1)

    # 2) Load eTag cache
    etag_map = load_etag_cache()

    all_items: List[Dict] = []

    # 3) Process each link
    for url in urls:
        print(f"\nProcessing link: {url}")
        if is_single_video(url):
            # single => try pytube
            item = fetch_single_video_pytube(url)
            if item and item.get("videoId"):
                item["originalUrl"] = url
                all_items.append(item)
            else:
                # fallback => yt-dlp
                run_yt_dlp_metadata_only(url, args.output_dir)
        else:
            # multi => channel or playlist
            if args.use_api and YT_API_KEY:
                # parse /channel/<id>
                m = re.search(r"/channel/([^/]+)", url)
                channel_id = m.group(1) if m else None

                if channel_id:
                    new_videos = fetch_channel_videos_api(channel_id, etag_map)
                    if new_videos:
                        all_items.extend(new_videos)
                    else:
                        print(f"[INFO] No new or ETag unchanged for channel {channel_id}")
                else:
                    # fallback => yt-dlp
                    run_yt_dlp_metadata_only(url, args.output_dir)
            else:
                run_yt_dlp_metadata_only(url, args.output_dir)

    # 4) Save updated eTag
    save_etag_cache(etag_map)

    # 5) Optionally consolidate all metadata into JSON/CSV
    if args.dump_json or args.dump_csv:
        # gather from memory + gather .info.json from yt-dlp
        combined_data = list(all_items)

        # parse .info.json from disk
        outdir = Path(args.output_dir)
        json_files = outdir.glob("*.info.json")
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    d = json.load(f)
                item = {
                    "videoId": d.get("id"),
                    "title": d.get("title"),
                    "channelId": d.get("channel_id"),
                    "channelTitle": d.get("channel"),
                    "duration": d.get("duration"),
                    "viewCount": d.get("view_count"),
                    "likeCount": d.get("like_count"),
                    "publishedAt": d.get("upload_date"),
                    "description": (d.get("description") or "")[:200],
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
