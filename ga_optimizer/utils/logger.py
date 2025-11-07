"""
Logger - Loglama Sistemi

GA optimizasyon sürecini loglar.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = 'ga_optimizer',
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Logger oluştur ve yapılandır.

    Args:
        name: Logger adı
        log_file: Log dosyası yolu (opsiyonel)
        level: Log seviyesi
        format_string: Custom format

    Returns:
        logging.Logger: Yapılandırılmış logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Mevcut handler'ları temizle
    logger.handlers = []

    # Format
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (opsiyonel)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = 'ga_optimizer') -> logging.Logger:
    """Mevcut logger'ı al."""
    return logging.getLogger(name)


# Default logger
_default_logger = None


def get_default_logger() -> logging.Logger:
    """Default logger'ı al (lazy initialization)."""
    global _default_logger
    if _default_logger is None:
        log_dir = Path('ga_optimizer/logs')
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'ga_optimizer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        _default_logger = setup_logger(log_file=str(log_file))
    return _default_logger
