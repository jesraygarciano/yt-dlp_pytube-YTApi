# YouTube Combo Scraper (Data API + yt-dlp + pytube) with ETag

This project demonstrates how to combine:

- **YouTube Data API** to list channel videos with eTag caching
- **yt-dlp** for metadata/detailed fallback scraping
- **pytube** for single-video quick checks
- All while storing your `YOUTUBE_API_KEY` in a `.env` file.

## Project Setup

1. **Clone** or copy this repo structure.

2. **Install dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate     # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
