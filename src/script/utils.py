import uuid
from datetime import timedelta, datetime

import pytz
import vobject
from loguru import logger


def generate_unique_id():
    """Generate a unique ID
    
    Returns:
        str: Unique ID
    """
    return str(uuid.uuid4())

def round_up_to_interval(date, interval_minutes):
    """Round a datetime up to the nearest interval
    
    Args:
        date (datetime): Date to round
        interval_minutes (int): Interval in minutes
        
    Returns:
        datetime: Rounded date
    """
    minutes = (date.hour * 60 + date.minute)
    remainder = minutes % interval_minutes
    
    if remainder == 0:
        return date
    
    return date + timedelta(minutes=interval_minutes - remainder)


def safe_date_search(calendar, start_date, end_date, expand=True):
    """
    Safe replacement for calendar.date_search() that avoids cache bugs.

    This method uses calendar.events() + manual filtering instead of date_search()
    to avoid the cache bug where date_search() returns stale data after deletions.

    Args:
        calendar: CalDAV calendar object
        start_date (datetime): Start date for search
        end_date (datetime): End date for search
        expand (bool): Ignored (kept for API compatibility)

    Returns:
        list: List of CalDAV event objects within the date range
    """
    try:
        # Get all events from the calendar (this method doesn't have the cache bug)
        all_events = calendar.events()

        # Ensure our comparison dates are timezone-aware
        search_start = start_date if start_date.tzinfo is not None else pytz.utc.localize(start_date)
        search_end = end_date if end_date.tzinfo is not None else pytz.utc.localize(end_date)

        # Filter events that fall within the date range
        filtered_events = []

        for event in all_events:
            try:
                # Parse the event to get its start time
                vcal = vobject.readOne(event.data)
                vevent = vcal.vevent

                if not hasattr(vevent, 'dtstart'):
                    continue

                dtstart = vevent.dtstart.value

                # Skip all-day events (they're date objects, not datetime)
                if not isinstance(dtstart, datetime):
                    continue

                # Ensure timezone awareness for comparison
                event_start = dtstart if dtstart.tzinfo is not None else pytz.utc.localize(dtstart)

                # Check if event falls within the date range
                if search_start <= event_start <= search_end:
                    filtered_events.append(event)

            except Exception as e:
                # Log the error but continue processing other events
                logger.debug(f"Error filtering event in safe_date_search: {str(e)}")
                continue

        return filtered_events

    except Exception as e:
        logger.error(f"Error in safe_date_search: {str(e)}")
        # Fallback to original date_search if everything fails
        # (though this may return stale data)
        try:
            return calendar.date_search(start=start_date, end=end_date, expand=expand)
        except Exception as fallback_error:
            logger.error(f"Fallback date_search also failed: {str(fallback_error)}")
            return []