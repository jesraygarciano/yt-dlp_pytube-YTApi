#!/usr/bin/env python3
"""
youtube_batch_combo.py

Demonstration of batch processing for two lists:
  1) accounts = [[channelUrl, countryName], ...]
  2) urls = [url1, url2, ...]

Uses:
  - yt-dlp for multi-video scraping (channels, playlists).
  - pytube for single-video scraping.

To run:
  python youtube_batch_combo.py
"""

import re
import sys
import os
import random
import json

from yt_dlp import YoutubeDL
from pytube import YouTube


# ==========================
# 1) Hard-coded data sets
# ==========================

accounts = [
    ["https://www.youtube.com/channel/UCVjlpEjEY9GpksqbEesJnNA", "アメリカ合衆国"],
    ["https://www.youtube.com/channel/UCpdvoICPfIeID9hNbB_9xXw", "不明"],
    ["https://www.youtube.com/channel/UCtdKiwN9vw961uho0lre4_A", "サウジアラビア"],
    ["https://www.youtube.com/channel/UCJK3VbSGg_3IHKtNIauIQTw", "不明"],
    ["https://www.youtube.com/channel/UC3jOiUbvgAEovuVU0uFVB4Q", "不明"],
    ["https://www.youtube.com/channel/UCERT7pnmRJdyxxtiar0B4dQ", "日本"],
    ["https://www.youtube.com/channel/UCy_peWgMbPYAx-Jh6cKKGYQ", "大韓民国"],
    ["https://www.youtube.com/channel/UCDjoi87PKTNPPTTA234g3Dg", "大韓民国"],
]

urls = [
    "https://www.youtube.com/@muni_gurume",
    "https://www.youtube.com/@Hasida",
    "https://www.youtube.com/@tamo__tyan",
    "https://www.youtube.com/@harapeko_Japan",
    "https://www.youtube.com/@shiyago",
    "https://www.youtube.com/@%E9%81%A0%E8%97%A4%E3%82%8A%E3%82%87%E3%81%86-m9s",
    "https://www.youtube.com/@%E3%82%B8%E3%83%A3%E3%82%AB%E3%83%AB%E3%82%BFB%E7%B4%9A%E3%82%B0%E3%83%AB%E3%83%A1%E3%82%AC%E3%82%A4%E3%83%89-n4z",
    "https://www.youtube.com/@gourmet_nikki",
    "https://www.youtube.com/@agedashi_gurume",
    "https://www.youtube.com/@cikarang-meshi",
]


# ==========================
# 2) Helper logic
# ==========================

def is_single_video(url: str) -> bool:
    """
    Heuristic to decide if `url` is likely a single video or not.
    If 'list=' or '/playlist' or '/channel/' is found => multi-video => yt-dlp.
    If 'watch?v=' or 'youtu.be/' => single => pytube.
    Otherwise guess by partial patterns (refine as needed).
    """
    if re.search(r"(list=|/playlist|/channel/)", url):
        return False
    if ("watch?v=" in url) or ("youtu.be/" in url):
        return True
    return False


def scrape_with_yt_dlp(url: str):
    """
    Use yt-dlp to fetch metadata from channel/playlist or multi-video links.
    Returns a dictionary containing metadata.
    """
    print(f"\n[yt-dlp] Scraping metadata for: {url}")
    ydl_opts = {
        'skip_download': True,
        'ignoreerrors': True,
        'quiet': True,  # set to False if you want more debug logs
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


def scrape_single_video_with_pytube(url: str):
    """
    Use pytube to fetch single video metadata.
    Returns a dictionary of essential data.
    """
    print(f"\n[pytube] Scraping single-video metadata for: {url}")
    yt = YouTube(url)
    data = {
        "title": yt.title,
        "author": yt.author,
        "views": yt.views,
        "length": yt.length,
        "publish_date": yt.publish_date.isoformat() if yt.publish_date else None,
        "description": yt.description,
        "channel_url": f"https://www.youtube.com/channel/{yt.channel_id}" if yt.channel_id else None,
    }
    return data


def print_yt_dlp_results(info: dict, extra_label: str = ""):
    """
    Print relevant metadata from yt-dlp's dictionary results.
    """
    if not info:
        print("No metadata found.")
        return

    # If multi-video, there may be an 'entries' array:
    if 'entries' in info and info['entries']:
        print(f"\n=== MULTI-VIDEO METADATA ({extra_label}) ===")
        main_title = info.get('title') or "Unknown Playlist/Channel"
        print(f"Collection Title: {main_title}")
        print(f"Video Count: {len(info['entries'])}")

        # Print short data for each entry
        for i, entry in enumerate(info['entries'], start=1):
            if not entry:
                continue
            print(f"\n[{i}] Title: {entry.get('title')}")
            print(f"   Uploader:    {entry.get('uploader')}")
            print(f"   Duration(s): {entry.get('duration')}")
            print(f"   ViewCount:   {entry.get('view_count')}")

    else:
        # Single entry from yt-dlp
        print(f"\n=== SINGLE VIDEO METADATA ({extra_label}, yt-dlp) ===")
        print(f"Title:       {info.get('title')}")
        print(f"Uploader:    {info.get('uploader')}")
        print(f"Duration(s): {info.get('duration')}")
        print(f"ViewCount:   {info.get('view_count')}")


def print_pytube_results(data: dict, extra_label: str = ""):
    """
    Print the single-video metadata from pytube's dictionary.
    """
    print(f"\n=== SINGLE VIDEO METADATA ({extra_label}, pytube) ===")
    print(f"Title:         {data.get('title')}")
    print(f"Author:        {data.get('author')}")
    print(f"Views:         {data.get('views')}")
    print(f"Length(s):     {data.get('length')}")
    print(f"Publish Date:  {data.get('publish_date')}")
    print(f"Channel URL:   {data.get('channel_url')}")
    desc = data.get('description') or ''
    print(f"Description:   {desc[:80]}...")


def process_entry(url: str, country_name: str = ""):
    """
    Decide single vs. multi approach. 
    If single => pytube, else => yt-dlp.
    Print results plus any country info if relevant.
    """
    # 1) Check single vs multiple
    single = is_single_video(url)

    # 2) If single => pytube
    if single:
        metadata = scrape_single_video_with_pytube(url)
        print_pytube_results(metadata, extra_label=country_name or "NoCountry")
    else:
        # multi => channel or playlist => use yt-dlp
        info = scrape_with_yt_dlp(url)
        print_yt_dlp_results(info, extra_label=country_name or "NoCountry")


# ==========================
# 3) Main "batch" logic
# ==========================

def process_accounts_batch():
    """
    This simulates your 'insert-youtube-accounts-with-company' style, 
    where we have [[channelUrl, countryName], ...].
    """
    print("\n========== BATCH: ACCOUNTS WITH COUNTRY ===========\n")
    for [url, country_name] in accounts:
        process_entry(url, country_name)


def process_urls_batch():
    """
    This simulates your 'insert-youtube-accounts' style, 
    where we have a plain list of URLs for channels or videos.
    """
    print("\n========== BATCH: PLAIN URLS ===========\n")
    for url in urls:
        process_entry(url)


def main():
    # 1) Process the "accounts" batch
    process_accounts_batch()
    # 2) Process the "urls" batch
    process_urls_batch()


if __name__ == "__main__":
    main()
