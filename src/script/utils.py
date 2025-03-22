import uuid
from datetime import timedelta


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