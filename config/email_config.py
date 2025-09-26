from .settings import settings

class EmailConfig:
    # IMAP Configuration
    IMAP_CONFIG = {
        'server': settings.IMAP_SERVER,
        'port': settings.IMAP_PORT,
        'username': settings.EMAIL_USER,
        'password': settings.EMAIL_PASSWORD,
        'use_ssl': True
    }
    
    # Updated: Email Filter Criteria for multiple senders
    FILTER_CRITERIA = {
        'senders': settings.TARGET_SENDER_EMAILS,  # Now a list of senders
        'keywords': settings.CLAIMS_KEYWORDS,
        'subject_contains': ['claim', 'marine', 'insurance', 'reinsurance']
    }
    
    # Folder Names
    FOLDERS = {
        'inbox': 'INBOX',
        'processed': 'Processed',
        'spam': 'Spam'
    }

email_config = EmailConfig()