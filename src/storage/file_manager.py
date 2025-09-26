import os
import shutil
import logging
from datetime import datetime
from typing import List, Dict, Any

from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FileManager:
    def __init__(self):
        self.base_dirs = {
            'processed_emails': settings.PROCESSED_EMAILS_DIR,
            'raw_attachments': settings.RAW_ATTACHMENTS_DIR,
            'reports': settings.REPORTS_DIR
        }
    
    def save_email_attachments(self, email_id: str, attachments: List[Dict]) -> List[str]:
        """Save email attachments to organized folder structure"""
        saved_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for attachment in attachments:
            try:
                # Create organized folder structure
                attachment_dir = os.path.join(
                    self.base_dirs['raw_attachments'],
                    f"email_{email_id}_{timestamp}"
                )
                os.makedirs(attachment_dir, exist_ok=True)
                
                # Save attachment
                file_path = os.path.join(attachment_dir, attachment['filename'])
                with open(file_path, 'wb') as f:
                    f.write(attachment['data'])
                
                saved_paths.append(file_path)
                logger.info(f"Saved attachment: {file_path}")
                
            except Exception as e:
                logger.error(f"Error saving attachment {attachment['filename']}: {str(e)}")
        
        return saved_paths
    
    def cleanup_old_files(self, days_old: int = 30):
        """Clean up files older than specified days"""
        try:
            cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            for base_dir in self.base_dirs.values():
                for root, dirs, files in os.walk(base_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            logger.info(f"Removed old file: {file_path}")
        
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")