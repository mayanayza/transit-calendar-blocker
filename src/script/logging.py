"""
Centralized logging configuration for the Transit Calendar application
with OpenObserve integration for error alerting.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from loguru import logger


class OpenObserveLogHandler:
    """
    Custom handler for Loguru that sends logs to OpenObserve.
    """
    
    def __init__(self, url, organization="default", stream="logs", 
                 api_key=None, username=None, password=None, 
                 batch_size=100, flush_interval=5, verbose=True):
        """
        Initialize the OpenObserve log handler.
        
        Args:
            url (str): OpenObserve base URL (e.g., "http://openobserve:5080")
            organization (str): Organization name in OpenObserve
            stream (str): Stream name in OpenObserve 
            api_key (str, optional): API key for authentication
            username (str, optional): Username for basic auth if not using API key
            password (str, optional): Password for basic auth if not using API key
            batch_size (int): Number of logs to batch before sending
            flush_interval (int): Maximum time in seconds between sends
            verbose (bool): Whether to print status messages to console
        """
        # Fix URL construction - extract base URL without API paths
        parsed_url = urlparse(url)
        # Extract domain and scheme only
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Construct proper endpoint URL
        self.url = f"{base_url}/api/{organization}/{stream}/_json"
        
        self.api_key = api_key
        self.username = username
        self.password = password
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.verbose = verbose
        self.buffer = []
        self.lock = threading.Lock()
        self.last_flush = time.time()
        self.successful_sends = 0
        self.failed_sends = 0
        
        # Set up the auth headers
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Basic {api_key}"
                
        # Start background thread for flushing
        self.flush_thread = threading.Thread(target=self._background_flush, daemon=True)
        self.flush_thread.start()
        
        if self.verbose:
            print(f"OpenObserve handler initialized - sending to {self.url}")
    
    def _get_auth(self):
        """Return auth tuple for requests if using username/password."""
        if self.username and self.password:
            return (self.username, self.password)
        return None
    
    def _background_flush(self):
        """Background thread that periodically flushes the log buffer."""
        while True:
            time.sleep(1)  # Check every second
            if time.time() - self.last_flush >= self.flush_interval:
                self.flush()
    
    def flush(self):
        """Flush the current log buffer to OpenObserve."""
        with self.lock:
            if not self.buffer:
                return
                
            logs_to_send = self.buffer.copy()
            self.buffer = []
        
        try:
            response = requests.post(
                self.url,
                headers=self.headers,
                auth=self._get_auth(),
                data="\n".join(logs_to_send),
                timeout=10
            )
            
            if response.status_code >= 400:
                self.failed_sends += 1
                error_msg = f"Error sending logs to OpenObserve. Status: {response.status_code}, Response: {response.text}"
                sys.stderr.write(error_msg + "\n")
                if self.verbose:
                    print(f"❌ {error_msg}")
        except requests.exceptions.ConnectionError as e:
            self.failed_sends += 1
            error_msg = f"Connection error sending logs to OpenObserve: {str(e)}"
            sys.stderr.write(error_msg + "\n")
            if self.verbose:
                print(f"❌ {error_msg}")
        except Exception as e:
            self.failed_sends += 1
            error_msg = f"Exception while sending logs to OpenObserve: {str(e)}"
            sys.stderr.write(error_msg + "\n")
            if self.verbose:
                print(f"❌ {error_msg}")
        finally:
            self.last_flush = time.time()
    
    def write(self, message):
        """Process a log message and add it to the buffer."""
        record = message.record
        
        # Create a dictionary with the log data
        log_data = {
            "timestamp": record["time"].timestamp() * 1000,  # Convert to milliseconds
            "level": record["level"].name,
            "message": record["message"],
            "name": record["name"],
            "function": record["function"],
            "line": record["line"],
            "file": record["file"].path,
            "process_id": record["process"].id,
            "thread_id": record["thread"].id
        }
        
        # Add any exception info if present
        if record["exception"]:
            log_data["exception"] = str(record["exception"])
            
        # Add any extra fields
        log_data.update(record["extra"])
        
        # Serialize and add to buffer
        with self.lock:
            self.buffer.append(json.dumps(log_data))
            
            # If we've reached batch size, flush immediately
            if len(self.buffer) >= self.batch_size:
                self.flush()
        
        # Return False to indicate we're not modifying the message
        return False

def setup_openobserve_logging(log_level="ERROR", **kwargs):
    """
    Add OpenObserve logging handler for error alerting.
    
    Args:
        log_level (str): Minimum log level to send to OpenObserve
        **kwargs: Additional arguments for OpenObserveLogHandler
    
    Returns:
        The OpenObserve log handler instance
    """
    # Get arguments from environment variables if not provided
    url = kwargs.get('url') or os.environ.get('OO_URL')
    if not url:
        print("❌ OpenObserve URL not provided! Please specify url parameter or set OO_URL environment variable")
        raise ValueError("OpenObserve URL must be provided either as a parameter or OO_URL environment variable")
    
    organization = kwargs.get('organization') or os.environ.get('OO_ORGANIZATION', 'default')
    stream = kwargs.get('stream') or os.environ.get('OO_STREAM', 'logs')
    api_key = kwargs.get('api_key') or os.environ.get('OO_API_KEY')
    username = kwargs.get('username') or os.environ.get('OO_USERNAME')
    password = kwargs.get('password') or os.environ.get('OO_PASSWORD')
    verbose = kwargs.get('verbose', True)
    
    if verbose:
        print("🔄 Initializing OpenObserve logging:")
        print(f"  URL: {url}")
        print(f"  Organization: {organization}")
        print(f"  Stream: {stream}")
        print(f"  Auth: {'API Key' if api_key else 'Username/Password' if username and password else 'None'}")
        print(f"  Log level: {log_level}")
    
    # Create and add the handler
    handler = OpenObserveLogHandler(
        url=url,
        organization=organization,
        stream=stream,
        api_key=api_key,
        username=username,
        password=password,
        batch_size=kwargs.get('batch_size', 100),
        flush_interval=kwargs.get('flush_interval', 5),
        verbose=verbose
    )
    
    logger.add(
        handler,
        level=log_level
    )
    
    if verbose:
        print(f"✅ OpenObserve logging initialized for level {log_level} and above")

    return handler

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