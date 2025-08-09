#!/usr/bin/env python3
import requests
import subprocess
import os

REPO = "nymtech/nym"
STATE_FILE = "/path/to/last_release.txt"  # store the last downloaded release tag
DOWNLOAD_DIR = "/path/to/downloads"       # where to store the binary
BINARY_NAME = "nym-node"

def get_latest_release_tag() -> str:
    """Get the latest release tag from GitHub API."""
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()["tag_name"]

def read_last_release() -> str:
    """Read the last installed release tag from file."""
    if not os.path.exists(STATE_FILE):
        return ""
    with open(STATE_FILE, "r") as f:
        return f.read().strip()

def write_last_release(tag: str) -> None:
    """Write the last installed release tag to file."""
    with open(STATE_FILE, "w") as f:
        f.write(tag)

def download_release(tag: str) -> None:
    """Download the release binary using wget."""
    # Adjust URL format if nym changes naming
    url = f"https://github.com/{REPO}/releases/download/{tag}/{BINARY_NAME}"
    output_path = os.path.join(DOWNLOAD_DIR, "nuevo")
    subprocess.run(["wget", "-c", url, "-O", output_path], check=True)

def main():
    latest_tag = get_latest_release_tag()
    last_tag = read_last_release()

    if latest_tag != last_tag:
        print(f"New release found: {latest_tag} (previous: {last_tag or 'none'})")
        download_release(latest_tag)
        write_last_release(latest_tag)
    else:
        print(f"No new release. Still at {last_tag}")

if __name__ == "__main__":
    main()

