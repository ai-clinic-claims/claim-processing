import os
import sys
from dotenv import load_dotenv

# Add the src directory to Python path
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

load_dotenv()

class Settings:
    # Email Configuration - Fixed: Only one default value per getenv()
    EMAIL_USER = os.getenv('EMAIL_USER', 'kellynyachiro@gmail.com')  # Fixed: removed second default
    
    # If you want to support multiple receiver emails, do it like this:
    EMAIL_USERS = os.getenv('EMAIL_USERS', 'kellynyachiro@gmail.com').split(',')
    
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'gytq ugan ofeh sbip')
    
    # Updated: Support multiple sender emails
    TARGET_SENDER_EMAILS = os.getenv('TARGET_SENDER_EMAILS', 'Daphneymaebawork@gmail.com').split(',')
    
    IMAP_SERVER = 'imap.gmail.com'
    IMAP_PORT = 993
    
    # Gemini API Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
    GEMINI_MAX_TOKENS = int(os.getenv('GEMINI_MAX_TOKENS', '100000'))
    
    # Base directory setup
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    
    # Storage paths for different types of files
    PROCESSED_EMAILS_DIR = os.path.join(DATA_DIR, 'processed_emails')
    COMPILED_PDFS_DIR = os.path.join(DATA_DIR, 'compiled_pdfs')
    PROCESSING_QUEUE_DIR = os.path.join(DATA_DIR, 'processing_queue')
    PROCESSED_CLAIMS_DIR = os.path.join(DATA_DIR, 'processed_claims')
    REPORTS_DIR = os.path.join(DATA_DIR, 'reports')
    RAW_ATTACHMENTS_DIR = os.path.join(DATA_DIR, 'raw_attachments')
    FRAUD_ANALYSIS_DIR = os.path.join(DATA_DIR, 'fraud_analysis')
    
    # Create directories if they don't exist
    os.makedirs(PROCESSED_EMAILS_DIR, exist_ok=True)
    os.makedirs(COMPILED_PDFS_DIR, exist_ok=True)
    os.makedirs(PROCESSING_QUEUE_DIR, exist_ok=True)
    os.makedirs(PROCESSED_CLAIMS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(RAW_ATTACHMENTS_DIR, exist_ok=True)
    os.makedirs(FRAUD_ANALYSIS_DIR, exist_ok=True)
    
    # Email Filtering
    CLAIMS_KEYWORDS = os.getenv('CLAIMS_KEYWORDS', 'claim,marine,insurance,reinsurance,loss,damage').split(',')
    
    # Processing Settings
    MAX_EMAILS_PER_RUN = 50
    PROCESS_ONLY_UNREAD = True
    
    # Processing Pipeline Settings
    AUTO_PROCESS_AFTER_EXTRACTION = True
    PROCESSING_BATCH_SIZE = 5  # Reduced for API rate limits
    
    # Fraud Detection Settings
    FRAUD_THRESHOLD = float(os.getenv('FRAUD_THRESHOLD', '0.7'))
    DUPLICATE_THRESHOLD = float(os.getenv('DUPLICATE_THRESHOLD', '0.8'))
    ENABLE_FRAUD_DETECTION = True
    ENABLE_DUPLICATE_CHECK = True

settings = Settings()