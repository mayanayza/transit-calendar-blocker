import hashlib
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set
from typing_extensions import Buffer, cast

import config
from loguru import logger
from sqlalchemy import Column, DateTime, String, create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def ensure_db_directory():
    """Ensure the database directory exists with proper permissions"""
    db_dir = os.path.dirname(config.DB_PATH)

    try:
        # Create directory with parents if it doesn't exist
        Path(db_dir).mkdir(parents=True, exist_ok=True)

        # Set permissions to ensure it is writable
        # In Docker this might be redundant but helps with debugging
        os.chmod(db_dir, 0o755)

        # Verify we can actually write to this location
        test_file = os.path.join(db_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info(f"Successfully verified write access to {db_dir}")

        return True
    except Exception as e:
        logger.error(f"Failed to create or access database directory: {str(e)}")
        logger.error(f"DB directory: {db_dir}, current working dir: {os.getcwd()}")
        logger.error(f"Directory listing: {os.listdir(os.getcwd())}")
        return False


# Ensure DB directory exists before engine creation
ensure_db_directory()

# Create database engine with more robust connection handling
engine = create_engine(
    config.DB_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # More generous timeout
    },
    poolclass=StaticPool,
    echo=False
)

# Create base class for models
Base = declarative_base()


# Define models
class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    title = Column(String)
    location = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    date = Column(String)  # YYYY-MM-DD format
    calendar_id = Column(String)
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Event(id='{self.id}', title='{self.title}', date='{self.date}')>"


class TransitEvent(Base):
    __tablename__ = "transit_events"

    id = Column(String, primary_key=True)
    title = Column(String)
    origin = Column(String)
    destination = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    date = Column(String)  # YYYY-MM-DD format
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<TransitEvent(id='{self.id}', title='{self.title}', date='{self.date}')>"


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id = Column(String, primary_key=True)
    title = Column(String)
    location = Column(String)
    date = Column(String)  # YYYY-MM-DD format
    hash_value = Column(String)  # Hash of relevant fields to detect changes
    last_processed = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<ProcessedEvent(id='{self.id}', title='{self.title}', date='{self.date}')>"


# Create a session factory
Session = sessionmaker(bind=engine)


def initialize_db():
    """Initialize the database by creating all tables"""
    logger.info("Initializing database")

    # Ensure the DB directory exists before trying to create tables
    if not ensure_db_directory():
        logger.error("Cannot initialize database: directory setup failed")
        return False

    try:
        # Check if we need to migrate the database
        inspector = inspect(engine)

        # Create all tables that don't exist
        Base.metadata.create_all(engine)

        logger.info(f"Database initialized with tables: {', '.join(inspector.get_table_names())}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        return False


def save_event(event_data):
    """Store an event in the database and check if it has changed

    Args:
        event_data (dict): Event data including id, title, location, startTime, endTime, calendarId

    Returns:
        tuple: (date_str, event_changed) where:
            - date_str (str): The date of the event in YYYY-MM-DD format
            - event_changed (bool): True if event was updated, False if unchanged
    """
    # Parse datetime objects
    start_time = datetime.fromisoformat(event_data["startTime"].replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(event_data["endTime"].replace("Z", "+00:00"))

    # Format date as YYYY-MM-DD
    date_str = start_time.strftime('%Y-%m-%d')

    # Step 1: Save the full event data to the Events table
    update_event_record(event_data, start_time, end_time, date_str)

    # Step 2: Check if the event has changed since last processing
    event_changed = check_event_changes(event_data, start_time, date_str)

    return date_str, event_changed


def update_event_record(event_data, start_time, end_time, date_str):
    """Update or create a record in the Events table

    Args:
        event_data (dict): Event data
        start_time (datetime): Parsed start time
        end_time (datetime): Parsed end time
        date_str (str): Formatted date string
    """
    session = Session()

    try:
        # Check if event exists in Events table
        existing_event = session.query(Event).filter(Event.id == event_data["id"]).first()

        if existing_event:
            # Update existing event record
            logger.debug(f"Updating existing event record for {event_data['id']}")
            existing_event.title = event_data["title"]
            existing_event.location = event_data.get("location", "")
            existing_event.start_time = start_time
            existing_event.end_time = end_time
            existing_event.date = date_str
            existing_event.updated_at = datetime.now()
        else:
            # Create new event record
            logger.debug(f"Creating new event record for {event_data['id']}")
            new_event = Event(
                id=event_data["id"],
                title=event_data["title"],
                location=event_data.get("location", ""),
                start_time=start_time,
                end_time=end_time,
                date=date_str,
                calendar_id=event_data["calendarId"],
                updated_at=datetime.now()
            )
            session.add(new_event)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating event record: {str(e)}")
        raise
    finally:
        session.close()


@contextmanager
def get_session():
    session = Session()
    try:
        yield session
    finally:
        session.close()


def check_event_changes(event_data, start_time, date_str):
    """Check if an event has changed since it was last processed

    Args:
        event_data (dict): Event data
        start_time (datetime): Parsed start time
        date_str (str): Formatted date string

    Returns:
        bool: True if event changed or is new, False if unchanged
    """

    with get_session() as session:
        try:
            # Create hash value for change detection
            # We only care about title, location and start_time for transit purposes
            hash_input = f"{event_data['title']}|{event_data.get('location', '')}|{start_time.isoformat()}"
            hash_value = hashlib.md5(cast(Buffer, hash_input.encode())).hexdigest()

            # Check if we've processed this event before
            processed_event = session.query(ProcessedEvent).filter(ProcessedEvent.id == event_data["id"]).first()

            if not processed_event:
                # This is a new event we haven't seen before
                logger.debug(f"New event {event_data['id']} being processed for the first time")

                # Create new processed event record
                new_processed_event = ProcessedEvent(
                    id=event_data["id"],
                    title=event_data["title"],
                    location=event_data.get("location", ""),
                    date=date_str,
                    hash_value=hash_value,
                    last_processed=datetime.now()
                )
                session.add(new_processed_event)
                session.commit()

                # New events always need processing
                return True
            else:
                # We've seen this event before, check if it changed
                if processed_event.hash_value == hash_value:
                    # Hash hasn't changed, event details relevant to transit are unchanged
                    logger.debug(f"Event {event_data['id']} unchanged since last processing")
                    return False
                else:
                    # Event has changed, update the processed event record
                    logger.debug(f"Event {event_data['id']} changed since last processing")
                    processed_event.title = event_data["title"]
                    processed_event.location = event_data.get("location", "")
                    processed_event.date = date_str
                    processed_event.hash_value = hash_value
                    processed_event.last_processed = datetime.now()
                    session.commit()
                    return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error checking event changes: {str(e)}")
            # If there's an error, return True to ensure processing happens
            return True


def detect_deleted_events(current_event_ids: Set[str]) -> Set[str]:
    """Detect events that have been deleted from the source calendar

    Args:
        current_event_ids (Set[str]): Set of event IDs currently in the calendar

    Returns:
        Set[str]: Set of date strings (YYYY-MM-DD) that had events deleted
    """
    session = Session()
    dates_with_deletions = set()

    try:
        # Get the date range we care about (today + look forward days)
        now = datetime.now()
        start_date = now.strftime('%Y-%m-%d')
        end_date = (now + timedelta(days=config.LOOK_FORWARD_DAYS)).strftime('%Y-%m-%d')

        # Find all events in our database within the date range
        stored_events = session.query(Event).filter(
            Event.date >= start_date,
            Event.date <= end_date
        ).all()

        # Check which stored events are no longer in the current calendar
        for stored_event in stored_events:
            if stored_event.id not in current_event_ids:
                logger.info(f"Detected deleted event: {stored_event.title} on {stored_event.date}")
                dates_with_deletions.add(stored_event.date)

                # Remove the event from our database
                session.delete(stored_event)

                # Also remove from processed events to clean up
                processed_event = session.query(ProcessedEvent).filter(
                    ProcessedEvent.id == stored_event.id
                ).first()
                if processed_event:
                    session.delete(processed_event)

        session.commit()

        if dates_with_deletions:
            logger.info(f"Found deletions on {len(dates_with_deletions)} dates: {sorted(dates_with_deletions)}")

        return dates_with_deletions

    except Exception as e:
        session.rollback()
        logger.error(f"Error detecting deleted events: {str(e)}")
        return set()
    finally:
        session.close()


def cleanup_orphaned_events_for_date(date_str: str):
    """Clean up any orphaned event records for a specific date

    This removes events from our database that are no longer in the calendar
    for the given date.

    Args:
        date_str (str): Date in YYYY-MM-DD format
    """
    session = Session()

    try:
        # Remove any remaining event records for this date
        # (These would be events that were deleted from calendar but are still in our DB)
        deleted_count = session.query(Event).filter(Event.date == date_str).delete()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} orphaned event records for date {date_str}")

        session.commit()

    except Exception as e:
        session.rollback()
        logger.error(f"Error cleaning up orphaned events for date {date_str}: {str(e)}")
    finally:
        session.close()


def get_events_for_date(date):
    """Get all events for a specific date

    Args:
        date (str or datetime): The date to get events for

    Returns:
        list: List of Event objects
    """
    session = Session()

    try:
        if isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = date

        events = session.query(Event).filter(Event.date == date_str).order_by(Event.start_time).all()
        return events
    finally:
        session.close()


def save_transit_event(transit_event):
    """Store a transit event

    Args:
        transit_event (dict): Transit event data
    """
    session = Session()

    try:
        # Parse datetime objects
        start_time = datetime.fromisoformat(transit_event["startTime"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(transit_event["endTime"].replace("Z", "+00:00"))

        # Format date as YYYY-MM-DD
        date_str = start_time.strftime('%Y-%m-%d')

        # Create new transit event
        new_transit_event = TransitEvent(
            id=transit_event["id"],
            title=transit_event["title"],
            origin=transit_event["origin"],
            destination=transit_event["destination"],
            start_time=start_time,
            end_time=end_time,
            date=date_str,
            created_at=datetime.now()
        )

        session.add(new_transit_event)
        session.commit()

    except Exception as e:
        session.rollback()
        logger.error(f"Error saving transit event: {str(e)}")
        raise
    finally:
        session.close()


def get_transit_events_for_date(date):
    """Get transit events for a specific date

    Args:
        date (str or datetime): The date to get events for

    Returns:
        list: List of TransitEvent objects
    """
    session = Session()

    try:
        if isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = date

        transit_events = session.query(TransitEvent).filter(TransitEvent.date == date_str).all()
        return transit_events
    finally:
        session.close()


def delete_transit_events_for_date(date):
    """Delete all transit events for a specific date

    Args:
        date (str or datetime): The date to delete events for

    Returns:
        int: Number of events deleted
    """
    session = Session()

    try:
        if isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = date

        result = session.query(TransitEvent).filter(TransitEvent.date == date_str).delete()
        session.commit()
        return result
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting transit events: {str(e)}")
        raise
    finally:
        session.close()


def cleanup_old_data(days=7):
    """Clean up data older than specified days

    Args:
        days (int): Number of days to keep
    """
    session = Session()

    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Delete old events
        session.query(Event).filter(Event.date < cutoff_date).delete()

        # Delete old transit events
        session.query(TransitEvent).filter(TransitEvent.date < cutoff_date).delete()

        # We keep ProcessedEvent records longer to avoid reprocessing
        # when events reappear due to recurrence

        session.commit()
        logger.info(f"Cleaned up data older than {cutoff_date}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error cleaning up old data: {str(e)}")
    finally:
        session.close()