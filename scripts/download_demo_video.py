"""
Download a demo traffic video for testing the vehicle detection pipeline.

Usage:
    python scripts/download_demo_video.py

This downloads a royalty-free traffic video from the internet.
If download fails, you can manually place any traffic video at:
    data/videos/demo_traffic.mp4
"""

import os
import sys
import urllib.request
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = PROJECT_ROOT / "data" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = VIDEOS_DIR / "demo_traffic.mp4"


def download_demo_video():
    """Download a sample traffic video."""
    # Pexels royalty-free traffic video (short clip)
    urls = [
        # A short traffic clip from Pexels (free to use)
        "https://videos.pexels.com/video-files/2053100/2053100-sd_640_360_30fps.mp4",
        "https://videos.pexels.com/video-files/1721294/1721294-sd_640_360_25fps.mp4",
    ]

    if OUTPUT_FILE.exists():
        print(f"Demo video already exists: {OUTPUT_FILE}")
        return True

    for url in urls:
        try:
            print(f"Downloading demo video from: {url}")
            print("This may take a moment...")

            def progress(count, block_size, total_size):
                pct = count * block_size * 100 / total_size
                print(f"\r  Progress: {pct:.1f}%", end="", flush=True)

            urllib.request.urlretrieve(url, str(OUTPUT_FILE), reporthook=progress)
            print(f"\n✅ Demo video saved: {OUTPUT_FILE}")
            return True
        except Exception as e:
            print(f"  Failed: {e}")
            continue

    print("\n⚠️  Could not download demo video automatically.")
    print(f"   Please manually place a traffic video at: {OUTPUT_FILE}")
    print("   Any .mp4 traffic video will work.")
    return False


if __name__ == "__main__":
    success = download_demo_video()
    sys.exit(0 if success else 1)
