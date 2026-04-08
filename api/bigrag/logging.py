from __future__ import annotations

import logging
import time


class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLORS = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    LEVEL_SHORT = {
        logging.DEBUG: "DBG",
        logging.INFO: "INF",
        logging.WARNING: "WRN",
        logging.ERROR: "ERR",
        logging.CRITICAL: "CRT",
    }

    def format(self, record: logging.LogRecord) -> str:
        c = self.COLORS.get(record.levelno, "")
        r = self.RESET
        lvl = self.LEVEL_SHORT.get(record.levelno, record.levelname)
        ts = self.formatTime(record, "%H:%M:%S")
        name = record.name.removeprefix("bigrag.")
        return f"\033[90m{ts}{r} {c}{lvl}{r} \033[1m{name}{r} {record.getMessage()}"


request_logger = logging.getLogger("bigrag.http")


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        path = scope["path"]
        method = scope["method"]
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        elapsed = (time.monotonic() - start) * 1000
        request_logger.info(f"← {method} {path} {status_code} {elapsed:.0f}ms")
