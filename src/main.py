import os
import signal
import sys
import time
from typing import Optional

import config
from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from calendar_service import calendar_service
from database import cleanup_old_data, initialize_db
from scheduler import check_for_calendar_updates, process_daily_update

from functools import wraps
import signal

# Add email alert handler for errors
def email_handler(message):
    """Handler for sending email alerts on ERROR/CRITICAL logs"""
    try:
        msg = MIMEMultipart()
        msg['From'] = config.ALERT_EMAIL_FROM
        msg['To'] = config.ALERT_EMAIL_TO
        msg['Subject'] = "Transit Calendar Alert"
        
        body = f"""
        Transit Calendar Error Alert
        
        {message}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        if config.SMTP_USE_TLS:
            server.starttls()
        if config.SMTP_USERNAME:
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        # Use print instead of logger to avoid recursion
        print(f"Failed to send alert email: {e}")

# Add with custom format that includes level info
logger.add(
    email_handler, 
    level="ERROR",
    format="{time} | {level} | {name} | {message}"
)

def timeout_handler(signum, frame):
    raise TimeoutError("Job execution timeout")

def with_timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result
        return wrapper
    return decorator

# Global scheduler
scheduler: Optional[BackgroundScheduler] = None

def setup_logging_directories():
    """Setup logging to ensure log directory exists"""
    log_dir = os.path.dirname(config.LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    
    # Log system information for debugging
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Database path: {config.DB_PATH}")
    logger.info(f"Log file: {config.LOG_FILE}")
    logger.info(f"Environment variables: DB_PATH={os.environ.get('DB_PATH')}, LOG_FILE={os.environ.get('LOG_FILE')}")

@with_timeout(600)
def setup_scheduler():
    """Set up the scheduler with all required jobs"""
    global scheduler
    scheduler = BackgroundScheduler()
    
    # Calendar check job - runs every X minutes
    scheduler.add_job(
        check_for_calendar_updates,
        'interval',
        minutes=config.CALENDAR_CHECK_INTERVAL,
        id='calendar_check',
        replace_existing=True,
        max_instances=1,  # Explicitly limit to 1 instance
        coalesce=True,    # Combine missed runs into one
        misfire_grace_time=300  # Allow 5 minutes grace period
    )
    
    # Daily update job - runs at configured time
    scheduler.add_job(
        process_daily_update,
        'cron',
        hour=config.DAILY_UPDATE_HOUR,
        minute=config.DAILY_UPDATE_MINUTE,
        id='daily_update',
        replace_existing=True
    )
    
    # Weekly cleanup job - runs on Sunday at 2 AM
    scheduler.add_job(
        cleanup_old_data,
        'cron',
        day_of_week=6,
        hour=2,
        minute=0,
        id='weekly_cleanup',
        replace_existing=True
    )
    
    return scheduler

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    global scheduler
    logger.info("Shutting down...")
    if scheduler:
        scheduler.shutdown()
    sys.exit(0)

def main():
    """Main entry point for the application"""
    global scheduler
    logger.info("Starting Transit Calendar application")
    
    try:
        # Setup logging directories
        setup_logging_directories()
        
        # Initialize the database - exit if it fails
        if not initialize_db():
            logger.error("Database initialization failed - exiting")
            sys.exit(1)
        
        # Initialize calendar service
        calendar_service.initialize()

        # Set up the scheduler
        scheduler = setup_scheduler()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the scheduler
        scheduler.start()
        
        # Run initial check
        logger.info("Running initial calendar check")
        check_for_calendar_updates()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application shutting down...")
        if scheduler:
            scheduler.shutdown()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()