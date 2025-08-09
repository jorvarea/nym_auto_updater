# Nym Auto Updater

Automates downloading, updating, and managing the `nym-node` service binary from official GitHub releases.

---

## Description

This Python script:

- Fetches the latest release tag from the official GitHub repository `nymtech/nym`.
- Downloads the updated binary if a new version is available.
- Stops the `nym-node` service, updates the binary, and restarts the service.
- Monitors the service logs to verify proper startup and reports status via console and optional Discord notifications.
- Uses rotating logs for activity tracking.

---

## Requirements

- Python 3.8+  
- Python package: `requests`  
- `wget` installed on your system  
- Sudo access to manage the `nym-node` systemd service  
- (Optional) Discord webhook URL for logging notifications  

---

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/nym_auto_updater.git
   cd nym_auto_updater
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Set up a Discord webhook URL in the `.env` file.

---

## Usage:

   ```bash
   python script.py
   ```

---

## Automation with cron

1. Add the script to your crontab to run it automatically.

   ```bash
   crontab -e
   ```

2. To schedule the script to run daily at 2:00 AM, add this line to your crontab:

```cron
0 2 * * * /home/nymnode/nym_auto_updater/venv/bin/python /home/nymnode/nym_auto_updater/script.py
```

Feel free to adjust paths and environment variables accordingly.
