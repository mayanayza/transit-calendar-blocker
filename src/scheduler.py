import uuid
from datetime import datetime, timedelta
from typing import Set

import config
from loguru import logger

import database as db
from calendar_service import calendar_service
from transit_service import are_locations_similar, calculate_transit_time


def check_for_calendar_updates():
    """Check for calendar updates and process any changes"""
    logger.info("Checking for calendar updates")

    try:
        # Fetch events for the look-forward window
        current_events = calendar_service.fetch_recently_updated_events()

        # Process all events with locations
        dates_to_process = set()
        current_event_ids = set()

        # Save events and collect dates to process for changed/new events
        for event in current_events:
            current_event_ids.add(event["id"])
            if event.get("location"):
                date_str, event_changed = db.save_event(event)
                # Only add to processing if event details have changed
                if event_changed:
                    dates_to_process.add(date_str)
                    logger.info(f"Event '{event.get('title')}' on {date_str} has changed, will process")
                else:
                    logger.debug(f"Event '{event.get('title')}' on {date_str} unchanged, skipping")

        # Check for deleted events
        deleted_event_dates = db.detect_deleted_events(current_event_ids)
        for date_str in deleted_event_dates:
            dates_to_process.add(date_str)
            logger.info(f"Detected deleted events on {date_str}, will process")

        # Process each date
        for date_str in dates_to_process:
            process_date(date_str)

        logger.info(f"Calendar update check complete, processed {len(dates_to_process)} dates")
    except Exception as e:
        logger.error(f"Error checking for calendar updates: {str(e)}")


def process_date(date):
    """Process a specific date

    Args:
        date (str or datetime): Date to process
    """
    if isinstance(date, datetime):
        date_str = date.strftime('%Y-%m-%d')
    else:
        date_str = date

    logger.info(f"Processing transit events for date: {date_str}")

    try:
        # First delete transit events from the calendar
        try:
            num_deleted = calendar_service.delete_transit_events_for_date(date_str)
            logger.info(f"Deleted {num_deleted} transit events from calendar for date: {date_str}")
        except Exception as e:
            logger.error(f"Error deleting transit events from calendar: {str(e)}")

        # Then delete from our database
        try:
            num_deleted_db = db.delete_transit_events_for_date(date_str)
            logger.info(f"Deleted {num_deleted_db} transit events from database for date: {date_str}")
        except Exception as e:
            logger.error(f"Error deleting transit events from database: {str(e)}")

        # Get current events for the date (this will only include events that still exist)
        events = db.get_events_for_date(date_str)

        # Filter events with locations and sort by start time
        events_with_location = [e for e in events if e.location]
        events_with_location.sort(key=lambda ev: ev.start_time)

        if not events_with_location:
            logger.info(f"No events with locations found for date: {date_str}")
            # Clean up any orphaned event records for this date
            db.cleanup_orphaned_events_for_date(date_str)
            return

        # Process events to create transit events
        last_location = config.HOME_ADDRESS
        last_event_name = "Home"

        for i, current_event in enumerate(events_with_location):
            current_location = current_event.location
            current_title = "Home" if are_locations_similar(config.HOME_ADDRESS,
                                                            current_location) else current_event.title
            transit_end_time = current_event.start_time

            if not are_locations_similar(last_location, current_location):
                # Calculate transit time
                transit_duration = calculate_transit_time(
                    last_location,
                    current_location,
                    transit_end_time
                )

                if transit_duration and transit_duration <= config.MAX_TRANSIT_TIME_HOURS * 3600:
                    # Round duration to nearest 15 minutes (900 seconds)
                    rounded_transit_duration = (transit_duration // 900 + 1) * 900
                    transit_start_time = transit_end_time - timedelta(seconds=rounded_transit_duration)

                    # Create transit event
                    transit_event = {
                        "id": str(uuid.uuid4()),
                        "title": f"{last_event_name} > {current_title}",
                        "origin": last_location,
                        "destination": current_location,
                        "startTime": transit_start_time.isoformat(),
                        "endTime": transit_end_time.isoformat()
                    }

                    # Save to database and create on calendar
                    db.save_transit_event(transit_event)
                    calendar_service.create_transit_event(transit_event)

            # Update last location and event name
            last_location = current_location
            last_event_name = current_title

            # Create transit event back home if this is the last event of the day
            if i == len(events_with_location) - 1:
                home_transit_start_time = current_event.end_time

                if not are_locations_similar(current_location, config.HOME_ADDRESS):
                    # Calculate transit time from last event to home
                    home_transit_duration = calculate_transit_time(
                        current_location,
                        config.HOME_ADDRESS,
                        home_transit_start_time
                    )

                    if home_transit_duration:
                        # Round duration to nearest 15 minutes
                        rounded_home_transit_duration = (home_transit_duration // 900 + 1) * 900
                        home_transit_end_time = home_transit_start_time + timedelta(
                            seconds=rounded_home_transit_duration)

                        # Create transit event
                        transit_event = {
                            "id": str(uuid.uuid4()),
                            "title": f"{current_title} > Home",
                            "origin": current_location,
                            "destination": config.HOME_ADDRESS,
                            "startTime": home_transit_start_time.isoformat(),
                            "endTime": home_transit_end_time.isoformat()
                        }

                        # Save to database and create on calendar
                        db.save_transit_event(transit_event)
                        calendar_service.create_transit_event(transit_event)

        logger.info(f"Completed processing transit events for date: {date_str}")
    except Exception as e:
        logger.error(f"Error processing date {date_str}: {str(e)}")


def process_daily_update():
    """Process the daily update - looks ahead in the calendar"""
    logger.info("Running daily update")

    try:
        # Look forward to target date (default is lookForwardDays ahead)
        now = datetime.now()
        target_date = now + timedelta(days=config.LOOK_FORWARD_DAYS)
        target_date_str = target_date.strftime('%Y-%m-%d')

        # Process the target date
        process_date(target_date_str)

        logger.info(f"Daily update complete for target date: {target_date_str}")
    except Exception as e:
        logger.error(f"Error in daily update: {str(e)}")


def reset_all_transit_events():
    """Reset all transit events for the look-forward window"""
    logger.info("Resetting all transit events")

    try:
        now = datetime.now()

        for i in range(config.LOOK_FORWARD_DAYS + 1):
            target_date = now + timedelta(days=i)
            target_date_str = target_date.strftime('%Y-%m-%d')

            process_date(target_date_str)

        logger.info("Reset of all transit events complete")
    except Exception as e:
        logger.error(f"Error resetting transit events: {str(e)}")