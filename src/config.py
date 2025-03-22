import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Calendar settings
SOURCE_CALENDAR_URL = os.getenv('SOURCE_CALENDAR_URL')
SOURCE_CALENDAR_USERNAME = os.getenv('SOURCE_CALENDAR_USERNAME')
SOURCE_CALENDAR_PASSWORD = os.getenv('SOURCE_CALENDAR_PASSWORD')

DESTINATION_CALENDAR_URL = os.getenv('DESTINATION_CALENDAR_URL')
DESTINATION_CALENDAR_USERNAME = os.getenv('DESTINATION_CALENDAR_USERNAME')
DESTINATION_CALENDAR_PASSWORD = os.getenv('DESTINATION_CALENDAR_PASSWORD')

# HERE API settings
HERE_API_KEY = os.getenv('HERE_API_KEY')

# Home location and transit defaults
HOME_ADDRESS = os.getenv('HOME_ADDRESS')
DEFAULT_TRANSIT_MODE = os.getenv('DEFAULT_TRANSIT_MODE', 'transit')  # transit, driving, walking, cycling

# Time settings
LOOK_FORWARD_DAYS = int(os.getenv('LOOK_FORWARD_DAYS', '28'))
CALENDAR_CHECK_INTERVAL = int(os.getenv('CALENDAR_CHECK_INTERVAL', '15'))
DAILY_UPDATE_TIME = os.getenv('DAILY_UPDATE_TIME', '01:00')
DAILY_UPDATE_HOUR, DAILY_UPDATE_MINUTE = map(int, DAILY_UPDATE_TIME.split(':'))

# Maximum transit time (hours) - don't create transit events longer than this
MAX_TRANSIT_TIME_HOURS = int(os.getenv('MAX_TRANSIT_TIME_HOURS', '3'))

# Database
DB_PATH = os.getenv('DB_PATH', './data/transit-calendar.sqlite')

# Ensure data directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# Database URL
DB_URL = f"sqlite:///{DB_PATH}"

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', './data/transit-calendar.log')