#!/usr/bin/env python3
import requests
import re
import time
import threading
import subprocess
import os
import sys
from logger_utils import setup_logger

# --- Configuration ---
REPO = "nymtech/nym"
STATE_FILE = "/home/nymnode/last_release.txt"   # Tracks last installed release
DOWNLOAD_DIR = "/home/nymnode"                  # Where to store binary
SERVICE_NAME = "nym-node"                       # systemd service name
BINARY_FILENAME = "nym-node"                    # Final binary name
# ----------------------

logger = setup_logger()

def get_latest_release_tag() -> str:
    """Fetch the latest release tag from GitHub API."""
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

def download_release(tag: str) -> str:
    """Download the release binary using wget, return its path."""
    # Build download URL
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
    latest_tag = get_latest_release_tag()
    last_tag = read_last_release()

    if latest_tag != last_tag:
        logger.info(f"New release detected: {latest_tag} (previous: {last_tag or 'none'})")
        binary_path = download_release(latest_tag)
        update_binary(binary_path)
        write_last_release(latest_tag)
    else:
        logger.debug(f"No new release. Still at {last_tag}")

if __name__ == "__main__":
    main()
