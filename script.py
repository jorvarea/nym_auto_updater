#!/usr/bin/env python3
import requests
import re
import time
import threading
import subprocess
import os
import sys
import re
import shutil
from datetime import datetime
from logger_utils import setup_logger

# --- Configuration ---
REPO = "nymtech/nym"
STATE_FILE = "/home/nymnode/last_release.txt"   # Tracks last installed release
DOWNLOAD_DIR = "/home/nymnode"                  # Where to store binary
SERVICE_NAME = "nym-node"                       # systemd service name
BINARY_FILENAME = "nym-node"                    # Final binary name
# ----------------------

logger = setup_logger()

def parse_version(tag: str) -> tuple:
    """
    Extracts version numbers from tag.
    Example: 'nym-binaries-v2025.13-emmental' -> (2025, 13)
    """
    match = re.search(r"nym-binaries-v(\d+)\.(\d+)", tag)
    if not match:
        raise ValueError(f"Could not parse version from tag: {tag}")
    major, minor = match.groups()
    return int(major), int(minor)

def is_newer_version(latest: str, last: str) -> bool:
    """Return True if latest > last."""
    if not last:
        return True
    return parse_version(latest) > parse_version(last)

def get_latest_binary_release_tag() -> str:
    """
    Gets the latest stable binary release tag from GitHub.
    Skips prereleases.
    """
    url = f"https://api.github.com/repos/{REPO}/releases"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    releases = resp.json()

    for r in releases:
        if re.match(r"^nym-binaries", r["tag_name"]) and not r["prerelease"]:
            return r["tag_name"]
    
    logger.warning("No stable binary release found.")
    return ""

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

def backup_nym_folder():
    """Backup the entire .nym folder before making changes."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    nym_folder = "/home/nymnode/.nym"
    if os.path.exists(nym_folder):
        backup_folder = f"{nym_folder}_backup_{timestamp}.tar.gz"
        logger.info(f"Creating compressed backup of .nym folder at {backup_folder} ...")
        shutil.make_archive(f"{nym_folder}_backup_{timestamp}", 'gztar', nym_folder)
        logger.info("Backup of .nym folder completed successfully.")
    else:
        logger.warning(f".nym folder not found at {nym_folder}, skipping backup.")

def download_release(tag: str) -> str:
    """Download the release binary using wget, return its path."""
    url = f"https://github.com/{REPO}/releases/download/{tag}/{BINARY_FILENAME}"
    output_path = os.path.join(DOWNLOAD_DIR, f"{tag}")

    logger.info(f"Downloading {url} -> {output_path}")
    subprocess.run(["wget", "-q", "-c", url, "-O", output_path], check=True)
    return output_path

def monitor_packets(service_name: str, logger, timeout=600, check_interval=10) -> bool:
    """
    Monitor journalctl logs for service_name.
    Wait until 'Packets sent [total]' != 0 or timeout expires.
    Returns True if packets > 0, False if timeout.
    """
    pattern = re.compile(
        r"Packets sent \[total\].*?([\d\.]+)([MK]?)"
    )  # Capture number with possible M or K suffix

    def convert_to_number(s: str, suffix: str) -> float:
        val = float(s)
        if suffix == "M":
            val *= 1_000_000
        elif suffix == "K":
            val *= 1_000
        return val

    proc = subprocess.Popen(
        ["journalctl", "-f", "-u", f"{service_name}.service", "-n", "0", "--no-pager"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    last_value = 0.0
    last_check_time = time.time()

    def reader():
        nonlocal last_value, last_check_time
        for line in proc.stdout:
            logger.debug(f"journalctl line: {line.strip()}")
            match = pattern.search(line)
            if match:
                num_str, suffix = match.groups()
                val = convert_to_number(num_str, suffix)
                last_value = val
                logger.debug(f"Detected packets sent [total]: {val}")
                last_check_time = time.time()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            logger.error(
                f"Timeout {timeout}s expired. Packets sent [total] still 0."
            )
            proc.terminate()
            thread.join(timeout=1)
            return False

        if last_value > 0:
            logger.info("Packets sent [total] is > 0. Service running fine.")
            proc.terminate()
            thread.join(timeout=1)
            return True

        time.sleep(check_interval)

def update_binary(new_binary_path: str):
    """Replace current binary with new one and restart service."""
    os.chdir(DOWNLOAD_DIR)

    if not os.path.isfile(new_binary_path):
        logger.error(f"File {new_binary_path} does not exist.")
        sys.exit(1)

    subprocess.run(["chmod", "+x", new_binary_path], check=True)

    logger.info(f"Stopping service {SERVICE_NAME}...")
    if subprocess.run(["sudo", "service", SERVICE_NAME, "stop"]).returncode == 0:
        # Remove old binary and replace
        if os.path.exists(BINARY_FILENAME):
            os.remove(BINARY_FILENAME)
        os.rename(new_binary_path, BINARY_FILENAME)

        logger.info("Reloading daemon and starting service...")
        if subprocess.run(["sudo", "systemctl", "daemon-reload"]).returncode == 0 and \
           subprocess.run(["sudo", "service", SERVICE_NAME, "start"]).returncode == 0:
            logger.info(f"{SERVICE_NAME} restarted.")

            success = monitor_packets(SERVICE_NAME, logger)
            if not success:
                logger.error("Service packets never started flowing after restart.")
            else:
                logger.info("Service packets flowing correctly.")
        else:
            logger.error("Error reloading daemon or starting service.")
    else:
        logger.error(f"Could not stop {SERVICE_NAME} service.")

def main():
    try:
        latest_tag = get_latest_binary_release_tag()
        
        if not latest_tag:
            logger.info("No stable release found to update.")
            return

        last_tag = read_last_release()

        if is_newer_version(latest_tag, last_tag):
            logger.info(f"Newer release detected: {latest_tag} (previous: {last_tag or 'none'})")
            backup_nym_folder()
            binary_path = download_release(latest_tag)
            update_binary(binary_path)
            write_last_release(latest_tag)
        elif latest_tag == last_tag:
            logger.debug(f"No new release. Still at {last_tag}")
        else:
            logger.warning(f"Ignoring downgrade attempt: {latest_tag} < {last_tag}")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
