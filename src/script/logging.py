"""
Centralized logging configuration for the Transit Calendar application.
Import this module in other modules to get a properly configured logger.
"""

import os
import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_file, log_level):
    """
    Set up logging for the application.
    
    Args:
        log_file (str): Path to the log file
        log_level (str): Log level (INFO, DEBUG, etc.)
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Remove default handlers
    logger.remove()
    
    # Add stderr handler
    logger.add(sys.stderr, level=log_level, 
               format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    
    # Add file handler
    logger.add(log_file, level=log_level, 
               rotation="10 MB", retention="30 days", compression="zip",
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
    
    logger.info(f"Logging initialized: level={log_level}, file={log_file}")