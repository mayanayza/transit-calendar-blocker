import uuid
from datetime import datetime, timedelta
from typing import Set, List, Optional, Tuple

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


def _clear_existing_transit_events(date_str: str) -> None:
    """Clear existing transit events for a date from both calendar and database"""
    # Delete from calendar
    try:
        num_deleted = calendar_service.delete_transit_events_for_date(date_str)
        logger.info(f"Deleted {num_deleted} transit events from calendar for date: {date_str}")
    except Exception as e:
        logger.error(f"Error deleting transit events from calendar: {str(e)}")

    # Delete from database
    try:
        num_deleted_db = db.delete_transit_events_for_date(date_str)
        logger.info(f"Deleted {num_deleted_db} transit events from database for date: {date_str}")
    except Exception as e:
        logger.error(f"Error deleting transit events from database: {str(e)}")


def _get_events_for_date(date_str: str) -> List:
    """Get and validate events for a specific date"""
    events = db.get_events_for_date(date_str)
    
    # Filter events with locations and sort by start time
    events_with_location = [e for e in events if e.location]
    events_with_location.sort(key=lambda ev: ev.start_time)
    
    if not events_with_location:
        logger.info(f"No events with locations found for date: {date_str}")
        db.cleanup_orphaned_events_for_date(date_str)
        return []
    
    return events_with_location


def _calculate_and_validate_transit_duration(origin: str, destination: str, arrival_time) -> Optional[int]:
    """Calculate transit duration and validate against limits"""
    
    logger.info(f"Calculating transit time from '{origin}' to '{destination}'")
    
    transit_duration = calculate_transit_time(origin, destination, arrival_time)
    logger.info(f"Transit duration result: {transit_duration} seconds ({transit_duration/3600 if transit_duration else 'None'} hours)")
    
    if not transit_duration:
        logger.info("Skipping transit event - no transit duration calculated (API error or no route)")
        return None
    
    if transit_duration > config.MAX_TRANSIT_TIME_HOURS * 3600:
        logger.info(f"Skipping transit event - duration {transit_duration}s ({transit_duration/3600:.1f}h) exceeds {config.MAX_TRANSIT_TIME_HOURS}h limit")
        return None
    
    logger.info(f"Transit duration {transit_duration}s is within {config.MAX_TRANSIT_TIME_HOURS}h limit")
    return transit_duration


def _create_transit_event_data(title: str, origin: str, destination: str, start_time, end_time) -> dict:
    """Create transit event data dictionary"""
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "origin": origin,
        "destination": destination,
        "startTime": start_time.isoformat(),
        "endTime": end_time.isoformat()
    }


def _save_and_create_transit_event(transit_event: dict) -> None:
    """Save transit event to database and create on calendar"""
    db.save_transit_event(transit_event)
    calendar_service.create_transit_event(transit_event)


def _process_outbound_transit(last_location: str, last_event_name: str, current_event, current_title: str) -> None:
    """Process transit from previous location to current event location"""
    current_location = current_event.location
    transit_end_time = current_event.start_time
    
    if are_locations_similar(last_location, current_location):
        return
    
    transit_duration = _calculate_and_validate_transit_duration(
        last_location, current_location, transit_end_time
    )
    
    if not transit_duration:
        return
    
    # Round duration to nearest 15 minutes (900 seconds)
    rounded_transit_duration = (transit_duration // 900 + 1) * 900
    transit_start_time = transit_end_time - timedelta(seconds=rounded_transit_duration)

    # Create and save transit event
    transit_event = _create_transit_event_data(
        title=f"{last_event_name} > {current_title}",
        origin=last_location,
        destination=current_location,
        start_time=transit_start_time,
        end_time=transit_end_time
    )
    
    _save_and_create_transit_event(transit_event)


def _process_return_home_transit(current_event, current_title: str) -> None:
    """Process transit from current event location back to home"""
    current_location = current_event.location
    home_transit_start_time = current_event.end_time
    
    if are_locations_similar(current_location, config.HOME_ADDRESS):
        return
    
    home_transit_duration = _calculate_and_validate_transit_duration(
        current_location, config.HOME_ADDRESS, home_transit_start_time
    )
    
    if not home_transit_duration:
        return
    
    # Round duration to nearest 15 minutes
    rounded_home_transit_duration = (home_transit_duration // 900 + 1) * 900
    home_transit_end_time = home_transit_start_time + timedelta(seconds=rounded_home_transit_duration)

    # Create and save transit event
    transit_event = _create_transit_event_data(
        title=f"{current_title} > Home",
        origin=current_location,
        destination=config.HOME_ADDRESS,
        start_time=home_transit_start_time,
        end_time=home_transit_end_time
    )
    
    _save_and_create_transit_event(transit_event)


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
        # Clear existing transit events
        _clear_existing_transit_events(date_str)
        
        # Get events for the date
        events_with_location = _get_events_for_date(date_str)
        if not events_with_location:
            return

        # Process events to create transit events
        last_location = config.HOME_ADDRESS
        last_event_name = "Home"

        for i, current_event in enumerate(events_with_location):
            current_location = current_event.location
            current_title = "Home" if are_locations_similar(config.HOME_ADDRESS, current_location) else current_event.title
            
            # Process outbound transit (to the event)
            _process_outbound_transit(last_location, last_event_name, current_event, current_title)

            # Update tracking variables
            last_location = current_location
            last_event_name = current_title

            # Process return home transit if this is the last event of the day
            if i == len(events_with_location) - 1:
                _process_return_home_transit(current_event, current_title)

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