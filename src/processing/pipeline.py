import os
import time
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config.settings import settings
from emails.email_processor import EmailProcessor
from gemini_integration.claims_analyzer import ClaimsAnalyzer
from gemini_integration.fraud_detector import FraudDetector
from gemini_integration.duplicate_detector import DuplicateDetector
from reporting.report_generator import ReportGenerator
from utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class ProcessingResult:
    email_id: str
    claim_number: str
    subject: str
    sender_email: str
    processing_status: str
    fraud_score: float
    is_duplicate: bool
    duplicate_of: Optional[str]
    analysis_results: Dict[str, Any]
    report_path: str
    processed_at: str

class ClaimsProcessingPipeline:
    def __init__(self):
        self.email_processor = EmailProcessor()
        self.claims_analyzer = ClaimsAnalyzer()
        self.fraud_detector = FraudDetector()
        self.duplicate_detector = DuplicateDetector()
        self.report_generator = ReportGenerator()
        self.processed_claims = self._load_processed_claims()
    
    def _load_processed_claims(self) -> Dict[str, Any]:
        """Load previously processed claims for duplicate detection"""
        try:
            claims_file = os.path.join(settings.PROCESSED_CLAIMS_DIR, 'processed_claims.json')
            if os.path.exists(claims_file):
                with open(claims_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading processed claims: {str(e)}")
        return {}
    
    def _save_processed_claims(self):
        """Save processed claims to file"""
        try:
            claims_file = os.path.join(settings.PROCESSED_CLAIMS_DIR, 'processed_claims.json')
            with open(claims_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_claims, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving processed claims: {str(e)}")
    
    def process_single_claim(self, email_data: Dict[str, Any]) -> ProcessingResult:
        """Process a single claim from email data"""
        try:
            logger.info(f"Processing claim from email: {email_data['subject']}")
            
            # Extract text content from compiled PDF
            pdf_text = self._extract_pdf_content(email_data['pdf_path'])
            
            # Analyze claim using Gemini
            claim_analysis = self.claims_analyzer.analyze_claim(pdf_text, email_data)
            
            # Check for duplicates
            duplicate_check = self.duplicate_detector.check_duplicate(
                claim_analysis, self.processed_claims
            )
            
            # Detect fraud
            fraud_analysis = self.fraud_detector.detect_fraud(claim_analysis, email_data)
            
            # Generate comprehensive report
            report_data = {
                'email_data': email_data,
                'claim_analysis': claim_analysis,
                'duplicate_check': duplicate_check,
                'fraud_analysis': fraud_analysis,
                'processing_timestamp': datetime.now().isoformat()
            }
            
            report_path = self.report_generator.generate_claim_report(report_data)
            
            # Create processing result
            result = ProcessingResult(
                email_id=email_data['id'],
                claim_number=claim_analysis.get('claim_number', 'Unknown'),
                subject=email_data['subject'],
                sender_email=email_data['sender_email'],
                processing_status='completed',
                fraud_score=fraud_analysis.get('fraud_score', 0.0),
                is_duplicate=duplicate_check.get('is_duplicate', False),
                duplicate_of=duplicate_check.get('duplicate_of'),
                analysis_results=report_data,
                report_path=report_path,
                processed_at=datetime.now().isoformat()
            )
            
            # Update processed claims registry
            if not duplicate_check.get('is_duplicate', False):
                self.processed_claims[result.claim_number] = {
                    'email_id': result.email_id,
                    'subject': result.subject,
                    'sender_email': result.sender_email,
                    'processed_at': result.processed_at,
                    'fraud_score': result.fraud_score,
                    'analysis_summary': claim_analysis.get('summary', {})
                }
                self._save_processed_claims()
            
            logger.info(f"Successfully processed claim {result.claim_number}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing claim: {str(e)}")
            return ProcessingResult(
                email_id=email_data['id'],
                claim_number='Error',
                subject=email_data['subject'],
                sender_email=email_data['sender_email'],
                processing_status='failed',
                fraud_score=0.0,
                is_duplicate=False,
                duplicate_of=None,
                analysis_results={},
                report_path='',
                processed_at=datetime.now().isoformat()
            )
    
    def _extract_pdf_content(self, pdf_path: str) -> str:
        """Extract text content from PDF file"""
        try:
            from document_processing.document_reader import DocumentReader
            reader = DocumentReader()
            return reader.extract_text_from_pdf(pdf_path)
        except Exception as e:
            logger.error(f"Error extracting PDF content: {str(e)}")
            return ""
    
    def run_continuous_processing(self, interval_minutes: int = 1):
        """Run continuous processing checking for new emails every interval"""
        logger.info(f"Starting continuous processing (checking every {interval_minutes} minute(s))")
        
        while True:
            try:
                # Process new emails
                processed_emails = self.email_processor.process_emails(process_all=False)
                
                if processed_emails:
                    logger.info(f"Found {len(processed_emails)} new emails to process")
                    
                    for email_data in processed_emails:
                        try:
                            result = self.process_single_claim(email_data)
                            self._log_processing_result(result)
                        except Exception as e:
                            logger.error(f"Error processing email {email_data['id']}: {str(e)}")
                
                # Wait for next interval
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Processing interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous processing: {str(e)}")
                time.sleep(interval_minutes * 60)  # Wait before retrying
    
    def _log_processing_result(self, result: ProcessingResult):
        """Log processing results"""
        status_icon = "🔄" if result.processing_status == 'processing' else "✅" if result.processing_status == 'completed' else "❌"
        duplicate_icon = "🔁" if result.is_duplicate else "🆕"
        fraud_icon = "🚨" if result.fraud_score > settings.FRAUD_THRESHOLD else "✅"
        
        logger.info(f"""
{status_icon} CLAIM PROCESSING RESULT {status_icon}
📧 Email: {result.subject}
👤 From: {result.sender_email}
🔢 Claim: {result.claim_number}
{duplicate_icon} Duplicate: {result.is_duplicate} {f'(of {result.duplicate_of})' if result.duplicate_of else ''}
{fraud_icon} Fraud Score: {result.fraud_score:.2f}
📊 Status: {result.processing_status}
📄 Report: {result.report_path}
        """)
    
def process_existing_emails(self, process_all=False):
    """Process emails with duplicate prevention"""
    try:
        email_processor = EmailProcessor()
        emails = email_processor.fetch_emails(process_all=process_all)
        
        processed_reports = []
        for email_data in emails:
            # Check if email already processed
            if email_processor.is_email_processed(email_data['email_id']):
                logger.info(f"Email {email_data['email_id']} already processed, skipping")
                continue
            
            try:
                # Process the email
                report = self.process_single_email(email_data)
                if report:
                    # Mark as processed
                    email_processor.mark_email_processed(email_data, report['report_path'])
                    processed_reports.append(report)
                    
            except Exception as e:
                logger.error(f"Error processing email {email_data['email_id']}: {str(e)}")
                continue
        
        return processed_reports
        
    except Exception as e:
        logger.error(f"Error in email processing pipeline: {str(e)}")
        return []
    
    def _generate_processing_summary(self, results: List[ProcessingResult]):
        """Generate a summary of processing results"""
        try:
            summary = {
                'total_processed': len(results),
                'successful': len([r for r in results if r.processing_status == 'completed']),
                'failed': len([r for r in results if r.processing_status == 'failed']),
                'duplicates_found': len([r for r in results if r.is_duplicate]),
                'high_fraud_risk': len([r for r in results if r.fraud_score > settings.FRAUD_THRESHOLD]),
                'processing_timestamp': datetime.now().isoformat(),
                'results': [
                    {
                        'claim_number': r.claim_number,
                        'status': r.processing_status,
                        'fraud_score': r.fraud_score,
                        'is_duplicate': r.is_duplicate,
                        'report_path': r.report_path
                    } for r in results
                ]
            }
            
            summary_file = os.path.join(settings.REPORTS_DIR, f"processing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Processing summary saved to: {summary_file}")
            
        except Exception as e:
            logger.error(f"Error generating processing summary: {str(e)}")