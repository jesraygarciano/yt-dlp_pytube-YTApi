import csv
import json
from typing import List, Dict

def parse_and_save_info_to_csv(info_list: List[Dict], out_csv: str):
    """
    Takes a list of video/item dictionaries and writes them to a CSV.
    Each dict might come from YouTube Data API, yt-dlp, or Pytube.
    """
    fieldnames = [
        "videoId",
        "title",
        "channelId",
        "channelTitle",
        "duration",
        "viewCount",
        "likeCount",
        "publishedAt",
        "description",
        "source",
    ]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in info_list:
            row = {
                "videoId": item.get("videoId", ""),
                "title": item.get("title", ""),
                "channelId": item.get("channelId", ""),
                "channelTitle": item.get("channelTitle", ""),
                "duration": str(item.get("duration", "")),
                "viewCount": str(item.get("viewCount", "")),
                "likeCount": str(item.get("likeCount", "")),
                "publishedAt": item.get("publishedAt", ""),
                "description": (item.get("description") or "")[:200],
                "source": item.get("source", ""),
            }
            writer.writerow(row)
    print(f"[parse_metadata] CSV saved to {out_csv}")
