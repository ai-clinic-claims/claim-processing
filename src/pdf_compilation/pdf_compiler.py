import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import re
import pandas as pd
from pdf2image import convert_from_path
import cv2
import numpy as np
from PIL import Image

# Add config to path
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
if config_path not in sys.path:
    sys.path.insert(0, config_path)

from config.settings import settings
from utils.logger import setup_logger
from document_processing.document_reader import DocumentReader

logger = setup_logger(__name__)

class PDFCompiler:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.document_reader = DocumentReader()
        self._setup_custom_styles()
        self.page_size = A4
        self.output_dir = settings.COMPILED_PDFS_DIR
        
    def _setup_custom_styles(self):
        """Setup custom styles for PDF formatting"""
        custom_styles = {
            'ClaimTitle': ParagraphStyle(
                name='ClaimTitle',
                parent=self.styles['Heading1'],
                fontSize=16,
                textColor=colors.darkblue,
                spaceAfter=12,
                alignment=1
            ),
            'SectionHeader': ParagraphStyle(
                name='SectionHeader',
                parent=self.styles['Heading2'],
                fontSize=12,
                textColor=colors.darkblue,
                spaceAfter=6,
                spaceBefore=12
            ),
            'BodyTextCustom': ParagraphStyle(
                name='BodyTextCustom',
                parent=self.styles['BodyText'],
                fontSize=9,
                spaceAfter=6,
                leading=12
            ),
            'SmallTextCustom': ParagraphStyle(
                name='SmallTextCustom',
                parent=self.styles['BodyText'],
                fontSize=8,
                textColor=colors.gray,
                leading=10
            ),
            'AttachmentContent': ParagraphStyle(
                name='AttachmentContent',
                parent=self.styles['BodyText'],
                fontSize=8,
                textColor=colors.darkgreen,
                spaceAfter=6,
                leading=10,
                leftIndent=10
            ),
            'CodeText': ParagraphStyle(
                name='CodeText',
                parent=self.styles['Code'],
                fontSize=7,
                textColor=colors.darkred,
                leading=9,
                leftIndent=10,
                fontName='Courier'
            ),
            'TableHeader': ParagraphStyle(
                name='TableHeader',
                parent=self.styles['BodyText'],
                fontSize=8,
                textColor=colors.white,
                fontName='Helvetica-Bold',
                alignment=1
            ),
            'TableCell': ParagraphStyle(
                name='TableCell',
                parent=self.styles['BodyText'],
                fontSize=7,
                leading=9,
                alignment=0
            )
        }
        
        for name, style in custom_styles.items():
            if name not in self.styles:
                self.styles.add(style)

    def extract_claim_number(self, email_data: Dict[str, Any]) -> str:
        """Extract claim number from email subject and body"""
        claim_number = "UNKNOWN_CLAIM"
        
        patterns = [
            r'Claim[:\s]*([A-Z0-9\-]+)',
            r'Claim\s*Number[:\s]*([A-Z0-9\-]+)',
            r'CLM[:\s]*([A-Z0-9\-]+)',
            r'Ref[:\s]*([A-Z0-9\-]+)',
            r'Reference[:\s]*([A-Z0-9\-]+)',
            r'([A-Z]{2,4}\d{4,8}[A-Z]?)',
            r'(\d{4}-\d{4}-\d{4})',
        ]
        
        text_to_search = f"{email_data['subject']} {email_data['body']}".upper()
        
        for pattern in patterns:
            matches = re.findall(pattern, text_to_search, re.IGNORECASE)
            if matches:
                claim_number = matches[0]
                break
        
        claim_number = re.sub(r'[^\w\-]', '', claim_number)
        if claim_number == "UNKNOWN_CLAIM":
            claim_number = f"CLAIM_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return claim_number

    def detect_form_elements(self, pdf_path: str) -> Dict[str, Any]:
        """
        Detect checkboxes, radio buttons, and form fields in PDF
        Returns structured data about form elements
        """
        try:
            form_data = {
                'checkboxes': [],
                'radio_buttons': [],
                'form_fields': [],
                'tables': []
            }
            
            # Convert PDF to images for visual analysis
            images = convert_from_path(pdf_path, dpi=150)
            
            for page_num, image in enumerate(images):
                # Convert PIL image to OpenCV format
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                
                # Detect rectangles (potential checkboxes/buttons)
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edges = cv2.Canny(blurred, 50, 150)
                
                # Find contours
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    # Approximate the contour
                    epsilon = 0.02 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    
                    # Check if it's a rectangle (4 sides)
                    if len(approx) == 4:
                        x, y, w, h = cv2.boundingRect(approx)
                        
                        # Check if it's checkbox/radio button sized
                        if 10 <= w <= 30 and 10 <= h <= 30:
                            aspect_ratio = w / h
                            if 0.8 <= aspect_ratio <= 1.2:  # Square-ish
                                # Check if it's filled (radio button) or empty (checkbox)
                                roi = gray[y:y+h, x:x+w]
                                mean_intensity = np.mean(roi)
                                
                                if mean_intensity < 100:  # Dark - probably filled
                                    form_data['radio_buttons'].append({
                                        'page': page_num + 1,
                                        'position': (x, y),
                                        'size': (w, h),
                                        'status': 'filled'
                                    })
                                else:  # Light - probably empty
                                    form_data['checkboxes'].append({
                                        'page': page_num + 1,
                                        'position': (x, y),
                                        'size': (w, h),
                                        'status': 'empty'
                                    })
            
            logger.info(f"Detected {len(form_data['checkboxes'])} checkboxes and {len(form_data['radio_buttons'])} radio buttons")
            return form_data
            
        except Exception as e:
            logger.warning(f"Form element detection failed: {str(e)}")
            return {'checkboxes': [], 'radio_buttons': [], 'form_fields': [], 'tables': []}

    def extract_tables_with_structure(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF while preserving structure
        Returns list of tables with their data and metadata
        """
        try:
            import pdfplumber
            tables_data = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract tables using pdfplumber
                    tables = page.extract_tables({
                        'vertical_strategy': 'lines', 
                        'horizontal_strategy': 'lines',
                        'snap_tolerance': 5
                    })
                    
                    for table_num, table in enumerate(tables, 1):
                        if table and any(any(cell is not None for cell in row) for row in table):
                            # Clean and process table data
                            cleaned_table = []
                            for row in table:
                                cleaned_row = []
                                for cell in row:
                                    if cell is None:
                                        cleaned_row.append('')
                                    else:
                                        # Clean cell content
                                        cell_text = str(cell).strip()
                                        cell_text = re.sub(r'\s+', ' ', cell_text)
                                        cleaned_row.append(cell_text)
                                cleaned_table.append(cleaned_row)
                            
                            # Only add non-empty tables
                            if any(any(cell.strip() for cell in row) for row in cleaned_table):
                                tables_data.append({
                                    'page': page_num,
                                    'table_number': table_num,
                                    'data': cleaned_table,
                                    'dimensions': f"{len(cleaned_table)}x{len(cleaned_table[0]) if cleaned_table else 0}",
                                    'has_header': len(cleaned_table) > 1 and any(
                                        any(cell.strip() for cell in cleaned_table[0])
                                    )
                                })
            
            logger.info(f"Extracted {len(tables_data)} tables from PDF")
            return tables_data
            
        except ImportError:
            logger.warning("pdfplumber not available for table extraction")
            return []
        except Exception as e:
            logger.warning(f"Table extraction failed: {str(e)}")
            return []

    def create_table_for_pdf(self, table_data: List[List[str]]) -> Table:
        """Convert extracted table data to ReportLab Table object"""
        try:
            if not table_data or not any(any(cell.strip() for cell in row) for row in table_data):
                return Paragraph("No table data available", self.styles['SmallTextCustom'])
            
            # Create table content with proper styling
            table_content = []
            for row_idx, row in enumerate(table_data):
                table_row = []
                for cell in row:
                    if row_idx == 0 and any(cell.strip() for cell in row):  # Header row
                        table_row.append(Paragraph(cell or '', self.styles['TableHeader']))
                    else:
                        table_row.append(Paragraph(cell or '', self.styles['TableCell']))
                table_content.append(table_row)
            
            # Calculate column widths
            num_cols = len(table_data[0]) if table_data else 1
            col_widths = [1.5 * inch] * num_cols
            
            table = Table(table_content, colWidths=col_widths)
            
            # Apply table styling
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),  # Header background
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),      # Header text color
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),              # Header alignment
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),   # Header font
                ('FONTSIZE', (0, 0), (-1, 0), 8),                  # Header font size
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),    # Body background
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),     # Body text color
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),       # Body font
                ('FONTSIZE', (0, 1), (-1, -1), 7),                 # Body font size
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),               # Cell alignment
                ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),      # Grid lines
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),               # Vertical alignment
                ('PADDING', (0, 0), (-1, -1), 3),                  # Cell padding
            ])
            
            # Alternate row colors for readability
            for row_idx in range(1, len(table_data)):
                if row_idx % 2 == 0:
                    style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightgrey)
            
            table.setStyle(style)
            return table
            
        except Exception as e:
            logger.error(f"Error creating PDF table: {str(e)}")
            return Paragraph(f"Error displaying table: {str(e)}", self.styles['SmallTextCustom'])

    def compile_email_to_pdf(self, email_data: Dict[str, Any], saved_paths: Dict[str, Any]) -> str:
        """Compile all email information and FULL attachment content into a single PDF"""
        try:
            # Extract claim number for filename
            claim_number = self.extract_claim_number(email_data)
            safe_claim_number = "".join(c for c in claim_number if c.isalnum() or c in ('-', '_'))
            
            # Create PDF filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_filename = f"Claim_{safe_claim_number}_{timestamp}.pdf"
            pdf_path = os.path.join(self.output_dir, pdf_filename)
            
            # Extract FULL content from attachments with enhanced table extraction
            attachment_results = self.document_reader.extract_from_attachments(
                saved_paths.get('attachments', [])
            )
            
            # Enhance attachment results with table and form data
            attachment_results = self._enhance_with_structured_data(attachment_results, saved_paths)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=self.page_size,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            story = []
            
            # Add title page
            story.extend(self._create_title_page(email_data, claim_number, attachment_results))
            story.append(PageBreak())
            
            # Add email content section
            story.extend(self._create_email_content_section(email_data))
            story.append(PageBreak())
            
            # Add attachments content section with FULL extracted text and structured data
            story.extend(self._create_attachments_content_section(attachment_results))
            
            # Add processing information
            story.extend(self._create_processing_section(saved_paths, attachment_results))
            
            # Build PDF
            doc.build(story)
            
            # Also create a comprehensive text file
            text_file_path = self.create_extracted_text_file(email_data, saved_paths, attachment_results)
            logger.info(f"Also created text file: {text_file_path}")
            
            logger.info(f"Successfully compiled comprehensive PDF with full attachment content and structured data: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Error compiling PDF: {str(e)}")
            raise

    def _enhance_with_structured_data(self, attachment_results: Dict, saved_paths: Dict) -> Dict:
        """Enhance attachment results with table and form element data"""
        enhanced_attachments = []
        
        for attachment in attachment_results.get('attachments', []):
            if attachment.get('extraction_success') and attachment.get('file_type') == 'pdf':
                file_path = None
                # Find the actual file path from saved_paths
                for saved_attachment in saved_paths.get('attachments', []):
                    if os.path.basename(saved_attachment) == attachment.get('filename'):
                        file_path = saved_attachment
                        break
                
                if file_path and os.path.exists(file_path):
                    try:
                        # Extract tables
                        tables = self.extract_tables_with_structure(file_path)
                        attachment['tables'] = tables
                        
                        # Detect form elements
                        form_elements = self.detect_form_elements(file_path)
                        attachment['form_elements'] = form_elements
                        
                        # Add structured data summary
                        attachment['structured_data_summary'] = {
                            'table_count': len(tables),
                            'checkbox_count': len(form_elements['checkboxes']),
                            'radio_button_count': len(form_elements['radio_buttons']),
                            'form_field_count': len(form_elements['form_fields'])
                        }
                        
                    except Exception as e:
                        logger.warning(f"Failed to enhance attachment with structured data: {str(e)}")
                        attachment['tables'] = []
                        attachment['form_elements'] = {'checkboxes': [], 'radio_buttons': [], 'form_fields': [], 'tables': []}
                        attachment['structured_data_summary'] = {
                            'table_count': 0,
                            'checkbox_count': 0,
                            'radio_button_count': 0,
                            'form_field_count': 0
                        }
            
            enhanced_attachments.append(attachment)
        
        attachment_results['attachments'] = enhanced_attachments
        return attachment_results

    def _create_title_page(self, email_data: Dict, claim_number: str, attachment_results: Dict) -> List:
        """Create title page with summary including structured data info"""
        elements = []
        
        # Title
        elements.append(Paragraph("MARINE INSURANCE CLAIM COMPREHENSIVE REPORT", self.styles['ClaimTitle']))
        elements.append(Spacer(1, 24))
        
        # Calculate structured data totals
        total_tables = sum(att.get('structured_data_summary', {}).get('table_count', 0) 
                          for att in attachment_results.get('attachments', []))
        total_checkboxes = sum(att.get('structured_data_summary', {}).get('checkbox_count', 0) 
                              for att in attachment_results.get('attachments', []))
        total_radio_buttons = sum(att.get('structured_data_summary', {}).get('radio_button_count', 0) 
                                 for att in attachment_results.get('attachments', []))
        
        # Claim summary table
        total_words = sum(att.get('word_count', 0) for att in attachment_results.get('attachments', []))
        total_pages = sum(att.get('pages', 1) for att in attachment_results.get('attachments', []))
        
        data = [
            ['Claim Number:', claim_number],
            ['Email Subject:', email_data['subject']],
            ['From:', f"{email_data.get('sender_name', '')} ({email_data.get('sender_email', '')})"],
            ['Date Received:', email_data.get('date', 'Unknown')],
            ['Total Attachments:', str(attachment_results.get('total_attachments', 0))],
            ['Successfully Processed:', str(attachment_results.get('successful_extractions', 0))],
            ['Tables Extracted:', str(total_tables)],
            ['Form Elements:', f"Checkboxes: {total_checkboxes}, Radio Buttons: {total_radio_buttons}"],
            ['Total Words Extracted:', f"{total_words:,}"],
            ['Total Pages (Est.):', str(total_pages)],
            ['Processing Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.darkblue),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, -1), 10),
            ('BACKGROUND', (1, 0), (1, -1), colors.beige),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 24))
        
        # Executive summary
        summary_text = f"""
        <b>EXECUTIVE SUMMARY</b><br/><br/>
        This comprehensive report contains the complete extraction of ALL content from the marine insurance claim email 
        and ALL attached documents, including structured data like tables and form elements.
        
        <b>Structured Data Extracted:</b>
        • {total_tables} tables with preserved structure
        • {total_checkboxes} checkboxes detected
        • {total_radio_buttons} radio buttons identified
        
        <b>Content Overview:</b>
        • Complete email body text
        • Full text extraction from all PDF attachments
        • Structured table data with original formatting
        • Form element analysis (checkboxes, radio buttons)
        • Complete content from Word documents, Excel spreadsheets, and other formats
        """
        elements.append(Paragraph(summary_text, self.styles['BodyTextCustom']))
        
        return elements

    def _create_attachment_subsection(self, attachment: Dict, index: int) -> List:
        """Create subsection for a single attachment with FULL content and structured data"""
        elements = []
        
        filename = attachment.get('filename', f'Attachment_{index}')
        file_type = attachment.get('file_type', 'Unknown')
        file_size = attachment.get('file_size', 0)
        pages = attachment.get('pages', 1)
        word_count = attachment.get('word_count', 0)
        success = attachment.get('extraction_success', False)
        content = attachment.get('content', '')
        
        # Enhanced header table with structured data info
        structured_summary = attachment.get('structured_data_summary', {})
        table_count = structured_summary.get('table_count', 0)
        checkbox_count = structured_summary.get('checkbox_count', 0)
        radio_count = structured_summary.get('radio_button_count', 0)
        
        header_data = [
            [f'Attachment {index}: {filename}', ''],
            ['File Type:', file_type.upper() if file_type else 'Unknown'],
            ['File Size:', f"{file_size / 1024:.1f} KB"],
            ['Estimated Pages:', str(pages)],
            ['Word Count:', f"{word_count:,}"],
            ['Tables Extracted:', str(table_count)],
            ['Form Elements:', f"✓: {checkbox_count}, ○: {radio_count}"],
            ['Extraction Status:', 'SUCCESS' if success else 'FAILED']
        ]
        
        header_table = Table(header_data, colWidths=[2.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (1, 1), (1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 12))
        
        # Add extracted tables section
        if attachment.get('tables'):
            elements.append(Paragraph("<b>Extracted Tables:</b>", self.styles['SectionHeader']))
            elements.append(Spacer(1, 6))
            
            for i, table_data in enumerate(attachment.get('tables', []), 1):
                elements.append(Paragraph(f"Table {i} (Page {table_data.get('page', 'N/A')}):", self.styles['BodyTextCustom']))
                elements.append(Spacer(1, 3))
                
                # Create PDF table
                pdf_table = self.create_table_for_pdf(table_data.get('data', []))
                elements.append(pdf_table)
                elements.append(Spacer(1, 12))
        
        # Add form elements section
        form_elements = attachment.get('form_elements', {})
        if form_elements.get('checkboxes') or form_elements.get('radio_buttons'):
            elements.append(Paragraph("<b>Form Elements Detected:</b>", self.styles['SectionHeader']))
            elements.append(Spacer(1, 6))
            
            if form_elements.get('checkboxes'):
                elements.append(Paragraph(f"Checkboxes found: {len(form_elements['checkboxes'])}", self.styles['BodyTextCustom']))
                for cb in form_elements['checkboxes'][:5]:  # Show first 5
                    elements.append(Paragraph(f"• Page {cb['page']}: Position {cb['position']} - Status: {cb['status']}", 
                                           self.styles['SmallTextCustom']))
                if len(form_elements['checkboxes']) > 5:
                    elements.append(Paragraph(f"... and {len(form_elements['checkboxes']) - 5} more checkboxes", 
                                           self.styles['SmallTextCustom']))
            
            if form_elements.get('radio_buttons'):
                elements.append(Paragraph(f"Radio buttons found: {len(form_elements['radio_buttons'])}", self.styles['BodyTextCustom']))
                for rb in form_elements['radio_buttons'][:5]:  # Show first 5
                    elements.append(Paragraph(f"• Page {rb['page']}: Position {rb['position']} - Status: {rb['status']}", 
                                           self.styles['SmallTextCustom']))
                if len(form_elements['radio_buttons']) > 5:
                    elements.append(Paragraph(f"... and {len(form_elements['radio_buttons']) - 5} more radio buttons", 
                                           self.styles['SmallTextCustom']))
            
            elements.append(Spacer(1, 12))
        
        # Add extracted content
        if success and content:
            elements.append(Paragraph("<b>Extracted Text Content:</b>", self.styles['BodyTextCustom']))
            elements.append(Spacer(1, 6))
            
            # Process content for PDF display
            if len(content) > 10000:
                content_preview = content[:10000] + f"\n\n...[Content truncated. Full {word_count:,} words available in separate text file.]..."
            else:
                content_preview = content
            
            # Split content into manageable chunks
            content_lines = content_preview.split('\n')
            for line_num, line in enumerate(content_lines[:100]):  # Limit lines for PDF
                if line.strip():
                    elements.append(Paragraph(line, self.styles['CodeText']))
            
            if len(content_lines) > 100:
                elements.append(Paragraph(f"...[Additional {len(content_lines) - 100} lines truncated for PDF display]...", 
                                       self.styles['SmallTextCustom']))
        
        elif not success:
            error_msg = attachment.get('content', 'Extraction failed')
            elements.append(Paragraph(f"<b>Extraction Error:</b> {error_msg}", self.styles['SmallTextCustom']))
        
        elements.append(Spacer(1, 12))
        
        return elements

    def create_extracted_text_file(self, email_data: Dict, saved_paths: Dict, attachment_results: Dict) -> str:
        """Create a comprehensive text file with ALL extracted content including structured data"""
        try:
            claim_number = self.extract_claim_number(email_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            text_filename = f"Full_Extracted_Content_{claim_number}_{timestamp}.txt"
            text_path = os.path.join(self.output_dir, text_filename)
            
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write("MARINE INSURANCE CLAIM - COMPLETE EXTRACTED CONTENT WITH STRUCTURED DATA\n")
                f.write("=" * 100 + "\n")
                f.write(f"Claim Number: {claim_number}\n")
                f.write(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Attachments: {attachment_results.get('total_attachments', 0)}\n")
                f.write(f"Successful Extractions: {attachment_results.get('successful_extractions', 0)}\n")
                f.write("=" * 100 + "\n\n")
                
                # Email content
                f.write("SECTION 1: EMAIL CONTENT\n")
                f.write("-" * 50 + "\n")
                f.write(f"Subject: {email_data.get('subject', '')}\n")
                f.write(f"From: {email_data.get('sender_name', '')} <{email_data.get('sender_email', '')}>\n")
                f.write(f"Date: {email_data.get('date', '')}\n")
                f.write(f"Body Length: {len(email_data.get('body', ''))} characters\n\n")
                f.write("EMAIL BODY:\n")
                f.write("-" * 30 + "\n")
                f.write(email_data.get('body', 'No email body content') + "\n\n")
                
                # Attachments content with structured data
                f.write("SECTION 2: ATTACHMENTS CONTENT WITH STRUCTURED DATA\n")
                f.write("-" * 50 + "\n")
                
                for i, attachment in enumerate(attachment_results.get('attachments', []), 1):
                    f.write(f"\n{'='*80}\n")
                    f.write(f"ATTACHMENT {i}: {attachment.get('filename', 'Unknown')}\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"File Type: {attachment.get('file_type', 'Unknown')}\n")
                    f.write(f"File Size: {attachment.get('file_size', 0)} bytes\n")
                    f.write(f"Word Count: {attachment.get('word_count', 0)}\n")
                    f.write(f"Pages: {attachment.get('pages', 1)}\n")
                    f.write(f"Tables Extracted: {attachment.get('structured_data_summary', {}).get('table_count', 0)}\n")
                    f.write(f"Form Elements: Checkboxes: {attachment.get('structured_data_summary', {}).get('checkbox_count', 0)}, ")
                    f.write(f"Radio Buttons: {attachment.get('structured_data_summary', {}).get('radio_button_count', 0)}\n")
                    f.write(f"Extraction: {'SUCCESS' if attachment.get('extraction_success') else 'FAILED'}\n")
                    f.write("-" * 50 + "\n")
                    
                    # Write tables
                    if attachment.get('tables'):
                        f.write("\nEXTRACTED TABLES:\n")
                        f.write("-" * 30 + "\n")
                        for table_idx, table in enumerate(attachment.get('tables', []), 1):
                            f.write(f"\nTable {table_idx} (Page {table.get('page', 'N/A')}):\n")
                            for row in table.get('data', []):
                                f.write(" | ".join(str(cell) for cell in row) + "\n")
                            f.write("\n")
                    
                    # Write form elements
                    form_elements = attachment.get('form_elements', {})
                    if form_elements.get('checkboxes') or form_elements.get('radio_buttons'):
                        f.write("\nFORM ELEMENTS:\n")
                        f.write("-" * 30 + "\n")
                        if form_elements.get('checkboxes'):
                            f.write(f"Checkboxes ({len(form_elements['checkboxes'])}):\n")
                            for cb in form_elements['checkboxes']:
                                f.write(f"  Page {cb['page']}: Position {cb['position']} - {cb['status']}\n")
                        if form_elements.get('radio_buttons'):
                            f.write(f"Radio Buttons ({len(form_elements['radio_buttons'])}):\n")
                            for rb in form_elements['radio_buttons']:
                                f.write(f"  Page {rb['page']}: Position {rb['position']} - {rb['status']}\n")
                    
                    # Write content
                    content = attachment.get('content', 'No content extracted')
                    f.write("\nEXTRACTED TEXT CONTENT:\n")
                    f.write("-" * 30 + "\n")
                    f.write(content + "\n")
                
                f.write("\n" + "=" * 100 + "\n")
                f.write("END OF EXTRACTED CONTENT\n")
                f.write("=" * 100 + "\n")
            
            return text_path
        except Exception as e:
            logger.error(f"Error creating comprehensive text file: {str(e)}")
            return ""

    # Keep the existing methods that haven't been modified
    def _create_email_content_section(self, email_data: Dict) -> List:
        """Create section with email content (unchanged from original)"""
        # ... (keep the original implementation)
        elements = []
        
        elements.append(Paragraph("EMAIL CONTENT ANALYSIS", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        # Email metadata
        metadata_text = f"""
        <b>Email Details:</b><br/>
        • Subject: {email_data['subject']}<br/>
        • Sender: {email_data.get('sender_name', 'Unknown')} ({email_data.get('sender_email', 'Unknown')})<br/>
        • Date: {email_data.get('date', 'Unknown')}<br/>
        • Body Length: {len(email_data.get('body', ''))} characters<br/>
        """
        elements.append(Paragraph(metadata_text, self.styles['BodyTextCustom']))
        elements.append(Spacer(1, 12))
        
        # Email body
        elements.append(Paragraph("<b>Complete Email Body Content:</b>", self.styles['BodyTextCustom']))
        elements.append(Spacer(1, 6))
        
        body = email_data.get('body', 'No content available')
        if len(body) > 50000:
            body = body[:50000] + "\n\n...[Content truncated for PDF size optimization. Full content available in separate text file.]..."
        
        # Split body into paragraphs with better formatting
        paragraphs = body.split('\n')
        for para in paragraphs:
            if para.strip():
                clean_para = para.replace('\t', '    ').replace('  ', ' ')
                elements.append(Paragraph(clean_para, self.styles['BodyTextCustom']))
        
        return elements

    def _create_attachments_content_section(self, attachment_results: Dict) -> List:
        """Create section with FULL extracted attachment content (modified to use enhanced subsection)"""
        elements = []
        
        elements.append(Paragraph("COMPLETE ATTACHMENTS CONTENT EXTRACTION", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        if not attachment_results.get('attachments'):
            elements.append(Paragraph("No attachments found or processed.", self.styles['BodyTextCustom']))
            return elements
        
        # Attachment summary with structured data
        total_tables = sum(att.get('structured_data_summary', {}).get('table_count', 0) 
                          for att in attachment_results.get('attachments', []))
        total_checkboxes = sum(att.get('structured_data_summary', {}).get('checkbox_count', 0) 
                              for att in attachment_results.get('attachments', []))
        total_radio_buttons = sum(att.get('structured_data_summary', {}).get('radio_button_count', 0) 
                                 for att in attachment_results.get('attachments', []))
        
        summary_text = f"""
        <b>Attachment Processing Summary:</b><br/>
        • Total Attachments: {attachment_results.get('total_attachments', 0)}<br/>
        • Successfully Extracted: {attachment_results.get('successful_extractions', 0)}<br/>
        • Failed Extractions: {attachment_results.get('failed_extractions', 0)}<br/>
        • Tables Extracted: {total_tables}<br/>
        • Form Elements: Checkboxes: {total_checkboxes}, Radio Buttons: {total_radio_buttons}<br/>
        • Total Words Extracted: {sum(att.get('word_count', 0) for att in attachment_results.get('attachments', [])):,}<br/>
        """
        elements.append(Paragraph(summary_text, self.styles['BodyTextCustom']))
        elements.append(Spacer(1, 12))
        
        # Process each attachment with FULL content and structured data
        for i, attachment in enumerate(attachment_results.get('attachments', []), 1):
            elements.extend(self._create_attachment_subsection(attachment, i))
            if i < len(attachment_results.get('attachments', [])):
                elements.append(PageBreak())
        
        return elements

    def _create_processing_section(self, saved_paths: Dict, attachment_results: Dict) -> List:
        """Create processing information section (enhanced with structured data info)"""
        elements = []
        
        elements.append(Paragraph("PROCESSING DETAILS", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        total_words = sum(att.get('word_count', 0) for att in attachment_results.get('attachments', []))
        total_tables = sum(att.get('structured_data_summary', {}).get('table_count', 0) 
                          for att in attachment_results.get('attachments', []))
        
        processing_info = f"""
        <b>System Processing Information:</b><br/>
        • Processing Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
        • Storage Directory: {saved_paths.get('email_folder', 'N/A')}<br/>
        • Original Files Preserved: {len(saved_paths.get('attachments', []))}<br/>
        • Text Extraction Success Rate: {attachment_results.get('successful_extractions', 0)}/{attachment_results.get('total_attachments', 1)}<br/>
        • Tables Extracted: {total_tables}<br/>
        • Total Words Processed: {total_words:,}<br/>
        • Generated By: Marine Insurance Claims AI Processing System<br/>
        • Next Step: This comprehensive PDF with structured data is ready for Gemini AI fraud detection analysis<br/>
        """
        elements.append(Paragraph(processing_info, self.styles['SmallTextCustom']))
        
        return elements

    def get_extraction_statistics(self, attachment_results: Dict) -> Dict[str, Any]:
        """Get detailed statistics about the extraction process (enhanced with structured data)"""
        stats = {
            'total_attachments': attachment_results.get('total_attachments', 0),
            'successful_extractions': attachment_results.get('successful_extractions', 0),
            'failed_extractions': attachment_results.get('failed_extractions', 0),
            'total_words': 0,
            'total_pages': 0,
            'total_tables': 0,
            'total_checkboxes': 0,
            'total_radio_buttons': 0,
            'file_types': {}
        }
        
        for attachment in attachment_results.get('attachments', []):
            stats['total_words'] += attachment.get('word_count', 0)
            stats['total_pages'] += attachment.get('pages', 1)
            
            structured_data = attachment.get('structured_data_summary', {})
            stats['total_tables'] += structured_data.get('table_count', 0)
            stats['total_checkboxes'] += structured_data.get('checkbox_count', 0)
            stats['total_radio_buttons'] += structured_data.get('radio_button_count', 0)
            
            file_type = attachment.get('file_type', 'unknown')
            if file_type not in stats['file_types']:
                stats['file_types'][file_type] = 0
            stats['file_types'][file_type] += 1
        
        stats['success_rate'] = (stats['successful_extractions'] / stats['total_attachments'] * 100) if stats['total_attachments'] > 0 else 0
        
        return stats