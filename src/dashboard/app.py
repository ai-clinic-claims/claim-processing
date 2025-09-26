#!/usr/bin/env python3
"""
Flask Dashboard for Marine Reinsurance Claims Processing System
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from threading import Thread, Event
import time

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from flask import Flask, render_template, send_file, jsonify, request
from config.settings import settings
from processing.pipeline import ClaimsProcessingPipeline
from utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)

app = Flask(__name__)
app.secret_key = 'marine_claims_dashboard_secret_key'

# Global variables for background processing
processing_pipeline = None
background_thread = None
stop_event = Event()
latest_updates = []

class DashboardManager:
    def __init__(self):
        self.reports_dir = settings.REPORTS_DIR
        self.processed_claims_file = os.path.join(settings.PROCESSED_CLAIMS_DIR, 'processed_claims.json')
        self.processing_log_file = os.path.join(settings.REPORTS_DIR, 'processing_log.json')
    
    def get_all_reports(self) -> List[Dict[str, Any]]:
        """Get all generated reports with metadata"""
        reports = []
        
        try:
            # Get report files
            for filename in os.listdir(self.reports_dir):
                if filename.startswith('claim_report_') and filename.endswith('.pdf'):
                    file_path = os.path.join(self.reports_dir, filename)
                    stat = os.stat(file_path)
                    
                    # Extract claim number from filename
                    claim_number = filename.replace('claim_report_', '').replace('.pdf', '')
                    parts = claim_number.split('_')
                    if len(parts) >= 2:
                        claim_number = parts[0]
                    
                    reports.append({
                        'filename': filename,
                        'file_path': file_path,
                        'claim_number': claim_number,
                        'created_at': datetime.fromtimestamp(stat.st_ctime),
                        'size': stat.st_size,
                        'download_url': f'/download/{filename}'
                    })
            
            # Sort by creation date (newest first)
            reports.sort(key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting reports: {str(e)}")
        
        return reports
    
    def get_reports_by_company(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group reports by company name"""
        reports = self.get_all_reports()
        companies = {}
        
        # Try to extract company names from processed claims data
        try:
            if os.path.exists(self.processed_claims_file):
                with open(self.processed_claims_file, 'r', encoding='utf-8') as f:
                    processed_claims = json.load(f)
                
                for claim_number, claim_data in processed_claims.items():
                    company_name = claim_data.get('sender_email', 'Unknown Company')
                    # Extract domain name as company identifier
                    if '@' in company_name:
                        company_name = company_name.split('@')[1].split('.')[0].title()
                    
                    if company_name not in companies:
                        companies[company_name] = []
                    
                    # Find matching report
                    for report in reports:
                        if report['claim_number'] == claim_number:
                            report['company_name'] = company_name
                            report['subject'] = claim_data.get('subject', 'No Subject')
                            report['fraud_score'] = claim_data.get('fraud_score', 0)
                            companies[company_name].append(report)
                            break
            
            # Add reports without company info to "Unknown" category
            for report in reports:
                if 'company_name' not in report:
                    if 'Unknown' not in companies:
                        companies['Unknown'] = []
                    report['company_name'] = 'Unknown'
                    report['subject'] = 'No subject information'
                    report['fraud_score'] = 0
                    companies['Unknown'].append(report)
                    
        except Exception as e:
            logger.error(f"Error grouping reports by company: {str(e)}")
        
        return companies
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        stats = {
            'total_reports': 0,
            'companies_count': 0,
            'latest_processing': None,
            'high_risk_claims': 0,
            'duplicate_claims': 0
        }
        
        try:
            reports = self.get_all_reports()
            stats['total_reports'] = len(reports)
            
            companies = self.get_reports_by_company()
            stats['companies_count'] = len(companies)
            
            # Get latest processing info
            if os.path.exists(self.processing_log_file):
                with open(self.processing_log_file, 'r', encoding='utf-8') as f:
                    processing_log = json.load(f)
                    if processing_log:
                        stats['latest_processing'] = processing_log[-1].get('processed_at')
            
            # Count high risk claims
            if os.path.exists(self.processed_claims_file):
                with open(self.processed_claims_file, 'r', encoding='utf-8') as f:
                    processed_claims = json.load(f)
                
                for claim_data in processed_claims.values():
                    if claim_data.get('fraud_score', 0) > 0.7:
                        stats['high_risk_claims'] += 1
            
        except Exception as e:
            logger.error(f"Error getting processing stats: {str(e)}")
        
        return stats
    
    def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest system updates"""
        updates = []
        
        try:
            if os.path.exists(self.processing_log_file):
                with open(self.processing_log_file, 'r', encoding='utf-8') as f:
                    processing_log = json.load(f)
                
                for log_entry in processing_log[-limit:]:
                    updates.append({
                        'type': 'claim_processed',
                        'message': f"New claim processed: {log_entry.get('subject', 'Unknown')}",
                        'timestamp': log_entry.get('processed_at'),
                        'claim_number': log_entry.get('claim_number'),
                        'company': log_entry.get('sender_email', 'Unknown').split('@')[1].split('.')[0].title() if '@' in log_entry.get('sender_email', '') else 'Unknown'
                    })
        
        except Exception as e:
            logger.error(f"Error getting latest updates: {str(e)}")
        
        # Add system status updates
        updates.append({
            'type': 'system_status',
            'message': 'System running normally',
            'timestamp': datetime.now().isoformat(),
            'status': 'online'
        })
        
        # Sort by timestamp
        updates.sort(key=lambda x: x['timestamp'], reverse=True)
        return updates[:limit]

# Initialize dashboard manager
dashboard_manager = DashboardManager()

def background_email_processor():
    """Background thread for continuous email processing"""
    global processing_pipeline, latest_updates
    
    logger.info("Background email processor started")
    
    while not stop_event.is_set():
        try:
            if not processing_pipeline:
                processing_pipeline = ClaimsProcessingPipeline()
            
            # Process new emails
            processed_emails = processing_pipeline.email_processor.process_emails(process_all=False)
            
            if processed_emails:
                logger.info(f"Background processing: Found {len(processed_emails)} new emails")
                
                for email_data in processed_emails:
                    try:
                        result = processing_pipeline.process_single_claim(email_data)
                        if result and hasattr(result, 'processing_status') and result.processing_status == 'completed':
                            # Add to latest updates
                            update_msg = {
                                'type': 'new_claim',
                                'message': f"New claim report generated: {result.claim_number}",
                                'timestamp': result.processed_at,
                                'claim_number': result.claim_number,
                                'company': result.sender_email.split('@')[1].split('.')[0].title() if '@' in result.sender_email else 'Unknown',
                                'fraud_score': result.fraud_score,
                                'is_duplicate': result.is_duplicate
                            }
                            latest_updates.insert(0, update_msg)
                            # Keep only last 20 updates
                            latest_updates = latest_updates[:20]
                            
                            logger.info(f"Background processing completed: {result.claim_number}")
                    except Exception as e:
                        logger.error(f"Error in background processing: {str(e)}")
            
            # Wait for next check
            stop_event.wait(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Background processor error: {str(e)}")
            stop_event.wait(60)  # Wait before retrying

@app.route('/')
def index():
    """Main dashboard page"""
    stats = dashboard_manager.get_processing_stats()
    companies_reports = dashboard_manager.get_reports_by_company()
    updates = latest_updates or dashboard_manager.get_latest_updates()
    
    return render_template('index.html', 
                         stats=stats, 
                         companies_reports=companies_reports,
                         updates=updates)

@app.route('/reports')
def reports_list():
    """Reports listing page"""
    companies_reports = dashboard_manager.get_reports_by_company()
    return render_template('reports.html', companies_reports=companies_reports)

@app.route('/download/<filename>')
def download_report(filename):
    """Download a report file"""
    try:
        file_path = os.path.join(settings.REPORTS_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return "File not found", 404
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        return "Error downloading file", 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    stats = dashboard_manager.get_processing_stats()
    return jsonify(stats)

@app.route('/api/updates')
def api_updates():
    """API endpoint for latest updates"""
    updates = latest_updates or dashboard_manager.get_latest_updates()
    return jsonify(updates)

@app.route('/api/process-now', methods=['POST'])
def api_process_now():
    """API endpoint to trigger immediate processing"""
    try:
        global processing_pipeline
        
        if not processing_pipeline:
            processing_pipeline = ClaimsProcessingPipeline()
        
        processed_emails = processing_pipeline.email_processor.process_emails(process_all=False)
        
        if processed_emails:
            results = []
            for email_data in processed_emails:
                result = processing_pipeline.process_single_claim(email_data)
                if result:
                    results.append({
                        'claim_number': result.claim_number,
                        'status': result.processing_status,
                        'fraud_score': result.fraud_score
                    })
            
            return jsonify({
                'success': True,
                'message': f'Processed {len(results)} new claims',
                'results': results
            })
        else:
            return jsonify({
                'success': True,
                'message': 'No new emails to process'
            })
            
    except Exception as e:
        logger.error(f"Error in manual processing: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Processing error: {str(e)}'
        }), 500

@app.route('/api/background-process/<action>', methods=['POST'])
def api_background_process(action):
    """API endpoint to control background processing"""
    global background_thread, stop_event
    
    if action == 'start':
        if background_thread and background_thread.is_alive():
            return jsonify({'success': False, 'message': 'Background processing already running'})
        
        stop_event.clear()
        background_thread = Thread(target=background_email_processor)
        background_thread.daemon = True
        background_thread.start()
        
        return jsonify({'success': True, 'message': 'Background processing started'})
    
    elif action == 'stop':
        stop_event.set()
        if background_thread:
            background_thread.join(timeout=10)
        
        return jsonify({'success': True, 'message': 'Background processing stopped'})
    
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

# Template filters
@app.template_filter('format_date')
def format_date(value):
    """Format date for display"""
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return value
    return value

@app.template_filter('format_size')
def format_size(value):
    """Format file size for display"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"

@app.template_filter('risk_color')
def risk_color(fraud_score):
    """Get color based on fraud risk"""
    if fraud_score > 0.7:
        return 'danger'
    elif fraud_score > 0.4:
        return 'warning'
    else:
        return 'success'

def start_dashboard(host='0.0.0.0', port=5000, debug=True):
    """Start the Flask dashboard"""
    logger.info(f"Starting Marine Claims Dashboard on {host}:{port}")
    
    # Create templates directory if it doesn't exist
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create basic templates if they don't exist
    create_default_templates(templates_dir)
    
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except Exception as e:
        logger.error(f"Error starting dashboard: {str(e)}")
        raise

def create_default_templates(templates_dir):
    """Create default HTML templates"""
    
    # Main template
    base_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Marine Claims Dashboard{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .navbar-brand { font-weight: bold; }
        .card { margin-bottom: 1rem; }
        .risk-badge { font-size: 0.8em; }
        .update-item { border-left: 4px solid #007bff; padding-left: 1rem; margin-bottom: 0.5rem; }
        .company-section { background: #f8f9fa; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-ship me-2"></i>Marine Claims Dashboard
            </a>
            <div class="navbar-nav">
                <a class="nav-link text-white" href="/">Dashboard</a>
                <a class="nav-link text-white" href="/reports">Reports</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
    """
    
    # Index template
    index_template = """
{% extends "base.html" %}

{% block content %}
<div class="row">
    <!-- Statistics -->
    <div class="col-md-3">
        <div class="card text-white bg-primary">
            <div class="card-body">
                <h5 class="card-title"><i class="fas fa-file-pdf"></i> Total Reports</h5>
                <h2 class="card-text">{{ stats.total_reports }}</h2>
            </div>
        </div>
    </div>
    
    <div class="col-md-3">
        <div class="card text-white bg-success">
            <div class="card-body">
                <h5 class="card-title"><i class="fas fa-building"></i> Companies</h5>
                <h2 class="card-text">{{ stats.companies_count }}</h2>
            </div>
        </div>
    </div>
    
    <div class="col-md-3">
        <div class="card text-white bg-warning">
            <div class="card-body">
                <h5 class="card-title"><i class="fas fa-exclamation-triangle"></i> High Risk</h5>
                <h2 class="card-text">{{ stats.high_risk_claims }}</h2>
            </div>
        </div>
    </div>
    
    <div class="col-md-3">
        <div class="card text-white bg-info">
            <div class="card-body">
                <h5 class="card-title"><i class="fas fa-sync"></i> Last Processed</h5>
                <h6 class="card-text">{{ stats.latest_processing|format_date if stats.latest_processing else 'Never' }}</h6>
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <!-- Latest Updates -->
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-bell"></i> Latest Updates</h5>
            </div>
            <div class="card-body">
                {% for update in updates %}
                <div class="update-item">
                    <small class="text-muted">{{ update.timestamp|format_date }}</small>
                    <div>{{ update.message }}</div>
                    {% if update.claim_number %}
                    <small class="text-muted">Claim: {{ update.claim_number }}</small>
                    {% endif %}
                </div>
                {% else %}
                <p class="text-muted">No recent updates</p>
                {% endfor %}
            </div>
        </div>
        
        <div class="card mt-3">
            <div class="card-header">
                <h5><i class="fas fa-cogs"></i> System Controls</h5>
            </div>
            <div class="card-body">
                <button id="processNow" class="btn btn-primary btn-sm">
                    <i class="fas fa-play"></i> Process Now
                </button>
                <button id="startBackground" class="btn btn-success btn-sm">
                    <i class="fas fa-play-circle"></i> Start Background
                </button>
                <button id="stopBackground" class="btn btn-danger btn-sm">
                    <i class="fas fa-stop"></i> Stop Background
                </button>
            </div>
        </div>
    </div>
    
    <!-- Companies Overview -->
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-building"></i> Companies Overview</h5>
            </div>
            <div class="card-body">
                {% for company, reports in companies_reports.items() %}
                <div class="company-section">
                    <h6>{{ company }} <span class="badge bg-secondary">{{ reports|length }} reports</span></h6>
                    {% for report in reports[:3] %}
                    <div class="d-flex justify-content-between align-items-center small">
                        <span>{{ report.claim_number }}</span>
                        <span class="badge bg-{{ report.fraud_score|risk_color }}">
                            Risk: {{ (report.fraud_score * 100)|int }}%
                        </span>
                    </div>
                    {% endfor %}
                    {% if reports|length > 3 %}
                    <small class="text-muted">... and {{ reports|length - 3 }} more</small>
                    {% endif %}
                </div>
                {% else %}
                <p class="text-muted">No reports available</p>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
document.getElementById('processNow').addEventListener('click', function() {
    fetch('/api/process-now', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            location.reload();
        });
});

document.getElementById('startBackground').addEventListener('click', function() {
    fetch('/api/background-process/start', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message));
});

document.getElementById('stopBackground').addEventListener('click', function() {
    fetch('/api/background-process/stop', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message));
});
</script>
{% endblock %}
    """
    
    # Reports template
    reports_template = """
{% extends "base.html" %}

{% block title %}Reports - Marine Claims Dashboard{% endblock %}

{% block content %}
<h2><i class="fas fa-file-pdf"></i> Claims Reports</h2>

{% for company, reports in companies_reports.items() %}
<div class="company-section">
    <h4>{{ company }} <span class="badge bg-primary">{{ reports|length }} reports</span></h4>
    
    <div class="table-responsive">
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Claim Number</th>
                    <th>Subject</th>
                    <th>Created</th>
                    <th>Risk Score</th>
                    <th>Size</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for report in reports %}
                <tr>
                    <td>{{ report.claim_number }}</td>
                    <td>{{ report.subject|truncate(50) }}</td>
                    <td>{{ report.created_at|format_date }}</td>
                    <td>
                        <span class="badge bg-{{ report.fraud_score|risk_color }}">
                            {{ (report.fraud_score * 100)|int }}%
                        </span>
                    </td>
                    <td>{{ report.size|format_size }}</td>
                    <td>
                        <a href="{{ report.download_url }}" class="btn btn-primary btn-sm">
                            <i class="fas fa-download"></i> Download
                        </a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% else %}
<div class="alert alert-info">
    <i class="fas fa-info-circle"></i> No reports available yet. Process some emails to generate reports.
</div>
{% endfor %}
{% endblock %}
    """
    
    # Write template files
    with open(os.path.join(templates_dir, 'base.html'), 'w') as f:
        f.write(base_template)
    
    with open(os.path.join(templates_dir, 'index.html'), 'w') as f:
        f.write(index_template)
    
    with open(os.path.join(templates_dir, 'reports.html'), 'w') as f:
        f.write(reports_template)

if __name__ == '__main__':
    start_dashboard()