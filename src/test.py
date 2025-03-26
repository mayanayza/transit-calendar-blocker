import traceback
from datetime import datetime, timedelta

import caldav


def list_upcoming_events(caldav_url, username, password):
    """
    Retrieve and list events happening in the next 7 days from a CalDAV calendar.
    
    :param caldav_url: URL of the CalDAV server
    :param username: Authentication username
    :param password: Authentication password
    """
    try:
        # Establish connection to the CalDAV server
        client = caldav.DAVClient(url=caldav_url, username=username, password=password)
        
        # Get the principal (main calendar account)
        principal = client.principal()
        
        # Get all calendars for this principal
        calendars = principal.calendars()
        
        if not calendars:
            print("No calendars found.")
            return
        
        # Use the first calendar (you can modify if needed)
        calendar = calendars[0]
        
        # Define date range for next 7 days
        now = datetime.now()
        week_later = now + timedelta(days=7)
        
        # Retrieve events
        events = calendar.date_search(start=now, end=week_later)
        
        # Print event details
        print(f"Found {len(events)} events in the next 7 days:")
        for event in events:
            # Parse the event
            event_obj = event.instance.vevent
            
            # Extract summary and start date
            summary = event_obj.summary.value if event_obj.summary else "Untitled Event"
            start_date = event_obj.dtstart.value
            
            print(f"Event: {summary}")
            print(f"Date: {start_date}")
            print("---")
    
    except Exception:
        print("An error occurred:")
        print(traceback.format_exc())

def main():
    # Replace these with your actual CalDAV server details
    CALDAV_URL = "https://caldav.forwardemail.net/dav/tester@maya.cloud/f8334fe7-56ff-4c51-b98f-48fff505f843/"
    USERNAME = "tester@maya.cloud"
    PASSWORD = "c59e773d0f44b9f4b36252ee"
    
    list_upcoming_events(CALDAV_URL, USERNAME, PASSWORD)

if __name__ == "__main__":
    main()