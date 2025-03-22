from datetime import datetime, timedelta

import config
from loguru import logger
from sqlalchemy import Column, DateTime, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Create database engine
engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False},
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

# Create a session factory
Session = sessionmaker(bind=engine)

def initialize_db():
    """Initialize the database by creating all tables"""
    logger.info("Initializing database")
    Base.metadata.create_all(engine)

def save_event(event_data):
    """Store an event in the database
    
    Args:
        event_data (dict): Event data including id, title, location, startTime, endTime, calendarId
        
    Returns:
        str: The date of the event in YYYY-MM-DD format
    """
    session = Session()
    
    try:
        # Parse datetime objects
        start_time = datetime.fromisoformat(event_data["startTime"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(event_data["endTime"].replace("Z", "+00:00"))
        
        # Format date as YYYY-MM-DD
        date_str = start_time.strftime('%Y-%m-%d')
        
        # Check if event exists
        existing_event = session.query(Event).filter(Event.id == event_data["id"]).first()
        
        if existing_event:
            # Update existing event
            existing_event.title = event_data["title"]
            existing_event.location = event_data.get("location", "")
            existing_event.start_time = start_time
            existing_event.end_time = end_time
            existing_event.date = date_str
            existing_event.updated_at = datetime.now()
        else:
            # Create new event
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
        return date_str
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving event: {str(e)}")
        raise
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
        
        session.commit()
        logger.info(f"Cleaned up data older than {cutoff_date}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error cleaning up old data: {str(e)}")
    finally:
        session.close()