import json
import logging
from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher
import hashlib

from config.settings import settings
from .gemini_client import GeminiClient
from .prompts import DUPLICATE_DETECTION_PROMPT
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DuplicateDetector:
    def __init__(self):
        self.gemini_client = GeminiClient()
    
    def check_duplicate(self, current_claim: Dict[str, Any], processed_claims: Dict[str, Any]) -> Dict[str, Any]:
        """Check if current claim is a duplicate of previously processed claims"""
        try:
            logger.info("Checking for duplicate claims")
            
            if not processed_claims:
                return {'is_duplicate': False, 'confidence': 0.0}
            
            # Multiple detection methods
            exact_matches = self._check_exact_matches(current_claim, processed_claims)
            similar_matches = self._check_similar_matches(current_claim, processed_claims)
            ai_matches = self._ai_duplicate_check(current_claim, processed_claims)
            
            # Combine results
            duplicate_result = self._combine_duplicate_results(
                exact_matches, similar_matches, ai_matches
            )
            
            logger.info(f"Duplicate check completed: {duplicate_result['is_duplicate']}")
            return duplicate_result
            
        except Exception as e:
            logger.error(f"Error in duplicate detection: {str(e)}")
            return {'is_duplicate': False, 'confidence': 0.0, 'error': str(e)}
    
    def _check_exact_matches(self, current_claim: Dict[str, Any], processed_claims: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for exact matches using claim fingerprints"""
        matches = []
        current_fingerprint = self._create_claim_fingerprint(current_claim)
        
        for claim_id, existing_claim in processed_claims.items():
            existing_fingerprint = self._create_claim_fingerprint(existing_claim)
            
            if current_fingerprint == existing_fingerprint:
                matches.append({
                    'claim_id': claim_id,
                    'match_type': 'exact',
                    'confidence': 1.0,
                    'matching_fields': ['full_claim_fingerprint']
                })
        
        return matches
    
    def _check_similar_matches(self, current_claim: Dict[str, Any], processed_claims: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for similar matches using fuzzy matching"""
        matches = []
        current_text = self._get_claim_text(current_claim)
        
        for claim_id, existing_claim in processed_claims.items():
            existing_text = self._get_claim_text(existing_claim)
            
            similarity = self._calculate_similarity(current_text, existing_text)
            
            if similarity > settings.DUPLICATE_THRESHOLD:
                matches.append({
                    'claim_id': claim_id,
                    'match_type': 'similar',
                    'confidence': similarity,
                    'matching_fields': ['claim_content']
                })
        
        return matches
    
    def _ai_duplicate_check(self, current_claim: Dict[str, Any], processed_claims: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use AI to detect sophisticated duplicates"""
        try:
            if len(processed_claims) > 10:  # Limit for performance
                sample_claims = dict(list(processed_claims.items())[:10])
            else:
                sample_claims = processed_claims
            
            prompt = self._build_duplicate_prompt(current_claim, sample_claims)
            ai_result = self.gemini_client.analyze_content(prompt)
            
            return self._parse_ai_duplicate_result(ai_result, processed_claims)
            
        except Exception as e:
            logger.error(f"AI duplicate check failed: {str(e)}")
            return []
    
    def _build_duplicate_prompt(self, current_claim: Dict[str, Any], processed_claims: Dict[str, Any]) -> str:
        """Build prompt for AI duplicate detection"""
        return f"""
        {DUPLICATE_DETECTION_PROMPT}
        
        CURRENT CLAIM:
        {json.dumps(current_claim, indent=2)}
        
        PREVIOUSLY PROCESSED CLAIMS:
        {json.dumps(processed_claims, indent=2)}
        
        Analyze if the current claim is a duplicate or variation of any previously processed claims.
        Consider similarities in: claim details, amounts, dates, parties involved, and loss descriptions.
        """
    
    def _parse_ai_duplicate_result(self, ai_text: str, processed_claims: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse AI duplicate detection results"""
        try:
            if '```json' in ai_text:
                json_str = ai_text.split('```json')[1].split('```')[0].strip()
                ai_result = json.loads(json_str)
            else:
                # Try to extract structured information
                ai_result = {'matches': [], 'confidence': 0.0}
            
            matches = []
            for match in ai_result.get('matches', []):
                claim_id = match.get('claim_id')
                if claim_id in processed_claims:
                    matches.append({
                        'claim_id': claim_id,
                        'match_type': 'ai_detected',
                        'confidence': match.get('confidence', 0.7),
                        'matching_fields': match.get('matching_fields', ['ai_analysis'])
                    })
            
            return matches
            
        except Exception as e:
            logger.warning(f"Could not parse AI duplicate results: {str(e)}")
            return []
    
    def _create_claim_fingerprint(self, claim: Dict[str, Any]) -> str:
        """Create a fingerprint for exact matching"""
        key_fields = [
            claim.get('claim_number', ''),
            claim.get('insured_party', ''),
            str(claim.get('claim_amount', 0)),
            claim.get('loss_date', ''),
            claim.get('loss_location', '')
        ]
        
        fingerprint_text = '|'.join(key_fields)
        return hashlib.md5(fingerprint_text.encode()).hexdigest()
    
    def _get_claim_text(self, claim: Dict[str, Any]) -> str:
        """Extract text for similarity comparison"""
        text_parts = [
            claim.get('claim_number', ''),
            claim.get('insured_party', ''),
            claim.get('loss_description', ''),
            claim.get('loss_location', ''),
            str(claim.get('claim_amount', 0))
        ]
        
        return ' '.join(str(part) for part in text_parts if part)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _combine_duplicate_results(self, exact_matches: List, similar_matches: List, ai_matches: List) -> Dict[str, Any]:
        """Combine results from different detection methods"""
        all_matches = exact_matches + similar_matches + ai_matches
        
        if not all_matches:
            return {'is_duplicate': False, 'confidence': 0.0, 'matches': []}
        
        # Find the best match
        best_match = max(all_matches, key=lambda x: x['confidence'])
        
        return {
            'is_duplicate': True,
            'confidence': best_match['confidence'],
            'duplicate_of': best_match['claim_id'],
            'match_type': best_match['match_type'],
            'all_matches': all_matches,
            'total_matches_found': len(all_matches)
        }