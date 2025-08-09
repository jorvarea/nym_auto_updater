import logging
from logging.handlers import RotatingFileHandler
import os
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[34m",     # blue
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[35m",  # magenta
    }

    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        colored_lines = [f"{color}{line}{self.RESET}" for line in message.splitlines()]
        return "\n".join(colored_lines)


class DiscordWebhookHandler(logging.Handler):
    """Logging handler that forwards log records (NOTIF and above) to a Discord webhook."""

    def __init__(self, webhook_url: str, level: int = logging.INFO) -> None:
        super().__init__(level)
        self.webhook_url: str = webhook_url

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            log_entry: str = self.format(record)
            payload: dict[str, str] = {
                "content": f"**{record.levelname}**```{log_entry}```"[:1975]
            }
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception as exc:
            print(f"[DiscordHandler] Failed to send log to Discord: {exc}", flush=True)
            pass


def setup_logger(log_name: str = "app") -> logging.Logger:
    logger = logging.getLogger(log_name)

    file_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        f"{log_name}.log", maxBytes=10 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(file_formatter)

    colored_formatter = ColoredFormatter("[%(asctime)s] [%(levelname)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    if DISCORD_WEBHOOK_URL:
        discord_handler = DiscordWebhookHandler(DISCORD_WEBHOOK_URL)
        discord_handler.setFormatter(file_formatter)
        logger.addHandler(discord_handler)

    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("app")
