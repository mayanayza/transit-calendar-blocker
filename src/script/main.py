import signal
import sys
import time

import config
from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from script.calendar_service import calendar_service
from script.database import cleanup_old_data, initialize_db
from script.scheduler import check_for_calendar_updates, process_daily_update

# Global scheduler
scheduler = None

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
        replace_existing=True
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
    logger.info("Shutting down...")
    if scheduler:
        scheduler.shutdown()
    sys.exit(0)

def main():
    """Main entry point for the application"""
    logger.info("Starting Transit Calendar application")
    
    try:
        # Initialize the database
        initialize_db()
        
        # Initialize calendar service
        calendar_service.initialize()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Setup and start the scheduler
        scheduler = setup_scheduler()
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