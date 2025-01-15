# YouTube Combo Scraper (Data API + yt-dlp + pytube) with ETag

This project demonstrates how to combine:

- **YouTube Data API** to list channel videos with eTag caching
- **yt-dlp** for metadata/detailed fallback scraping
- **pytube** for single-video quick checks
- All while storing your `YOUTUBE_API_KEY` and PROXIES in a `.env` file.

## Project Setup

**Clone** or copy this repo structure.

# 1) Create venv & install dependencies
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2) Put your .env with YOUTUBE_API_KEY and PROXIES
NODE_ENV=
YOUTUBE_API_KEY=
PROXIES=

# 3) Adjust data/input_links.json to your desired list of URLs
E.G:
{
    "urls": [
      "https://www.youtube.com/@muni_gurume",
      "https://www.youtube.com/@Hasida",
      "https://www.youtube.com/@tamo__tyan"
    ]
}

# 4) Run main.py
python main.py \
  --use-api \
  --dump-json data/output/merged.json \
  --dump-csv data/output/merged.csv

# That will:
#  - Use YouTube Data API for channel links,
#  - fallback to yt-dlp or single-video pytube,
#  - rotate proxies for each request,
#  - produce data/output/*.info.json for each channel or video,
#  - create data/output/merged.json + merged.csv with all info.
