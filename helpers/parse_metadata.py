import csv
import json
from typing import List, Dict

def parse_and_save_info_to_csv(info_list: List[Dict], out_csv: str):
    """
    Takes a list of raw JSON data from yt-dlp .info.json
    and writes a structured CSV.
    """
    fieldnames = [
        "video_id",
        "title",
        "channel",
        "channel_id",
        "duration",
        "view_count",
        "like_count",
        "webpage_url",
        "description"
    ]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in info_list:
            row = {
                "video_id": item.get("id", ""),
                "title": item.get("title", ""),
                "channel": item.get("channel", ""),
                "channel_id": item.get("channel_id", ""),
                "duration": item.get("duration", ""),
                "view_count": item.get("view_count", ""),
                "like_count": item.get("like_count", ""),
                "webpage_url": item.get("webpage_url", ""),
                "description": item.get("description", "")[:200]  # store partial desc or entire
            }
            writer.writerow(row)
    print(f"Saved CSV: {out_csv}")
