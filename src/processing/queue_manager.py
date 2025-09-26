import os
import json
import logging
import shutil
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass

from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class ProcessingItem:
    claim_number: str
    pdf_path: str
    email_data: Dict[str, Any]
    extracted_content_path: str
    created_at: str
    status: str = 'queued'  # queued, processing, completed, failed

class ProcessingQueueManager:
    def __init__(self):
        self.queue_dir = settings.PROCESSING_QUEUE_DIR
        self.processed_dir = settings.PROCESSED_CLAIMS_DIR
        self.queue_file = os.path.join(self.queue_dir, 'processing_queue.json')
        
    def add_to_queue(self, pdf_path: str, email_data: Dict[str, Any], extracted_content_path: str = "") -> str:
        """Add a new item to the processing queue"""
        try:
            # Generate claim number or use existing one
            claim_number = email_data.get('claim_number', f"CLAIM_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Create processing item
            processing_item = ProcessingItem(
                claim_number=claim_number,
                pdf_path=pdf_path,
                email_data=email_data,
                extracted_content_path=extracted_content_path,
                created_at=datetime.now().isoformat(),
                status='queued'
            )
            
            # Load existing queue
            queue = self._load_queue()
            
            # Add new item
            queue.append({
                'claim_number': processing_item.claim_number,
                'pdf_path': processing_item.pdf_path,
                'email_data': processing_item.email_data,
                'extracted_content_path': processing_item.extracted_content_path,
                'created_at': processing_item.created_at,
                'status': processing_item.status
            })
            
            # Save queue
            self._save_queue(queue)
            
            # Create a dedicated folder for this claim in processing queue
            claim_folder = os.path.join(self.queue_dir, processing_item.claim_number)
            os.makedirs(claim_folder, exist_ok=True)
            
            # Copy PDF to claim folder
            if os.path.exists(pdf_path):
                pdf_filename = os.path.basename(pdf_path)
                target_pdf_path = os.path.join(claim_folder, pdf_filename)
                shutil.copy2(pdf_path, target_pdf_path)
            
            logger.info(f"Added claim {processing_item.claim_number} to processing queue")
            return processing_item.claim_number
            
        except Exception as e:
            logger.error(f"Error adding item to processing queue: {str(e)}")
            raise
    
    def get_next_batch(self, batch_size: int = None) -> List[Dict[str, Any]]:
        """Get the next batch of items for processing"""
        if batch_size is None:
            batch_size = settings.PROCESSING_BATCH_SIZE
            
        queue = self._load_queue()
        queued_items = [item for item in queue if item['status'] == 'queued']
        
        # Return oldest items first
        queued_items.sort(key=lambda x: x['created_at'])
        
        return queued_items[:batch_size]
    
    def mark_as_processing(self, claim_number: str):
        """Mark an item as being processed"""
        self._update_status(claim_number, 'processing')
    
    def mark_as_completed(self, claim_number: str, results: Dict[str, Any] = None):
        """Mark an item as completed and move to processed folder"""
        try:
            # Update status
            self._update_status(claim_number, 'completed')
            
            # Move to processed folder
            source_folder = os.path.join(self.queue_dir, claim_number)
            target_folder = os.path.join(self.processed_dir, claim_number)
            
            if os.path.exists(source_folder):
                if os.path.exists(target_folder):
                    shutil.rmtree(target_folder)
                shutil.move(source_folder, target_folder)
                
                # Save processing results
                if results:
                    results_file = os.path.join(target_folder, 'processing_results.json')
                    with open(results_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Claim {claim_number} processing completed")
            
        except Exception as e:
            logger.error(f"Error marking claim {claim_number} as completed: {str(e)}")
    
    def mark_as_failed(self, claim_number: str, error_message: str):
        """Mark an item as failed"""
        self._update_status(claim_number, 'failed')
        
        # Save error details
        claim_folder = os.path.join(self.queue_dir, claim_number)
        error_file = os.path.join(claim_folder, 'error_log.json')
        
        error_data = {
            'claim_number': claim_number,
            'error_message': error_message,
            'failed_at': datetime.now().isoformat()
        }
        
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)
        
        logger.error(f"Claim {claim_number} processing failed: {error_message}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        queue = self._load_queue()
        
        status = {
            'total': len(queue),
            'queued': len([item for item in queue if item['status'] == 'queued']),
            'processing': len([item for item in queue if item['status'] == 'processing']),
            'completed': len([item for item in queue if item['status'] == 'completed']),
            'failed': len([item for item in queue if item['status'] == 'failed'])
        }
        
        return status
    
    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load the processing queue from file"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading queue: {str(e)}")
            return []
    
    def _save_queue(self, queue: List[Dict[str, Any]]):
        """Save the processing queue to file"""
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving queue: {str(e)}")
            raise
    
    def _update_status(self, claim_number: str, status: str):
        """Update the status of a specific claim"""
        queue = self._load_queue()
        
        for item in queue:
            if item['claim_number'] == claim_number:
                item['status'] = status
                item['updated_at'] = datetime.now().isoformat()
                break
        
        self._save_queue(queue)