import re

import config
import requests
from loguru import logger
from datetime import datetime


def calculate_transit_time(origin, destination, arrival_time):
    """Calculate transit time between two locations using HERE Transit API
    
    Args:
        origin (str): Origin address
        destination (str): Destination address
        arrival_time (datetime): Arrival time
        
    Returns:
        int: Transit time in seconds or None if calculation failed
    """
    try:
        # Normalize address format
        origin = normalize_address(origin)
        destination = normalize_address(destination)
        
        # Convert addresses to coordinates
        origin_coords = geocode_address(origin)
        dest_coords = geocode_address(destination)
        
        if not origin_coords or not dest_coords:
            logger.error("Failed to geocode one or both addresses")
            return None
        
        # Format the arrival time for HERE API (ISO 8601)
        arrival_time_iso = arrival_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Prepare HERE Transit API request
        url = "https://transit.router.hereapi.com/v8/routes"
        params = {
            'apiKey': config.HERE_API_KEY,
            'origin': f"{origin_coords[1]},{origin_coords[0]}",  # HERE uses lat,lon format
            'destination': f"{dest_coords[1]},{dest_coords[0]}",
            'arrival': arrival_time_iso,
            'return': 'travelSummary'
        }
        
        # Add transit mode preference if specified
        if config.DEFAULT_TRANSIT_MODE == 'transit':
            # For public transit, no additional parameters needed
            pass
        elif config.DEFAULT_TRANSIT_MODE == 'driving':
            params['transportMode'] = 'car'
        elif config.DEFAULT_TRANSIT_MODE == 'walking':
            params['transportMode'] = 'pedestrian'
        elif config.DEFAULT_TRANSIT_MODE == 'cycling':
            params['transportMode'] = 'bicycle'
        
        # Make API request
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if we have routes
            if 'routes' in data and len(data['routes']) > 0:
                route = data['routes'][0]
                
                # Get the travel summary
                if 'sections' in route and len(route['sections']) > 0:
                    total_duration = 0
                    for section in route['sections']:
                        if 'travelSummary' in section:
                            total_duration += section['travelSummary'].get('duration', 0)
                    
                    # Return duration in seconds
                    return total_duration
            
            logger.warning("No routes found in HERE Transit API response")
            return None
        else:
            logger.error(f"Error from HERE Transit API: {response.status_code} - {response.text}")
            return None
        
    except Exception as e:
        logger.error(f"Error calculating transit time with HERE Transit API: {str(e)}")
        return None

def normalize_address(address):
    """Normalize address format for geocoding
    
    Args:
        address (str): Address in any format
        
    Returns:
        str: Normalized address
    """
    if not address:
        return ""
        
    # Replace newlines with commas
    address = re.sub(r'\r?\n', ', ', address)
    
    # Replace multiple spaces with single space
    address = re.sub(r'\s+', ' ', address)
    
    # Replace multiple commas with a single comma
    address = re.sub(r',+', ',', address)
    
    # Replace comma+space with just comma
    address = re.sub(r',\s+', ',', address)
    
    # Remove leading/trailing commas and spaces
    address = address.strip(' ,')
    
    return address

def get_apple_maps_url(origin, destination):
    """Create an Apple Maps URL for directions
    
    Args:
        origin (str): Origin address
        destination (str): Destination address
        
    Returns:
        str: Apple Maps URL
    """
    # Normalize addresses
    origin = normalize_address(origin)
    destination = normalize_address(destination)
    
    # Encode for URL
    encoded_origin = requests.utils.quote(origin)
    encoded_destination = requests.utils.quote(destination)
    
    # Create Apple Maps URL
    url = f"http://maps.apple.com/?saddr={encoded_origin}&daddr={encoded_destination}"
    
    return url

def geocode_address(address):
    """Geocode an address to coordinates using HERE Geocoding API
    
    Args:
        address (str): Address to geocode
        
    Returns:
        list: [longitude, latitude] or None if geocoding failed
    """
    try:
        # Prepare HERE Geocoding API request
        url = "https://geocode.search.hereapi.com/v1/geocode"
        params = {
            'apiKey': config.HERE_API_KEY,
            'q': address,
            'limit': 1
        }
        
        # Make API request
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if we have items
            if 'items' in data and len(data['items']) > 0:
                position = data['items'][0]['position']
                # Return as [longitude, latitude] to match expected format
                return [position['lng'], position['lat']]
            
            logger.warning(f"No geocoding results found for address '{address}'")
            return None
        else:
            logger.error(f"Error from HERE Geocoding API: {response.status_code} - {response.text}")
            return None
        
    except Exception as e:
        logger.error(f"Error geocoding address '{address}': {str(e)}")
        return None

def are_locations_similar(location1, location2):
    """Check if two locations are similar
    
    Args:
        location1 (str): First location
        location2 (str): Second location
        
    Returns:
        bool: True if locations are similar, False otherwise
    """
    if not location1 or not location2:
        return False
    
    standardized1 = standardize_location(location1)
    standardized2 = standardize_location(location2)
    
    return standardized1 in standardized2 or standardized2 in standardized1

def standardize_location(location):
    """Standardize a location string for comparison
    
    Args:
        location (str): Location string
        
    Returns:
        str: Standardized location string
    """
    # Normalize the address first
    location = normalize_address(location)
    
    # Convert to lowercase
    result = location.lower()
    
    # Remove whitespace
    result = re.sub(r'\s+', '', result)
    
    # Remove non-alphanumeric characters
    result = re.sub(r'[^a-z0-9]', '', result)
    
    # Standardize common abbreviations
    replacements = {
        r'\bst\b': 'street',
        r'\bave\b': 'avenue',
        r'\bblvd\b': 'boulevard',
        r'\bdr\b': 'drive',
        r'\bct\b': 'court',
        r'\brd\b': 'road',
        r'\bln\b': 'lane',
        r'\bapt\b': 'apartment',
        r'\bsuite\b': 'suite',
        r'\bpkwy\b': 'parkway',
        r'\bpl\b': 'place',
        r'\btrl\b': 'trail',
        r'\bcir\b': 'circle',
        r'\bway\b': 'way',
        r'\bbldg\b': 'building',
        r'\bfwy\b': 'freeway'
    }
    
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result)
    
    return result