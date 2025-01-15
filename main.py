#!/usr/bin/env python3
import os
import subprocess
import sys
import argparse
import json
from pathlib import Path

def run_yt_dlp_metadata_only(url: str, output_dir: str):
    """
    Use yt-dlp to download ONLY the metadata (info JSON) for the given URL.
    - This will create a JSON file in the output directory.
    - By default, the file name is something like: %(title)s [%(id)s].info.json
    """
    # Ensure output dir exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    command = [
        "yt-dlp",
        "--skip-download",           # don't actually download the video file
        "--write-info-json",         # produce .info.json with all metadata
        "--ignore-errors",           # keep going on errors
        "--output", f"{output_dir}/%(title)s [%(id)s].%(ext)s",
        url
    ]
    print(f"Running yt-dlp: {' '.join(command)}")
    subprocess.run(command, check=False)
    # Using check=False to let it continue if a URL fails

def load_info_json_files(output_dir: str):
    """
    Gather all *.info.json files from the output_dir and load them into memory as a list.
    You can parse them or process them further.
    """
    info_files = list(Path(output_dir).glob("*.info.json"))
    all_data = []
    for fpath in info_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_data.append(data)
        except Exception as e:
            print(f"Failed to load {fpath}: {e}")
    return all_data

def parse_data_example(all_data):
    """
    Example function to parse loaded data for your own usage:
    Each item in all_data is the YouTube metadata from yt-dlp.
    Some common keys:
      - title
      - description
      - channel
      - channel_id
      - view_count
      - like_count
      - comment_count
      - webpage_url
      - upload_date
      - duration
      - playlist / playlist_id (if from a playlist) ...
    """
    results = []
    for entry in all_data:
        summary = {
            "video_id": entry.get("id"),
            "title": entry.get("title"),
            "channel": entry.get("channel"),
            "channel_id": entry.get("channel_id"),
            "view_count": entry.get("view_count"),
            "like_count": entry.get("like_count"),
            "upload_date": entry.get("upload_date"),
            "duration_sec": entry.get("duration"),
            "webpage_url": entry.get("webpage_url"),
        }
        results.append(summary)
    return results

def save_json(data, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved combined JSON to {out_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Scrape YouTube metadata using yt-dlp (optionally show Pytube demo)."
    )
    parser.add_argument(
        "--input-file",
        default="data/input_links.txt",
        help="Text file with one YouTube link per line"
    )
    parser.add_argument(
        "--output-dir",
        default="data/output",
        help="Directory to save .info.json files and consolidated results"
    )
    parser.add_argument(
        "--consolidate-json",
        action="store_true",
        help="If set, load all .info.json files and create a single JSON file"
    )
    parser.add_argument(
        "--pytube-demo",
        action="store_true",
        help="If set, runs a quick Pytube demo on the first link instead of scraping them all"
    )

    args = parser.parse_args()

    # If --pytube-demo is set, just demonstrate Pytube usage on the first line in the input file.
    if args.pytube_demo:
        try:
            from pytube import YouTube
        except ImportError:
            print("Error: Pytube is not installed. Run 'pip install pytube'.")
            sys.exit(1)
        
        with open(args.input_file, "r", encoding="utf-8") as f:
            first_link = f.readline().strip()
        if not first_link:
            print(f"No link found in {args.input_file} - cannot demo Pytube.")
            sys.exit(1)
        
        print(f">>> Pytube Demo for: {first_link}")
        yt = YouTube(first_link)
        print("Video Title:", yt.title)
        print("Channel URL:", yt.channel_url)
        print("Channel ID:", yt.channel_id)
        print("Description:", (yt.description or "")[:80], "...")
        print("Publish Date:", yt.publish_date)
        print()
        print(">>> Pytube demo complete. Exiting.")
        sys.exit(0)

    # Otherwise, we proceed with yt-dlp calls for each line in input_file.
    with open(args.input_file, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    if not links:
        print(f"No links found in {args.input_file}. Nothing to do.")
        sys.exit(0)

    # Step 1: For each link, run yt-dlp in metadata-only mode.
    for link in links:
        run_yt_dlp_metadata_only(link, args.output_dir)

    # Step 2: (Optional) Consolidate results into a single JSON file.
    if args.consolidate_json:
        all_data = load_info_json_files(args.output_dir)
        parsed = parse_data_example(all_data)
        out_path = os.path.join(args.output_dir, "consolidated.json")
        save_json(parsed, out_path)

    print("Script finished.")

if __name__ == "__main__":
    main()
