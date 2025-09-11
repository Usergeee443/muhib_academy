import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

class Config:
    # Database Configuration - SQLite
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'muhib_academy.db')
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'muhib-academy-secret-key-2024')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID_HERE')
    
    # Database URL
    @property
    def DATABASE_URL(self):
        return f"sqlite:///{self.DATABASE_PATH}"




