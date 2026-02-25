"""
로깅 설정 (loguru 기반, 없으면 표준 logging fallback)
"""

import sys
import logging
from pathlib import Path

_initialized = False

# loguru 사용 가능 여부 확인
try:
    from loguru import logger as _loguru_logger
    _USE_LOGURU = True
except ImportError:
    _USE_LOGURU = False
    _loguru_logger = None

# 표준 logging fallback
_stdlib_logger = logging.getLogger("autopilot")


class _StdlibLoggerWrapper:
    """loguru와 동일한 인터페이스를 제공하는 표준 logging 래퍼"""

    def __init__(self, stdlib_logger):
        self._logger = stdlib_logger

    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg)

    def info(self, msg, *args, **kwargs):
        self._logger.info(msg)

    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg)

    def error(self, msg, *args, **kwargs):
        self._logger.error(msg)

    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg)

    def success(self, msg, *args, **kwargs):
        self._logger.info(f"✅ {msg}")

    def remove(self, *args, **kwargs):
        pass

    def add(self, *args, **kwargs):
        pass


def setup_logger(log_level: str = "INFO", log_dir: Path | None = None):
    """로거 초기화"""
    global _initialized
    if _initialized:
        return get_logger()

    if _USE_LOGURU:
        # loguru 사용
        _loguru_logger.remove()
        _loguru_logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            colorize=True,
        )
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            _loguru_logger.add(
                str(log_dir / "autopilot_{time:YYYY-MM-DD}.log"),
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
                rotation="1 day",
                retention="30 days",
                compression="zip",
            )
    else:
        # 표준 logging fallback
        level = getattr(logging, log_level.upper(), logging.INFO)
        _stdlib_logger.setLevel(level)
        if not _stdlib_logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(level)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            _stdlib_logger.addHandler(handler)

            if log_dir:
                log_dir.mkdir(parents=True, exist_ok=True)
                fh = logging.FileHandler(str(log_dir / "autopilot.log"))
                fh.setLevel(level)
                fh.setFormatter(formatter)
                _stdlib_logger.addHandler(fh)

    _initialized = True
    return get_logger()


def get_logger():
    """로거 인스턴스 반환"""
    if _USE_LOGURU:
        return _loguru_logger
    return _StdlibLoggerWrapper(_stdlib_logger)
