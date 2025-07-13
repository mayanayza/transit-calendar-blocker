# Transit Calendar Blocker

A Python application that automatically creates transit events in your calendar by monitoring your existing calendar events and calculating travel times between locations.

## Overview

Transit Calendar watches your source calendar for events with locations and automatically creates corresponding travel time events in a destination calendar. It calculates realistic travel times using the HERE Maps API and creates Apple Maps links for easy navigation.

### How It Works

1. **Event Monitoring**: The application periodically checks your source calendar for events with locations
2. **Change Detection**: Uses content hashing to detect when events have actually changed (ie new location) and need corresponding transit event to be updated
3. **Travel Time Calculation**: For each event, calculates travel time from the previous location using HERE Maps API
4. **Transit Event Creation**: Creates appropriately timed transit events in your destination calendar
5. **Apple Maps Links**: Each transit event includes an Apple Maps link for easy navigation

## Installation

### Requirements

- Python 3.10+
- HERE Maps API key
- CalDAV-compatible calendars (source and destination)
- Docker (optional, for containerized deployment)

### Option 1: Docker (Recommended)

1. Clone the repository
2. Create a `.env` file with your configuration (see Configuration section)
3. Run with Docker Compose:

```bash
cd src
docker-compose up -d
```

### Option 2: Local Installation

1. Clone the repository
2. Install dependencies:

```bash
cd src
pip install -r requirements.txt
```

3. Create a `.env` file with your configuration
4. Run the application:

```bash
python main.py
```

## Configuration

Create a `.env` file in the `src` directory with the following variables:

### Required Settings

```env
# Source Calendar (where your events are)
SOURCE_CALENDAR_URL=https://your-calendar-server.com/path/to/calendar
SOURCE_CALENDAR_USERNAME=your-username
SOURCE_CALENDAR_PASSWORD=your-password

# Destination Calendar (where transit events will be created)
DESTINATION_CALENDAR_URL=https://your-calendar-server.com/path/to/transit-calendar
DESTINATION_CALENDAR_USERNAME=your-username
DESTINATION_CALENDAR_PASSWORD=your-password

# HERE Maps API Key
HERE_API_KEY=your-here-api-key

# Home Address (starting/ending point for daily travel)
HOME_ADDRESS=123 Main St, Your City, State, ZIP
```

### Optional Settings

```env
# Transport mode: transit, driving, walking, cycling
DEFAULT_TRANSIT_MODE=transit

# How many days ahead to process
LOOK_FORWARD_DAYS=28

# How often to check for calendar updates (minutes)
CALENDAR_CHECK_INTERVAL=15

# Daily update time (HH:MM format)
DAILY_UPDATE_TIME=01:00

# Maximum transit time to create events for (hours)
MAX_TRANSIT_TIME_HOURS=3

# Logging level
LOG_LEVEL=INFO
```

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review application logs
3. Create an issue in the repository with:
   - Error messages
   - Configuration (without sensitive data)
   - Steps to reproduce

## Architecture

### Files

- **Calendar Service** (`calendar_service.py`): Handles CalDAV connections and event management
- **Transit Service** (`transit_service.py`): Calculates travel times using HERE Maps API
- **Database** (`database.py`): SQLite database for event tracking and change detection
- **Scheduler** (`scheduler.py`): Manages periodic calendar checks and daily updates
- **Main Application** (`main.py`): Entry point and scheduler setup

### Processing Logic

- Events without locations are ignored
- Travel times are rounded up to the nearest 15-minute interval
- The application creates transit events both to and from your home address
- Transit events longer than the configured maximum are not created

### Integrations

#### HERE Maps API

The application uses HERE Maps APIs for:
- **Geocoding**: Converting addresses to coordinates
- **Transit Routing**: Calculating travel times and routes
- **Multiple Transport Modes**: Supporting public transit, driving, walking, and cycling

To get a HERE API key:
1. Sign up at [developer.here.com](https://developer.here.com)
2. Create a new project
3. Generate an API key with Geocoding and Transit API access

#### CalDAV

The application works with any CalDAV-compatible calendar service, such as:
- Apple iCloud (with app-specific passwords)
- Google Calendar (via CalDAV)
- [Forward Email](forwardemail.net)
- Any RFC 4791 compliant CalDAV server

### Database

The application uses SQLite to store:
- **Events**: Full event details from your source calendar
- **Transit Events**: Generated transit events
- **Processed Events**: Hash-based change tracking to avoid unnecessary updates

The database is automatically created and managed by the application.

### Scheduling

The application runs several scheduled jobs:

- **Calendar Check**: Runs every 15 minutes (configurable) to check for calendar updates
- **Daily Update**: Runs daily at 1:00 AM (configurable) to process events for the next date in the look forward window
- **Weekly Cleanup**: Runs weekly to remove old data from database

### Logging

The application provides comprehensive logging:
- Event processing details
- API call results
- Error handling and debugging information
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)

Logs are written to both console and file (`data/transit-calendar.log`).

### Debug

Set `LOG_LEVEL=DEBUG` in your environment to get detailed logging information.