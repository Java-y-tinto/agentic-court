import logging
from datetime import datetime
from pathlib import Path

_RESET = "\x1b[0m"
_LEVEL_COLORS = {
    logging.DEBUG:    "\x1b[37m",      # white
    logging.INFO:     "\x1b[32m",      # green
    logging.WARNING:  "\x1b[33m",      # yellow
    logging.ERROR:    "\x1b[31m",      # red
    logging.CRITICAL: "\x1b[1;31m",   # bold red
}



class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, _RESET)
        original = record.levelname
        record.levelname = f"{color}[{original}]{_RESET}"
        result = super().format(record)
        record.levelname = original
        return result


_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

_file_handler = logging.FileHandler(
    _LOG_DIR / f"tribunal_{_run_ts}.log",
    encoding="utf-8",
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_ColorFormatter("%(levelname)s %(message)s"))

logger = logging.getLogger("sentinel")
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)
