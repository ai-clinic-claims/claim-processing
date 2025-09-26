import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import hashlib

from config.settings import settings
from config.email_config import email_config
from .email_client import EmailClient
from storage.file_manager import FileManager
from pdf_compilation.pdf_compiler import PDFCompiler
from utils.logger import setup_logger

logger = setup_logger(__name__)

class EmailProcessor:
    def __init__(self):
        self.email_client = EmailClient()
        self.file_manager = FileManager()
        self.pdf_compiler = PDFCompiler()
        self.filter_criteria = email_config.FILTER_CRITERIA
        self.processed_emails_file = os.path.join(settings.PROCESSED_CLAIMS_DIR, 'processed_emails.json')
        self.processed_emails = self._load_processed_emails()
    
    def _load_processed_emails(self) -> Dict[str, Any]:
        """Load previously processed emails to avoid duplication"""
        try:
            if os.path.exists(self.processed_emails_file):
                with open(self.processed_emails_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading processed emails: {str(e)}")
        return {}
    
    def _save_processed_emails(self):
        """Save processed emails registry"""
        try:
            with open(self.processed_emails_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_emails, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving processed emails: {str(e)}")
    
    def _get_email_fingerprint(self, email_data: Dict[str, Any]) -> str:
        """Create a unique fingerprint for each email to avoid duplicates"""
        fingerprint_data = {
            'subject': email_data.get('subject', ''),
            'sender_email': email_data.get('sender_email', ''),
            'body_preview': email_data.get('body_preview', '')[:200],
            'attachment_count': len(email_data.get('attachments', []))
        }
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()
    
    def _is_email_processed(self, email_data: Dict[str, Any]) -> bool:
        """Check if email has already been processed"""
        email_fingerprint = self._get_email_fingerprint(email_data)
        return email_fingerprint in self.processed_emails
    
    def _mark_email_processed(self, email_data: Dict[str, Any], result: Dict[str, Any]):
        """Mark email as processed"""
        email_fingerprint = self._get_email_fingerprint(email_data)
        self.processed_emails[email_fingerprint] = {
            'email_id': email_data.get('id'),
            'subject': email_data.get('subject'),
            'sender_email': email_data.get('sender_email'),
            'processed_at': datetime.now().isoformat(),
            'claim_number': result.get('claim_number', 'Unknown'),
            'pdf_path': result.get('pdf_path', '')
        }
        self._save_processed_emails()
    
    def process_emails(self, process_all: bool = False) -> List[Dict[str, Any]]:
        """Main method to process all relevant emails from multiple senders"""
        logger.info("Starting comprehensive email processing...")
        
        if not self.email_client.connect():
            logger.error("Failed to connect to email server")
            return []
        
        try:
            if not self.email_client.select_folder('INBOX'):
                logger.error("Failed to select INBOX folder")
                return []
            
            # Get emails from all target senders
            all_email_ids = self._get_emails_from_all_senders(process_all)
            
            if not all_email_ids:
                logger.info("No emails found from any target sender")
                return []
            
            # Remove duplicates and sort
            unique_email_ids = list(set(all_email_ids))
            unique_email_ids.sort()  # Process in order
            
            processed_emails = []
            for i, email_id in enumerate(unique_email_ids[:settings.MAX_EMAILS_PER_RUN]):
                try:
                    logger.info(f"Processing email {i+1}/{len(unique_email_ids)}")
                    processed_email = self._process_single_email(email_id)
                    if processed_email:
                        processed_emails.append(processed_email)
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {str(e)}")
                    continue
            
            return processed_emails
            
        except Exception as e:
            logger.error(f"Error during email processing: {str(e)}")
            return []
        finally:
            self.email_client.disconnect()
    
    def _get_emails_from_all_senders(self, process_all: bool) -> List[str]:
        """Get emails from all target senders"""
        all_email_ids = []
        
        for sender in self.filter_criteria['senders']:
            sender = sender.strip()  # Clean whitespace
            if not sender:
                continue
                
            logger.info(f"Searching for emails from sender: {sender}")
            
            if process_all:
                # Search for all emails from this sender
                criteria = f'(FROM "{sender}")'
            else:
                # Search for unread emails from this sender
                criteria = f'(UNSEEN FROM "{sender}")'
                
            email_ids = self.email_client.search_emails(criteria)
            
            # If no unread emails found and we're not processing all, try all emails from sender
            if not email_ids and not process_all:
                criteria = f'(FROM "{sender}")'
                email_ids = self.email_client.search_emails(criteria)
            
            if email_ids:
                logger.info(f"Found {len(email_ids)} emails from {sender}")
                all_email_ids.extend(email_ids)
            else:
                logger.info(f"No emails found from {sender}")
        
        return all_email_ids
    
    def _process_single_email(self, email_id: str) -> Dict[str, Any]:
        """Process a single email with comprehensive document extraction"""
        # Fetch email data
        email_data = self.email_client.fetch_email(email_id)
        if not email_data:
            return None
        
        # Check if email matches our criteria (from any target sender)
        if not self._is_relevant_email(email_data):
            return None
        
        # Check if email has already been processed
        if self._is_email_processed(email_data):
            logger.info(f"Email already processed: {email_data['subject']}")
            return None
        
        logger.info(f"Processing relevant email: {email_data['subject']}")
        
        # Save email and attachments
        saved_paths = self._save_email_data(email_data)
        
        # Compile to PDF with full content extraction
        pdf_path = self._compile_comprehensive_pdf(email_data, saved_paths)
        
        # Mark as read
        self.email_client.mark_as_read(email_id)
        
        # Create processing record
        processed_email = {
            **email_data,
            'saved_paths': saved_paths,
            'pdf_path': pdf_path,
            'claim_number': self.pdf_compiler.extract_claim_number(email_data),
            'processed_at': datetime.now().isoformat(),
            'processing_status': 'success'
        }
        
        # Mark email as processed
        self._mark_email_processed(email_data, processed_email)
        
        # Save processing metadata
        self._save_processing_metadata(processed_email)
        
        logger.info(f"Successfully processed email {email_id} with full content extraction")
        return processed_email
    
    # ... rest of the existing methods remain the same ...
    def _compile_comprehensive_pdf(self, email_data: Dict[str, Any], saved_paths: Dict[str, Any]) -> str:
        """Compile email data and attachment content to PDF"""
        try:
            pdf_path = self.pdf_compiler.compile_email_to_pdf(email_data, saved_paths)
            
            # Add PDF path to saved paths
            saved_paths['compiled_pdf'] = pdf_path
            
            logger.info(f"Comprehensive PDF created: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Error compiling comprehensive PDF: {str(e)}")
            raise
    
    def _is_relevant_email(self, email_data: Dict[str, Any]) -> bool:
        """Check if email matches our processing criteria (any target sender)"""
        sender_email = email_data['sender_email'].lower()
        subject = email_data['subject'].lower()
        body = email_data['body'].lower()
        
        # Check if sender is in our target senders list
        target_senders = [s.strip().lower() for s in self.filter_criteria['senders']]
        sender_match = any(target_sender in sender_email for target_sender in target_senders)
        
        if not sender_match:
            return False
        
        # Check for keywords in subject or body
        keywords = [k.lower() for k in self.filter_criteria['keywords']]
        subject_contains_keyword = any(keyword in subject for keyword in keywords)
        body_contains_keyword = any(keyword in body for keyword in keywords)
        
        return subject_contains_keyword or body_contains_keyword
    
    def _save_email_data(self, email_data: Dict[str, Any]) -> Dict[str, str]:
        """Save email and attachments to file system"""
        email_id = email_data['id']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        email_folder = f"email_{email_id}_{timestamp}"
        
        saved_paths = {
            'email_folder': email_folder,
            'email_metadata': None,
            'email_body': None,
            'attachments': []
        }
        
        try:
            email_base_path = os.path.join(settings.PROCESSED_EMAILS_DIR, email_folder)
            os.makedirs(email_base_path, exist_ok=True)
            
            # Save email metadata
            metadata_path = os.path.join(email_base_path, 'email_metadata.json')
            metadata = {
                'id': email_data['id'],
                'subject': email_data['subject'],
                'sender_name': email_data['sender_name'],
                'sender_email': email_data['sender_email'],
                'date': email_data['date'],
                'processed_at': datetime.now().isoformat(),
                'attachment_count': len(email_data['attachments']),
                'body_preview': email_data['body_preview']
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            saved_paths['email_metadata'] = metadata_path
            
            # Save email body
            body_path = os.path.join(email_base_path, 'email_body.txt')
            with open(body_path, 'w', encoding='utf-8') as f:
                f.write(email_data['body'])
            
            saved_paths['email_body'] = body_path
            
            # Save attachments
            for attachment in email_data['attachments']:
                clean_filename = "".join(c for c in attachment['filename'] if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                attachment_path = os.path.join(email_base_path, clean_filename)
                
                with open(attachment_path, 'wb') as f:
                    f.write(attachment['data'])
                
                saved_paths['attachments'].append({
                    'original_filename': attachment['filename'],
                    'saved_filename': clean_filename,
                    'path': attachment_path,
                    'size': attachment['size'],
                    'content_type': attachment['content_type']
                })
            
        except Exception as e:
            logger.error(f"Error saving email data: {str(e)}")
        
        return saved_paths
    
    def _save_processing_metadata(self, processed_email: Dict[str, Any]):
        """Save processing metadata to central log"""
        try:
            log_file = os.path.join(settings.REPORTS_DIR, 'processing_log.json')
            
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = []
            
            log_entry = {
                'email_id': processed_email['id'],
                'claim_number': processed_email['claim_number'],
                'subject': processed_email['subject'],
                'sender_email': processed_email['sender_email'],
                'processed_at': processed_email['processed_at'],
                'attachment_count': len(processed_email['attachments']),
                'pdf_path': processed_email['pdf_path'],
                'saved_folder': processed_email['saved_paths']['email_folder'],
                'processing_status': processed_email['processing_status']
            }
            
            log_data.append(log_entry)
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving processing metadata: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test email server connection"""
        try:
            logger.info("Testing email server connection...")
            
            if not self.email_client.connect():
                logger.error("Failed to connect to email server")
                return False
            
            # Test folder selection
            if not self.email_client.select_folder('INBOX'):
                logger.error("Failed to select INBOX folder")
                return False
            
            # Test search capability
            email_count = self.email_client.get_email_count()
            logger.info(f"Email server connection successful. Inbox contains {email_count} emails.")
            
            self.email_client.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"Email connection test failed: {str(e)}")
            return False