import os
import json
import logging
from typing import Dict, Any, List
import google.generativeai as genai

from config.settings import settings
from .gemini_client import GeminiClient
from .prompts import CLAIM_ANALYSIS_PROMPT
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ClaimsAnalyzer:
    def __init__(self):
        self.gemini_client = GeminiClient()
    
    def analyze_claim(self, claim_text: str, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze claim document using Gemini AI"""
        try:
            logger.info("Starting claim analysis with Gemini AI")
            
            # Prepare context for analysis
            context = {
                'email_subject': email_data.get('subject', ''),
                'sender_email': email_data.get('sender_email', ''),
                'email_date': email_data.get('date', ''),
                'attachment_count': len(email_data.get('attachments', [])),
                'claim_content': claim_text[:10000]  # Limit context size
            }
            
            # Generate analysis prompt
            prompt = self._build_analysis_prompt(context)
            
            # Get AI analysis
            analysis_result = self.gemini_client.analyze_content(prompt)
            
            # Parse and structure the analysis
            structured_analysis = self._parse_analysis_result(analysis_result, context)
            
            logger.info("Claim analysis completed successfully")
            return structured_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing claim: {str(e)}")
            return self._get_default_analysis()
    
    def _build_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Build comprehensive analysis prompt"""
        return f"""
        {CLAIM_ANALYSIS_PROMPT}
        
        EMAIL CONTEXT:
        - Subject: {context['email_subject']}
        - Sender: {context['sender_email']}
        - Date: {context['email_date']}
        - Attachments: {context['attachment_count']}
        
        CLAIM DOCUMENT CONTENT:
        {context['claim_content']}
        
        Please analyze this marine insurance claim thoroughly and provide a structured JSON response.
        """
    
    def _parse_analysis_result(self, analysis_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI analysis result into structured data"""
        try:
            # Try to extract JSON from the response
            if '```json' in analysis_text:
                json_str = analysis_text.split('```json')[1].split('```')[0].strip()
            elif '```' in analysis_text:
                json_str = analysis_text.split('```')[1].strip()
            else:
                json_str = analysis_text
            
            analysis_data = json.loads(json_str)
            
            # Add metadata
            analysis_data['analysis_timestamp'] = context.get('email_date', '')
            analysis_data['source_email'] = context['sender_email']
            analysis_data['content_length'] = len(context['claim_content'])
            
            return analysis_data
            
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON from AI response, using text analysis")
            return self._structure_text_analysis(analysis_text, context)
    
    def _structure_text_analysis(self, analysis_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Structure text analysis when JSON parsing fails"""
        return {
            'claim_number': self._extract_claim_number(analysis_text),
            'insured_party': 'Unknown',
            'loss_date': 'Unknown',
            'loss_location': 'Unknown',
            'claim_amount': 0.0,
            'currency': 'USD',
            'loss_description': analysis_text[:500],
            'analysis_summary': analysis_text,
            'key_findings': ['Analysis completed but structured parsing failed'],
            'recommendations': ['Review claim manually for detailed assessment'],
            'confidence_score': 0.5,
            'analysis_timestamp': context.get('email_date', ''),
            'source_email': context['sender_email'],
            'raw_analysis': analysis_text
        }
    
    def _extract_claim_number(self, text: str) -> str:
        """Extract claim number from text"""
        import re
        # Common claim number patterns
        patterns = [
            r'Claim[:\s]*([A-Z0-9-]+)',
            r'Claim\s*Number[:\s]*([A-Z0-9-]+)',
            r'CLM[:\s]*([A-Z0-9-]+)',
            r'#([A-Z]{2,3}\d{5,})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return f"CLM-{hash(text) % 100000:05d}"  # Fallback
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Return default analysis structure when analysis fails"""
        return {
            'claim_number': 'UNKNOWN',
            'insured_party': 'Unknown',
            'loss_date': 'Unknown',
            'loss_location': 'Unknown',
            'claim_amount': 0.0,
            'currency': 'USD',
            'loss_description': 'Analysis failed',
            'analysis_summary': 'AI analysis could not be completed',
            'key_findings': ['Analysis system error'],
            'recommendations': ['Manual review required'],
            'confidence_score': 0.0,
            'analysis_timestamp': '',
            'source_email': '',
            'raw_analysis': ''
        }