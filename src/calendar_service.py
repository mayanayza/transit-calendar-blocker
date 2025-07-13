import time
import uuid
from datetime import datetime, timedelta

import caldav
import config
import pytz
import vobject
from dateutil.parser import parse
from icalendar import Calendar, Event
from loguru import logger
from transit_service import get_apple_maps_url

from utils import safe_date_search


class CalendarService:
    def __init__(self):
        self.source_client = None
        self.source_calendar = None
        self.dest_client = None
        self.dest_calendar = None
        
    def initialize(self):
        """Initialize connections to calendars"""
        self._connect_source_calendar()
        self._connect_destination_calendar()
        
    def _connect_source_calendar(self):
        """Connect to source calendar"""
        try:
            logger.info(f"Connecting to source calendar: {config.SOURCE_CALENDAR_URL}")
            
            # Create client
            self.source_client = caldav.DAVClient(
                url=config.SOURCE_CALENDAR_URL,
                username=config.SOURCE_CALENDAR_USERNAME,
                password=config.SOURCE_CALENDAR_PASSWORD
            )
            
            # Use the provided URL directly instead of discovering calendars
            self.source_calendar = caldav.Calendar(
                client=self.source_client,
                url=config.SOURCE_CALENDAR_URL
            )
            
            # Verify the calendar exists by trying to get a property
            name = self.source_calendar.get_properties([caldav.dav.DisplayName()])
            logger.info(f"Connected to source calendar: {name}, {config.SOURCE_CALENDAR_URL}")
            
        except Exception as e:
            logger.error(f"Error connecting to source calendar: {str(e)}")
            raise

    def _connect_destination_calendar(self):
        """Connect to destination calendar"""
        try:
            logger.info(f"Connecting to destination calendar: {config.DESTINATION_CALENDAR_URL}")
            
            # Create client
            self.dest_client = caldav.DAVClient(
                url=config.DESTINATION_CALENDAR_URL,
                username=config.DESTINATION_CALENDAR_USERNAME,
                password=config.DESTINATION_CALENDAR_PASSWORD
            )
            
            # Use the provided URL directly instead of discovering calendars
            self.dest_calendar = caldav.Calendar(
                client=self.dest_client,
                url=config.DESTINATION_CALENDAR_URL
            )
            
            # Verify the calendar exists by trying to get a property
            name = self.dest_calendar.get_properties([caldav.dav.DisplayName()])
            logger.info(f"Connected to destination calendar: {name}, {config.DESTINATION_CALENDAR_URL}")
            
        except Exception as e:
            logger.error(f"Error connecting to destination calendar: {str(e)}")
            raise
    
    def fetch_events(self, start_date, end_date):
        """Fetch events from source calendar within a time range
        
        Args:
            start_date (datetime): Start date
            end_date (datetime): End date
            
        Returns:
            list: List of event dictionaries
        """
        if not self.source_calendar:
            self._connect_source_calendar()
            
        try:
            logger.info(f"Fetching events from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                        
            # FIXED: Use safe_date_search instead of date_search
            events = safe_date_search(
                self.source_calendar,
                start_date,
                end_date,
                expand=True
            )
                
            # Parse events to our internal format
            parsed_events = []
            for event in events:
                try:
                    event_data = self._parse_event(event)
                    if event_data:
                        if "notes" in event_data and "No location needed" in event_data["notes"]:
                            logger.debug(f"Skipping event: {event_data['title']} due to No location needed in notes")
                        elif event_data.get("location"):
                            parsed_events.append(event_data)
                            logger.debug(f"Added event with location: {event_data['title']} - {event_data['location']}")
                        else:
                            logger.debug(f"Event has no location: {event_data['title']}")
                except Exception as e:
                    logger.error(f"Error parsing specific event: {str(e)}")
            
            logger.info(f"Parsed {len(parsed_events)} events with locations")
            return parsed_events
            
        except Exception as e:
            logger.error(f"Error fetching events: {str(e)}")
            return []

    def fetch_recently_updated_events(self):
        """Fetch recently updated events
        
        Returns:
            list: List of event dictionaries
        """
        now = datetime.now()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=config.LOOK_FORWARD_DAYS)
        
        return self.fetch_events(start_date, end_date)
    
    def _parse_event(self, caldav_event):
        """Parse a CalDAV event to our internal format
        
        Args:
            caldav_event: A CalDAV event
            
        Returns:
            dict: Event data in our internal format
        """
        try:
            # Parse the iCalendar data
            vcal = vobject.readOne(caldav_event.data)
            vevent = vcal.vevent
            
            # Get event properties
            uid = str(vevent.uid.value) if hasattr(vevent, 'uid') else str(uuid.uuid4())
            summary = vevent.summary.value if hasattr(vevent, 'summary') else "No Title"
            location = vevent.location.value if hasattr(vevent, 'location') else ""
            
            # Get start and end times
            if hasattr(vevent, 'dtstart'):
                dtstart = vevent.dtstart.value
                # Skip all-day events as they're not relevant for transit
                if not isinstance(dtstart, datetime):
                    return None
                start_time = dtstart
            else:
                return None
                
            if hasattr(vevent, 'dtend'):
                dtend = vevent.dtend.value
                # Skip all-day events as they're not relevant for transit
                if not isinstance(dtend, datetime):
                    return None
                end_time = dtend
            else:
                # If no end time, use start time + 1 hour
                end_time = start_time + timedelta(hours=1)
            
            # Ensure timezone awareness
            if start_time.tzinfo is None:
                start_time = pytz.utc.localize(start_time)
            if end_time.tzinfo is None:
                end_time = pytz.utc.localize(end_time)
                
            # Create event data
            event_data = {
                "id": uid,
                "title": summary,
                "location": location,
                "startTime": start_time.isoformat(),
                "endTime": end_time.isoformat(),
                "calendarId": str(self.source_calendar.url)
            }
            
            return event_data
            
        except Exception as e:
            logger.error(f"Error parsing event: {str(e)}")
            return None
    
    def create_transit_event(self, transit_event):
        """Create a transit event on the destination calendar
        
        Args:
            transit_event (dict): Transit event data
            
        Returns:
            bool: Success or failure
        """
        if not self.dest_calendar:
            self._connect_destination_calendar()
            
        try:
            # Create iCalendar event
            cal = Calendar()
            cal.add('prodid', '-//Transit Calendar//EN')
            cal.add('version', '2.0')
            
            event = Event()
            event.add('uid', transit_event['id'])
            event.add('summary', transit_event['title'])
            
            # Create Apple Maps link in description
            apple_maps_url = get_apple_maps_url(
                transit_event['origin'],
                transit_event['destination']
            )
            
            # Set description with Apple Maps link
            event.add('description', f"{apple_maps_url}")
            
            # Add start and end times
            start_time = parse(transit_event['startTime'])
            end_time = parse(transit_event['endTime'])
            
            event.add('dtstart', start_time)
            event.add('dtend', end_time)
            
            # Add to calendar
            cal.add_component(event)
            
            # Create calendar object
            ical_str = cal.to_ical()
            
            # Save to destination calendar
            self.dest_calendar.save_event(ical_str)
            
            logger.info(f"Created transit event: {transit_event['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating transit event: {str(e)}")
            return False
    
    def delete_transit_events_for_date(self, date):
        """Delete transit events for a specific date
        
        Args:
            date (datetime or str): The date to delete events for
            
        Returns:
            int: Number of events deleted
        """
        if not self.dest_calendar:
            self._connect_destination_calendar()
            
        try:
            # Convert to datetime if needed
            if isinstance(date, str):
                date = datetime.strptime(date, '%Y-%m-%d')
                    
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            logger.debug(f"Searching for events to delete between {start_of_day} and {end_of_day}")
            
            events = safe_date_search(
                self.dest_calendar,
                start_of_day,
                end_of_day,
                expand=True
            )
            
            logger.debug(f"Found {len(events)} events to delete")
            
            # Delete each event
            count = 0
            for event in events:
                try:
                    # Get event summary for logging
                    try:
                        vcal = vobject.readOne(event.data)
                        vevent = vcal.vevent
                        summary = vevent.summary.value if hasattr(vevent, 'summary') else "No Title"
                    except Exception as e:
                        logger.error(f"Error getting event summary: {str(e)}")
                        summary = "Unknown"
                    
                    logger.debug(f"Deleting event: {summary}")
                    
                    # Delete the event
                    event.delete()
                    
                    # Wait briefly to allow server to process the deletion
                    time.sleep(0.5)
                    
                    count += 1
                    logger.debug(f"Successfully deleted event: {summary}")
                except Exception as e:
                    logger.error(f"Error deleting specific event: {str(e)}")
                    
            logger.info(f"Deleted {count} transit events for date {date.strftime('%Y-%m-%d')}")
            return count
                
        except Exception as e:
            logger.error(f"Error deleting transit events: {str(e)}")
            return 0

# Create a singleton instance
calendar_service = CalendarService()