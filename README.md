# YouTube Combo Scraper (yt-dlp + pytube)

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
