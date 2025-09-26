import json
import logging
from typing import Dict, Any, List
import re

from config.settings import settings
from .gemini_client import GeminiClient
from .prompts import FRAUD_DETECTION_PROMPT
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FraudDetector:
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.fraud_patterns = self._load_fraud_patterns()
    
    def detect_fraud(self, claim_analysis: Dict[str, Any], email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect potential fraud in claim using Gemini AI"""
        try:
            logger.info("Starting fraud detection analysis")
            
            # Combine rule-based and AI-based detection
            rule_based_score = self._rule_based_fraud_detection(claim_analysis, email_data)
            ai_based_analysis = self._ai_based_fraud_detection(claim_analysis, email_data)
            
            # Combine scores
            final_score = self._combine_fraud_scores(rule_based_score, ai_based_analysis)
            
            fraud_result = {
                'fraud_score': final_score,
                'risk_level': self._get_risk_level(final_score),
                'rule_based_score': rule_based_score,
                'ai_analysis': ai_based_analysis,
                'red_flags': self._extract_red_flags(claim_analysis, ai_based_analysis),
                'recommendations': self._generate_fraud_recommendations(final_score, ai_based_analysis),
                'detection_methods': ['rule_based', 'ai_analysis']
            }
            
            logger.info(f"Fraud detection completed - Score: {final_score:.2f}")
            return fraud_result
            
        except Exception as e:
            logger.error(f"Error in fraud detection: {str(e)}")
            return self._get_default_fraud_analysis()
    
    def _rule_based_fraud_detection(self, claim_analysis: Dict[str, Any], email_data: Dict[str, Any]) -> float:
        """Rule-based fraud detection using predefined patterns"""
        score = 0.0
        triggers = []
        
        # Check claim amount anomalies
        claim_amount = claim_analysis.get('claim_amount', 0)
        if claim_amount > 1000000:  # Over $1M
            score += 0.3
            triggers.append("High claim amount")
        
        # Check date inconsistencies
        loss_date = claim_analysis.get('loss_date', '')
        if self._suspicious_date_pattern(loss_date):
            score += 0.2
            triggers.append("Suspicious date pattern")
        
        # Check location patterns
        location = claim_analysis.get('loss_location', '').lower()
        if any(pattern in location for pattern in ['unknown', 'tbd', 'n/a']):
            score += 0.1
            triggers.append("Vague location")
        
        # Check sender email patterns
        sender_email = email_data.get('sender_email', '').lower()
        if self._suspicious_email_pattern(sender_email):
            score += 0.2
            triggers.append("Suspicious sender email")
        
        # Check for urgency language in subject
        subject = email_data.get('subject', '').lower()
        urgency_words = ['urgent', 'immediate', 'asap', 'emergency']
        if any(word in subject for word in urgency_words):
            score += 0.1
            triggers.append("Urgency language")
        
        return min(score, 1.0)
    
    def _ai_based_fraud_detection(self, claim_analysis: Dict[str, Any], email_data: Dict[str, Any]) -> Dict[str, Any]:
        """AI-based fraud detection using Gemini"""
        try:
            prompt = f"""
            {FRAUD_DETECTION_PROMPT}
            
            CLAIM ANALYSIS DATA:
            {json.dumps(claim_analysis, indent=2)}
            
            EMAIL CONTEXT:
            - Subject: {email_data.get('subject', '')}
            - Sender: {email_data.get('sender_email', '')}
            - Date: {email_data.get('date', '')}
            
            Analyze this marine insurance claim for potential fraud indicators and provide a detailed assessment.
            """
            
            analysis_result = self.gemini_client.analyze_content(prompt)
            return self._parse_fraud_analysis(analysis_result)
            
        except Exception as e:
            logger.error(f"AI fraud detection failed: {str(e)}")
            return {'error': str(e), 'score': 0.5}
    
    def _parse_fraud_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse AI fraud analysis result"""
        try:
            if '```json' in analysis_text:
                json_str = analysis_text.split('```json')[1].split('```')[0].strip()
                return json.loads(json_str)
            else:
                return {
                    'fraud_indicators': ['Analysis completed but parsing failed'],
                    'confidence': 0.5,
                    'recommendations': ['Manual review recommended'],
                    'raw_analysis': analysis_text
                }
        except:
            return {
                'fraud_indicators': ['Analysis parsing error'],
                'confidence': 0.5,
                'recommendations': ['System error - manual review required'],
                'raw_analysis': analysis_text
            }
    
    def _suspicious_date_pattern(self, date_str: str) -> bool:
        """Check for suspicious date patterns"""
        if not date_str or date_str.lower() in ['unknown', 'n/a', '']:
            return True
        
        # Check for recent dates only (potential for backdating)
        from datetime import datetime
        try:
            loss_date = datetime.strptime(date_str, '%Y-%m-%d')
            days_diff = (datetime.now() - loss_date).days
            if days_diff < 7:  # Very recent loss
                return True
        except:
            pass
        
        return False
    
    def _suspicious_email_pattern(self, email: str) -> bool:
        """Check for suspicious email patterns"""
        suspicious_domains = ['temp-mail', 'throwaway', 'guerrillamail']
        if any(domain in email for domain in suspicious_domains):
            return True
        
        # Check for numeric patterns (like auto-generated emails)
        if re.search(r'\d{6,}@', email):
            return True
        
        return False
    
    def _combine_fraud_scores(self, rule_score: float, ai_analysis: Dict[str, Any]) -> float:
        """Combine rule-based and AI-based fraud scores"""
        ai_score = ai_analysis.get('confidence', 0.5) if isinstance(ai_analysis, dict) else 0.5
        
        # Weighted combination (60% AI, 40% rules)
        combined_score = (ai_score * 0.6) + (rule_score * 0.4)
        
        return min(combined_score, 1.0)
    
    def _get_risk_level(self, score: float) -> str:
        """Convert fraud score to risk level"""
        if score >= 0.8:
            return "HIGH"
        elif score >= 0.6:
            return "MEDIUM"
        elif score >= 0.4:
            return "LOW"
        else:
            return "VERY LOW"
    
    def _extract_red_flags(self, claim_analysis: Dict[str, Any], ai_analysis: Dict[str, Any]) -> List[str]:
        """Extract red flags from analysis"""
        red_flags = []
        
        # From rule-based detection
        if claim_analysis.get('claim_amount', 0) > 1000000:
            red_flags.append("Exceptionally high claim amount")
        
        # From AI analysis
        if isinstance(ai_analysis, dict):
            indicators = ai_analysis.get('fraud_indicators', [])
            red_flags.extend(indicators)
        
        return red_flags[:10]  # Limit to top 10
    
    def _generate_fraud_recommendations(self, score: float, ai_analysis: Dict[str, Any]) -> List[str]:
        """Generate fraud prevention recommendations"""
        recommendations = []
        
        if score > settings.FRAUD_THRESHOLD:
            recommendations.extend([
                "Immediate investigation required",
                "Contact insured party for verification",
                "Review supporting documentation carefully",
                "Consider involving special investigations unit"
            ])
        elif score > 0.5:
            recommendations.extend([
                "Enhanced documentation review recommended",
                "Verify loss details with independent sources",
                "Check claim history of insured party"
            ])
        else:
            recommendations.append("Standard processing procedures applicable")
        
        # Add AI recommendations if available
        if isinstance(ai_analysis, dict):
            ai_recommendations = ai_analysis.get('recommendations', [])
            recommendations.extend(ai_recommendations)
        
        return list(set(recommendations))[:5]  # Remove duplicates and limit
    
    def _load_fraud_patterns(self) -> Dict[str, Any]:
        """Load known fraud patterns"""
        return {
            'amount_patterns': ['round numbers', 'unusually high', 'inconsistent with history'],
            'date_patterns': ['weekend losses', 'holiday losses', 'recent dates'],
            'location_patterns': ['high-risk areas', 'vague locations', 'multiple locations'],
            'document_patterns': ['inconsistent dates', 'poor quality', 'missing information']
        }
    
    def _get_default_fraud_analysis(self) -> Dict[str, Any]:
        """Return default fraud analysis when detection fails"""
        return {
            'fraud_score': 0.5,
            'risk_level': 'UNKNOWN',
            'rule_based_score': 0.0,
            'ai_analysis': {'error': 'Analysis failed'},
            'red_flags': ['System error in fraud detection'],
            'recommendations': ['Manual fraud assessment required'],
            'detection_methods': ['failed']
        }