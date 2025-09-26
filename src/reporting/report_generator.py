import os
import json
import logging
from datetime import datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom styles for PDF reports"""
        # Title style
        self.styles.add(ParagraphStyle(
            'ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.darkblue,
            spaceAfter=12,
            alignment=1  # Center aligned
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.darkblue,
            spaceAfter=6,
            spaceBefore=12
        ))
        
        # Highlight style for important findings
        self.styles.add(ParagraphStyle(
            'Highlight',
            parent=self.styles['Normal'],
            backColor=colors.lightgrey,
            borderPadding=5,
            spaceAfter=6
        ))
    
    def generate_claim_report(self, report_data: Dict[str, Any]) -> str:
        """Generate comprehensive PDF report for a claim"""
        try:
            claim_number = report_data['claim_analysis'].get('claim_number', 'UNKNOWN')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"claim_report_{claim_number}_{timestamp}.pdf"
            report_path = os.path.join(settings.REPORTS_DIR, report_filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(report_path, pagesize=A4, topMargin=0.5*inch)
            story = []
            
            # Add report sections
            story.extend(self._create_header_section(report_data))
            story.append(Spacer(1, 0.2*inch))
            
            story.extend(self._create_executive_summary(report_data))
            story.append(Spacer(1, 0.1*inch))
            
            story.extend(self._create_claim_details_section(report_data))
            story.append(Spacer(1, 0.1*inch))
            
            story.extend(self._create_fraud_analysis_section(report_data))
            story.append(Spacer(1, 0.1*inch))
            
            story.extend(self._create_duplicate_check_section(report_data))
            story.append(Spacer(1, 0.1*inch))
            
            story.extend(self._create_recommendations_section(report_data))
            story.append(Spacer(1, 0.1*inch))
            
            story.extend(self._create_technical_details_section(report_data))
            
            # Build PDF
            doc.build(story)
            logger.info(f"Claim report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating claim report: {str(e)}")
            raise
    
    def _create_header_section(self, report_data: Dict[str, Any]) -> list:
        """Create report header section"""
        elements = []
        
        # Title
        elements.append(Paragraph("MARINE INSURANCE CLAIM ANALYSIS REPORT", self.styles['ReportTitle']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Basic info table
        claim_analysis = report_data['claim_analysis']
        email_data = report_data['email_data']
        
        info_data = [
            ['Claim Number:', claim_analysis.get('claim_number', 'Unknown')],
            ['Insured Party:', claim_analysis.get('insured_party', 'Unknown')],
            ['Loss Date:', claim_analysis.get('loss_date', 'Unknown')],
            ['Claim Amount:', f"{claim_analysis.get('claim_amount', 0):,.2f} {claim_analysis.get('currency', 'USD')}"],
            ['Report Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Analyst:', 'AI Claims Processing System'],
            ['Status:', 'Automated Analysis Complete']
        ]
        
        info_table = Table(info_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        elements.append(info_table)
        return elements
    
    def _create_executive_summary(self, report_data: Dict[str, Any]) -> list:
        """Create executive summary section"""
        elements = []
        
        elements.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        
        fraud_analysis = report_data['fraud_analysis']
        duplicate_check = report_data['duplicate_check']
        claim_analysis = report_data['claim_analysis']
        
        # Risk assessment
        fraud_score = fraud_analysis.get('fraud_score', 0)
        risk_level = fraud_analysis.get('risk_level', 'UNKNOWN')
        is_duplicate = duplicate_check.get('is_duplicate', False)
        
        risk_color = colors.red if fraud_score > 0.7 else colors.orange if fraud_score > 0.4 else colors.green
        
        summary_text = f"""
        This automated analysis of marine insurance claim {claim_analysis.get('claim_number', 'Unknown')} 
        has been completed. Key findings include:
        
        • <b>Fraud Risk:</b> <font color="{risk_color}">{risk_level} ({fraud_score:.1%})</font>
        • <b>Duplicate Check:</b> {'DUPLICATE CLAIM DETECTED' if is_duplicate else 'No duplicates found'}
        • <b>Claim Amount:</b> {claim_analysis.get('claim_amount', 0):,.2f} {claim_analysis.get('currency', 'USD')}
        • <b>Confidence Score:</b> {claim_analysis.get('confidence_score', 0):.1%}
        
        {claim_analysis.get('analysis_summary', 'Analysis completed successfully.')}
        """
        
        elements.append(Paragraph(summary_text, self.styles['Normal']))
        return elements
    
    def _create_claim_details_section(self, report_data: Dict[str, Any]) -> list:
        """Create claim details section"""
        elements = []
        
        elements.append(Paragraph("CLAIM DETAILS", self.styles['SectionHeader']))
        
        claim_analysis = report_data['claim_analysis']
        
        # Loss description
        loss_desc = claim_analysis.get('loss_description', 'No description provided')
        elements.append(Paragraph("<b>Loss Description:</b>", self.styles['Normal']))
        elements.append(Paragraph(loss_desc, self.styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Key findings
        elements.append(Paragraph("<b>Key Findings:</b>", self.styles['Normal']))
        for finding in claim_analysis.get('key_findings', []):
            elements.append(Paragraph(f"• {finding}", self.styles['Normal']))
        
        return elements
    
    def _create_fraud_analysis_section(self, report_data: Dict[str, Any]) -> list:
        """Create fraud analysis section"""
        elements = []
        
        elements.append(Paragraph("FRAUD RISK ANALYSIS", self.styles['SectionHeader']))
        
        fraud_analysis = report_data['fraud_analysis']
        fraud_score = fraud_analysis.get('fraud_score', 0)
        
        # Risk indicator
        risk_text = f"Overall Fraud Risk Score: {fraud_score:.1%} ({fraud_analysis.get('risk_level', 'UNKNOWN')})"
        elements.append(Paragraph(risk_text, self.styles['Highlight']))
        elements.append(Spacer(1, 0.05*inch))
        
        # Red flags
        red_flags = fraud_analysis.get('red_flags', [])
        if red_flags:
            elements.append(Paragraph("<b>Red Flags Identified:</b>", self.styles['Normal']))
            for flag in red_flags[:5]:  # Show top 5 flags
                elements.append(Paragraph(f"• {flag}", self.styles['Normal']))
        else:
            elements.append(Paragraph("No significant red flags identified.", self.styles['Normal']))
        
        return elements
    
    def _create_duplicate_check_section(self, report_data: Dict[str, Any]) -> list:
        """Create duplicate check section"""
        elements = []
        
        elements.append(Paragraph("DUPLICATE CLAIM CHECK", self.styles['SectionHeader']))
        
        duplicate_check = report_data['duplicate_check']
        
        if duplicate_check.get('is_duplicate', False):
            duplicate_info = f"""
            <b>DUPLICATE CLAIM DETECTED</b><br/>
            This claim appears to be a duplicate of: {duplicate_check.get('duplicate_of', 'Unknown')}<br/>
            Confidence: {duplicate_check.get('confidence', 0):.1%}<br/>
            Match Type: {duplicate_check.get('match_type', 'Unknown')}
            """
            elements.append(Paragraph(duplicate_info, self.styles['Highlight']))
        else:
            elements.append(Paragraph("No duplicate claims detected.", self.styles['Normal']))
        
        return elements
    
    def _create_recommendations_section(self, report_data: Dict[str, Any]) -> list:
        """Create recommendations section"""
        elements = []
        
        elements.append(Paragraph("RECOMMENDATIONS", self.styles['SectionHeader']))
        
        claim_analysis = report_data['claim_analysis']
        fraud_analysis = report_data['fraud_analysis']
        
        # Combine recommendations
        all_recommendations = claim_analysis.get('recommendations', []) + fraud_analysis.get('recommendations', [])
        
        if all_recommendations:
            for i, recommendation in enumerate(all_recommendations[:5], 1):  # Top 5 recommendations
                elements.append(Paragraph(f"{i}. {recommendation}", self.styles['Normal']))
        else:
            elements.append(Paragraph("No specific recommendations generated.", self.styles['Normal']))
        
        return elements
    
    def _create_technical_details_section(self, report_data: Dict[str, Any]) -> list:
        """Create technical details section"""
        elements = []
        
        elements.append(Paragraph("TECHNICAL DETAILS", self.styles['SectionHeader']))
        
        tech_data = [
            ['Processing Timestamp:', report_data['processing_timestamp']],
            ['Analysis Method:', 'AI-Powered Automated Analysis'],
            ['Data Sources:', 'Email content + Attachments + Historical data'],
            ['AI Model:', 'Gemini AI'],
            ['System Version:', 'Marine Claims Processor v1.0']
        ]
        
        tech_table = Table(tech_data, colWidths=[2*inch, 3.5*inch])
        tech_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        elements.append(tech_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # Disclaimer
        disclaimer = """
        <i>This is an automated analysis report generated by AI systems. 
        The findings should be verified by qualified insurance professionals 
        before making any final decisions. The system confidence score 
        represents the AI's assessment of its own analysis accuracy.</i>
        """
        elements.append(Paragraph(disclaimer, self.styles['Italic']))
        
        return elements