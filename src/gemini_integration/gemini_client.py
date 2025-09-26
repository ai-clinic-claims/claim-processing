import os
import logging
import google.generativeai as genai
from typing import Dict, Any, Optional
from typing import Dict,Any, Optional, List

from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.max_tokens = settings.GEMINI_MAX_TOKENS
        self._configure_client()
    
    def _configure_client(self):
        """Configure Gemini AI client"""
        try:
            if not self.api_key:
                raise ValueError("Gemini API key not configured")
            
            genai.configure(api_key=self.api_key)
            logger.info("Gemini AI client configured successfully")
            
        except Exception as e:
            logger.error(f"Error configuring Gemini client: {str(e)}")
            raise
    
    def analyze_content(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Analyze content using Gemini AI"""
        try:
            model = genai.GenerativeModel(self.model_name)
            
            # Prepare the full prompt
            full_prompt = self._prepare_prompt(prompt, context)
            
            # Generate response
            response = model.generate_content(
                full_prompt,
                generation_config={
                    'max_output_tokens': self.max_tokens,
                    'temperature': 0.1  # Low temperature for consistent results
                }
            )
            
            if response.text:
                logger.info("Gemini AI analysis completed successfully")
                return response.text
            else:
                logger.error("Empty response from Gemini AI")
                return "Analysis failed - empty response"
                
        except Exception as e:
            logger.error(f"Error in Gemini AI analysis: {str(e)}")
            return f"Analysis failed: {str(e)}"
    
    def _prepare_prompt(self, prompt: str, context: Optional[Dict[str, Any]]) -> str:
        """Prepare the complete prompt for Gemini AI"""
        system_message = """
        You are an expert marine insurance claims analyst. Your role is to analyze insurance claims
        for completeness, accuracy, and potential issues. Provide structured, professional analysis
        focusing on key insurance aspects like coverage, liability, damages, and fraud indicators.
        
        Always respond with comprehensive, well-structured analysis that includes:
        1. Clear identification of key claim elements
        2. Assessment of claim validity
        3. Identification of potential issues or red flags
        4. Professional recommendations
        
        Format your response using clear sections and structured data where appropriate.
        """
        
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            return f"{system_message}\n\nCONTEXT:\n{context_str}\n\nPROMPT:\n{prompt}"
        else:
            return f"{system_message}\n\n{prompt}"
    
    def batch_analyze(self, prompts: List[str]) -> List[str]:
        """Analyze multiple prompts in sequence (not parallel due to API limits)"""
        results = []
        
        for i, prompt in enumerate(prompts):
            try:
                logger.info(f"Processing batch item {i+1}/{len(prompts)}")
                result = self.analyze_content(prompt)
                results.append(result)
                
                # Add delay to respect API rate limits
                import time
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in batch analysis item {i+1}: {str(e)}")
                results.append(f"Analysis failed: {str(e)}")
        
        return results