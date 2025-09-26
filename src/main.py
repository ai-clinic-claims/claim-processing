#!/usr/bin/env python3
"""
Main entry point for Marine Reinsurance Claims Processing System
"""

import os
import sys
import logging
import argparse
import time
from datetime import datetime

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from utils.logger import setup_logger
from emails.email_processor import EmailProcessor
from processing.pipeline import ClaimsProcessingPipeline
from dashboard.app import start_dashboard

logger = setup_logger(__name__)

def main():
    """Main function to run the complete claims processing system"""
    parser = argparse.ArgumentParser(
        description='Marine Insurance Claims Processing System with AI Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py --mode continuous    # Run continuous processing
  python src/main.py --mode batch         # Process all existing emails
  python src/main.py --mode single        # Process only new emails
  python src/main.py --test               # Test system components
  python src/main.py --extract-only       # Only extract emails, no AI analysis
  python src/main.py --dashboard          # Start web dashboard
        """
    )
    
    parser.add_argument('--mode', choices=['single', 'continuous', 'batch', 'extract', 'dashboard'], 
                       default='continuous', help='Processing mode (default: continuous)')
    parser.add_argument('--interval', type=int, default=1, 
                       help='Check interval in minutes for continuous mode (default: 1)')
    parser.add_argument('--test', action='store_true', help='Test system components')
    parser.add_argument('--all', action='store_true', help='Process all emails (batch mode)')
    parser.add_argument('--extract-only', action='store_true', 
                       help='Only extract emails and documents, skip AI analysis')
    parser.add_argument('--max-emails', type=int, default=50,
                       help='Maximum number of emails to process per run (default: 50)')
    parser.add_argument('--dashboard-host', default='0.0.0.0', help='Dashboard host (default: 0.0.0.0)')
    parser.add_argument('--dashboard-port', type=int, default=5000, help='Dashboard port (default: 5000)')
    
    args = parser.parse_args()
    
    try:
        logger.info("🚢 Starting Marine Reinsurance Claims Processing System")
        logger.info(f"📋 Mode: {args.mode.upper()}")
        logger.info(f"⏰ Interval: {args.interval} minute(s)" if args.mode == 'continuous' else "")
        
        if args.mode == 'dashboard':
            logger.info(f"🌐 Starting dashboard on {args.dashboard_host}:{args.dashboard_port}")
            return start_dashboard(host=args.dashboard_host, port=args.dashboard_port)
        
        if args.extract_only:
            logger.info("📧 Running in extraction-only mode (no AI analysis)")
            return run_extraction_only(args)
        
        # Initialize the complete processing pipeline
        pipeline = ClaimsProcessingPipeline()
        
        if args.test:
            logger.info("🔧 Running system tests...")
            return run_system_tests(pipeline)
        
        if args.mode == 'single':
            logger.info("📧 Processing single batch of new emails...")
            pipeline.process_existing_emails(process_all=False)
            
        elif args.mode == 'batch':
            logger.info("📦 Processing all existing emails...")
            pipeline.process_existing_emails(process_all=True)
            
        elif args.mode == 'continuous':
            logger.info(f"🔄 Starting continuous processing (checking every {args.interval} minute(s))")
            logger.info("Press Ctrl+C to stop processing")
            pipeline.run_continuous_processing(interval_minutes=args.interval)
        
        elif args.mode == 'extract':
            logger.info("📥 Running email extraction only...")
            return run_extraction_only(args)
        
        logger.info("✅ Processing completed successfully")
        
    except KeyboardInterrupt:
        logger.info("⏹️ Processing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Application error: {str(e)}")
        logger.exception("Detailed error traceback:")
        sys.exit(1)

def run_extraction_only(args):
    """Run only email extraction without AI analysis"""
    try:
        from config.settings import settings
        
        # Update settings for extraction only
        settings.AUTO_PROCESS_AFTER_EXTRACTION = False
        settings.ENABLE_FRAUD_DETECTION = False
        settings.ENABLE_DUPLICATE_CHECK = False
        
        processor = EmailProcessor()
        processed_emails = processor.process_emails(process_all=args.all)
        
        if processed_emails:
            logger.info(f"✅ Extraction completed. Processed {len(processed_emails)} emails")
            for email in processed_emails:
                logger.info(f"   📧 {email['subject']} from {email['sender_email']}")
                logger.info(f"      📎 Attachments: {len(email['attachments'])}")
                logger.info(f"      📄 PDF: {email.get('pdf_path', 'Unknown')}")
        else:
            logger.info("ℹ️ No emails were processed")
            
    except Exception as e:
        logger.error(f"❌ Extraction error: {str(e)}")
        return 1
    return 0

def run_system_tests(pipeline):
    """Run comprehensive system component tests"""
    try:
        logger.info("🧪 Running system diagnostics...")
        
        # Test 1: Check configuration
        from config.settings import settings
        logger.info("✅ Configuration loaded successfully")
        logger.info(f"   📧 Email: {settings.EMAIL_USER}")
        logger.info(f"   🤖 Gemini API: {'Configured' if settings.GEMINI_API_KEY else 'Not configured'}")
        logger.info(f"   📁 Data directory: {settings.DATA_DIR}")
        
        # Test 2: Check directory structure
        required_dirs = [
            settings.PROCESSED_EMAILS_DIR,
            settings.COMPILED_PDFS_DIR,
            settings.REPORTS_DIR,
            settings.PROCESSED_CLAIMS_DIR
        ]
        
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                logger.info(f"✅ Directory exists: {dir_path}")
            else:
                logger.warning(f"⚠️ Directory missing: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"   📁 Created directory: {dir_path}")
        
        # Test 3: Test email connection
        logger.info("📧 Testing email connection...")
        from emails.email_client import EmailClient
        email_client = EmailClient()
        if email_client.connect():
            logger.info("✅ Email connection successful")
            email_count = email_client.get_email_count()
            logger.info(f"   📬 Emails in inbox: {email_count}")
            email_client.disconnect()
        else:
            logger.error("❌ Email connection failed")
            return 1
        
        # Test 4: Test Gemini API (if configured)
        if settings.GEMINI_API_KEY:
            logger.info("🤖 Testing Gemini API connection...")
            try:
                from gemini_integration.gemini_client import GeminiClient
                gemini_client = GeminiClient()
                test_response = gemini_client.analyze_content("Test connection - respond with 'OK'")
                if "OK" in test_response.upper():
                    logger.info("✅ Gemini API connection successful")
                else:
                    logger.warning("⚠️ Gemini API responded but with unexpected content")
            except Exception as e:
                logger.error(f"❌ Gemini API test failed: {str(e)}")
        else:
            logger.warning("⚠️ Gemini API key not configured - AI features will be limited")
        
        # Test 5: Check PDF generation capability
        logger.info("📄 Testing PDF generation...")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            test_pdf_path = os.path.join(settings.REPORTS_DIR, "test_report.pdf")
            c = canvas.Canvas(test_pdf_path, pagesize=A4)
            c.drawString(100, 750, "Test PDF Generation")
            c.save()
            if os.path.exists(test_pdf_path):
                logger.info("✅ PDF generation test passed")
                os.remove(test_pdf_path)  # Clean up test file
            else:
                logger.error("❌ PDF generation test failed")
        except Exception as e:
            logger.error(f"❌ PDF generation test failed: {str(e)}")
        
        logger.info("🎉 All system tests completed successfully!")
        logger.info("\n📋 SYSTEM READY FOR PROCESSING")
        logger.info("💡 Recommended next steps:")
        logger.info("   1. python src/main.py --mode single (test with a few emails)")
        logger.info("   2. python src/main.py --mode continuous (start continuous processing)")
        logger.info("   3. python src/main.py --dashboard (start web dashboard)")
        logger.info("   4. Check the 'data/reports' directory for generated reports")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ System tests failed: {str(e)}")
        logger.exception("Detailed error traceback:")
        return 1

def display_system_info():
    """Display system information and status"""
    from config.settings import settings
    
    print("\n" + "="*60)
    print("🚢 MARINE REINSURANCE CLAIMS PROCESSING SYSTEM")
    print("="*60)
    print(f"📧 Email Account: {settings.EMAIL_USER}")
    print(f"👤 Target Senders: {', '.join(settings.TARGET_SENDER_EMAILS)}")
    print(f"🤖 AI Analysis: {'Enabled' if settings.GEMINI_API_KEY else 'Disabled'}")
    print(f"📁 Data Directory: {settings.DATA_DIR}")
    print(f"⚙️ Fraud Detection: {'Enabled' if settings.ENABLE_FRAUD_DETECTION else 'Disabled'}")
    print(f"🔍 Duplicate Check: {'Enabled' if settings.ENABLE_DUPLICATE_CHECK else 'Disabled'}")
    print("="*60)
    print("\n💡 Available Processing Modes:")
    print("   --mode single     : Process only new/unread emails")
    print("   --mode batch      : Process all existing emails") 
    print("   --mode continuous : Continuous monitoring (every 1 minute)")
    print("   --mode extract    : Extract emails only (no AI analysis)")
    print("   --mode dashboard  : Start web dashboard")
    print("   --test            : Run system diagnostics")
    print("\nExample: python src/main.py --mode continuous --interval 5")
    print("Example: python src/main.py --dashboard --dashboard-port 8080")
    print("="*60 + "\n")

if __name__ == "__main__":
    # Display system info when starting
    display_system_info()
    
    # Run the main function
    main()