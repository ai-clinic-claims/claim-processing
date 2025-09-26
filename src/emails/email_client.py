import imaplib
import email
from email.header import decode_header
import logging
from typing import List, Dict, Any
import os
import re

from config.email_config import email_config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class EmailClient:
    def __init__(self):
        self.config = email_config.IMAP_CONFIG
        self.connection = None
        
    def connect(self) -> bool:
        """Establish connection to email server"""
        try:
            logger.info(f"Connecting to {self.config['server']}:{self.config['port']}")
            self.connection = imaplib.IMAP4_SSL(
                self.config['server'], 
                self.config['port']
            )
            logger.info("SSL connection established")
            
            self.connection.login(
                self.config['username'], 
                self.config['password']
            )
            logger.info("Successfully logged in to email server")
            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP login error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to email server: {str(e)}")
            return False
    
    def disconnect(self):
        """Close connection to email server"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
                logger.info("Disconnected from email server")
            except Exception as e:
                logger.error(f"Error disconnecting: {str(e)}")
    
    def list_folders(self):
        """List all available folders/mailboxes"""
        try:
            logger.info("Listing available folders...")
            result, folders = self.connection.list()
            if result == 'OK':
                for folder in folders:
                    logger.info(f"Folder: {folder.decode()}")
            return folders
        except Exception as e:
            logger.error(f"Error listing folders: {str(e)}")
            return []
    
    def select_folder(self, folder_name='INBOX'):
        """Select a specific folder"""
        try:
            result, data = self.connection.select(folder_name)
            if result == 'OK':
                messages = int(data[0])
                logger.info(f"Selected folder '{folder_name}' with {messages} messages")
                return True
            else:
                logger.error(f"Failed to select folder '{folder_name}'")
                return False
        except Exception as e:
            logger.error(f"Error selecting folder '{folder_name}': {str(e)}")
            return False
    
    def search_emails(self, criteria: str = 'ALL') -> List[str]:
        """Search for emails matching criteria"""
        try:
            # First select INBOX folder
            if not self.select_folder('INBOX'):
                return []
            
            logger.info(f"Searching emails with criteria: {criteria}")
            status, messages = self.connection.search(None, criteria)
            
            if status == 'OK' and messages[0]:
                email_ids = messages[0].split()
                logger.info(f"Found {len(email_ids)} emails matching criteria")
                return email_ids
            else:
                logger.info("No emails found matching criteria")
                return []
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return []
    
    def search_emails_by_sender(self, sender_email: str) -> List[str]:
        """Search for emails from specific sender"""
        try:
            criteria = f'(FROM "{sender_email}")'
            return self.search_emails(criteria)
        except Exception as e:
            logger.error(f"Error searching emails by sender: {str(e)}")
            return []
    
    def search_unread_emails(self) -> List[str]:
        """Search for unread emails"""
        return self.search_emails('UNSEEN')
    
    def search_recent_emails(self, days: int = 7) -> List[str]:
        """Search for recent emails from last N days"""
        try:
            import datetime
            date_since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%d-%b-%Y')
            criteria = f'(SINCE "{date_since}")'
            return self.search_emails(criteria)
        except Exception as e:
            logger.error(f"Error searching recent emails: {str(e)}")
            return self.search_emails('ALL')  # Fallback to all emails
    
    def fetch_email(self, email_id: str) -> Dict[str, Any]:
        """Fetch complete email data"""
        try:
            logger.debug(f"Fetching email ID: {email_id}")
            status, msg_data = self.connection.fetch(email_id, '(RFC822)')
            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return None
            
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            parsed_email = self._parse_email(email_message, email_id)
            logger.info(f"Successfully parsed email: {parsed_email['subject']}")
            return parsed_email
            
        except Exception as e:
            logger.error(f"Error fetching email {email_id}: {str(e)}")
            return None
    
    def _parse_email(self, email_message, email_id: str) -> Dict[str, Any]:
        """Parse email message into structured data"""
        try:
            # Decode subject
            subject = "No Subject"
            if email_message['Subject']:
                subject_header = decode_header(email_message['Subject'])[0]
                subject_text, encoding = subject_header
                if isinstance(subject_text, bytes):
                    subject = subject_text.decode(encoding if encoding else 'utf-8', errors='ignore')
                else:
                    subject = subject_text
            
            # Parse sender
            sender_name, sender_email = email.utils.parseaddr(email_message['From'])
            if not sender_email:
                sender_email = email_message['From']
            
            # Parse date
            date = email_message['Date'] or "Unknown"
            
            # Get email body
            body = self._extract_body(email_message)
            
            # Get attachments
            attachments = self._extract_attachments(email_message, email_id)
            
            return {
                'id': email_id.decode() if isinstance(email_id, bytes) else email_id,
                'subject': subject,
                'sender_name': sender_name,
                'sender_email': sender_email,
                'date': date,
                'body': body,
                'attachments': attachments,
                'body_preview': body[:200] + "..." if len(body) > 200 else body
            }
        except Exception as e:
            logger.error(f"Error parsing email {email_id}: {str(e)}")
            return {
                'id': email_id,
                'subject': 'Error parsing subject',
                'sender_email': 'Error parsing sender',
                'date': 'Unknown',
                'body': '',
                'attachments': [],
                'body_preview': 'Error parsing email'
            }
    
    def _extract_body(self, email_message) -> str:
        """Extract text body from email"""
        body = ""
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue
                    
                    if content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode('utf-8', errors='ignore')
                                break
                        except Exception as e:
                            logger.warning(f"Error decoding text/plain part: {e}")
                            continue
                    elif content_type == "text/html":
                        # Fallback to HTML if no plain text
                        if not body:
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    # Basic HTML to text conversion
                                    html_content = payload.decode('utf-8', errors='ignore')
                                    # Remove HTML tags
                                    clean_text = re.sub('<[^<]+?>', '', html_content)
                                    body = clean_text
                            except Exception as e:
                                logger.warning(f"Error decoding text/html part: {e}")
                                continue
            else:
                # Not multipart, just get the payload
                try:
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                except Exception as e:
                    logger.warning(f"Error decoding single part email: {e}")
                    body = email_message.get_payload()
        
        except Exception as e:
            logger.error(f"Error extracting email body: {str(e)}")
        
        return body if body else "No body content could be extracted"
    
    def _extract_attachments(self, email_message, email_id: str) -> List[Dict]:
        """Extract attachments from email"""
        attachments = []
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            # Decode filename
                            filename_header = decode_header(filename)[0]
                            filename_text, encoding = filename_header
                            if isinstance(filename_text, bytes):
                                filename = filename_text.decode(encoding if encoding else 'utf-8', errors='ignore')
                            else:
                                filename = filename_text
                            
                            attachment_data = part.get_payload(decode=True)
                            
                            if attachment_data:
                                attachments.append({
                                    'filename': filename,
                                    'data': attachment_data,
                                    'content_type': part.get_content_type(),
                                    'size': len(attachment_data)
                                })
                                logger.debug(f"Found attachment: {filename} ({len(attachment_data)} bytes)")
            
            logger.info(f"Extracted {len(attachments)} attachments from email {email_id}")
            
        except Exception as e:
            logger.error(f"Error extracting attachments: {str(e)}")
        
        return attachments
    
    def mark_as_read(self, email_id: str):
        """Mark email as read"""
        try:
            self.connection.store(email_id, '+FLAGS', '\\Seen')
            logger.debug(f"Marked email {email_id} as read")
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
    
    def mark_as_unread(self, email_id: str):
        """Mark email as unread"""
        try:
            self.connection.store(email_id, '-FLAGS', '\\Seen')
            logger.debug(f"Marked email {email_id} as unread")
        except Exception as e:
            logger.error(f"Error marking email as unread: {str(e)}")
    
    def get_email_count(self) -> int:
        """Get total number of emails in selected folder"""
        try:
            result, data = self.connection.status('INBOX', '(MESSAGES)')
            if result == 'OK':
                messages = int(data[0].split()[2].strip(b')'))
                return messages
            return 0
        except Exception as e:
            logger.error(f"Error getting email count: {str(e)}")
            return 0