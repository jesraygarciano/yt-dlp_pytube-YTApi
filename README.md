# YouTube Combo Scraper (yt-dlp + pytube + Youtube Data API)

A combined approach to scraping YouTube metadata **without** using the official Data API.  
- **yt-dlp**: used for **channels** and **playlists** (multiple videos).
- **pytube**: used for **single videos** (simple scenario, quick metadata).

> **Note**: Automated scraping may violate YouTube’s Terms of Service. Use responsibly and primarily for personal research/archival. For large production usage, consider official APIs or request higher quotas.

## Features

- Single script that detects whether a URL is a single video or a channel/playlist, then uses the right library.
- Prints out video titles, durations, view counts, etc. 
- Optionally skip or modify the logic if you want to also download videos.

## Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/<youruser>/youtube-combo-scraper.git
   cd youtube-combo-scraper

# 1. Set up your environment:
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Export or set your YouTube Data API key (if you want to use it):
export YT_API_KEY="AIza..."

# 3. Create or edit data/input_links.txt to contain a mix of single videos, channel links, etc.

# 4. Run the main script
python main.py --use-api --dump-json data/output/combined.json

#   Explanation:
#   --use-api => tries the YouTube Data API for channel links
#   --dump-json => merges results (Data API, yt-dlp, pytube) into one JSON
#
#   Check data/output for .info.json files from yt-dlp, or see data/channel_etags.json for ETag caching.

