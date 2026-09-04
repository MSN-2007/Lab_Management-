import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'robolab-super-secret-key-2026')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    # Database settings - MySQL by default
    # Change these credentials to match your local MySQL configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
    DB_NAME = os.getenv('DB_NAME', 'robotics_lab')
    
    # Dual-mode capability: If MySQL is not running locally, auto-fallback to SQLite
    # to allow immediate running and UI testing without blocking the user.
    AUTO_FALLBACK_SQLITE = os.getenv('AUTO_FALLBACK_SQLITE', 'True') == 'True'
    SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'robolab.db')
