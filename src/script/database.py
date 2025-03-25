import os
from datetime import datetime
from pathlib import Path

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
        
        # Set permissions to ensure it's writable
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
        existing_tables = inspector.get_table_names()
        
        # Create all tables that don't exist
        Base.metadata.create_all(engine)
        
        logger.info(f"Database initialized with tables: {', '.join(inspector.get_table_names())}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        return False

# Rest of the database.py file remains unchanged...