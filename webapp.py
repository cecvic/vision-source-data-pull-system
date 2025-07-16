#!/usr/bin/env python3
"""
Vision Source GA4 Property Selection Web App
Web interface for selecting properties and running data extraction
"""

import os
import json
import yaml
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
import logging
from property_discovery import PropertyDiscovery
from ga4_client import GA4DataClient
from data_exporter import DataExporter
import pandas as pd
import threading
import time

app = Flask(__name__)
app.secret_key = 'vision-source-secret-key-change-in-production'

# Global variables for storing state
discovered_properties = {}
extraction_status = {}
extraction_results = {}

class WebAppManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.property_discovery = PropertyDiscovery(config_path)
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def load_discovered_properties(self):
        """Load discovered properties from file or discover them"""
        global discovered_properties
        
        # Try to load from file first
        try:
            with open('discovered_properties.json', 'r') as f:
                discovered_properties = json.load(f)
            self.logger.info(f"Loaded discovered properties from file: {len(discovered_properties)} accounts")
            
            # Log some details about what was loaded
            for auth_account, data in discovered_properties.items():
                account_count = len(data['accounts'])
                property_count = sum(len(acc['properties']) for acc in data['accounts'])
                self.logger.info(f"  {auth_account}: {account_count} GA accounts, {property_count} properties")
            
            return True
        except FileNotFoundError:
            self.logger.info("No cached properties found, discovering...")
            return self.discover_properties()

    def discover_properties(self):
        """Discover properties and cache them"""
        global discovered_properties
        
        try:
            discovered_properties = self.property_discovery.discover_all_accounts()
            
            if discovered_properties:
                # Save to file
                with open('discovered_properties.json', 'w') as f:
                    json.dump(discovered_properties, f, indent=2, default=str)
                self.logger.info("Properties discovered and cached")
                return True
            else:
                self.logger.error("No properties discovered")
                return False
        except Exception as e:
            self.logger.error(f"Error discovering properties: {str(e)}")
            return False

    def extract_data_for_properties(self, selected_properties, date_range, task_id):
        """Extract data for selected properties (runs in background)"""
        global extraction_status, extraction_results
        
        extraction_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'current_property': '',
            'total_properties': len(selected_properties),
            'completed_properties': 0,
            'start_time': datetime.now().isoformat()
        }
        
        try:
            # Create a temporary config for selected properties
            temp_config = self.config.copy()
            temp_config['data_config']['date_range'] = date_range
            
            # Initialize clients
            ga4_client = GA4DataClient(self.config_path)
            data_exporter = DataExporter(temp_config)
            
            all_data = []
            
            for i, prop_info in enumerate(selected_properties):
                extraction_status[task_id]['current_property'] = prop_info['property_name']
                extraction_status[task_id]['progress'] = int((i / len(selected_properties)) * 100)
                
                try:
                    # Extract data for this property
                    client = ga4_client.get_client_for_account(prop_info['auth_account'])
                    
                    # Determine appointment event name (you might want to make this configurable)
                    appointment_event = prop_info.get('appointment_event', 'book_appointments')
                    
                    data = ga4_client.extract_data_for_property(
                        client,
                        prop_info['property_id'],
                        appointment_event,
                        prop_info['property_name']
                    )
                    
                    if data is not None and not data.empty:
                        all_data.append(data)
                    
                    extraction_status[task_id]['completed_properties'] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error extracting data for property {prop_info['property_id']}: {str(e)}")
                    continue
            
            # Combine and export data
            if all_data:
                combined_data = pd.concat(all_data, ignore_index=True)
                
                # Export to multiple formats
                exported_files = data_exporter.export_multiple_formats(combined_data, ['xlsx', 'csv'])
                
                # Generate summary
                summary = ga4_client.get_summary_report(combined_data)
                
                extraction_results[task_id] = {
                    'success': True,
                    'exported_files': exported_files,
                    'summary': summary.to_dict('records') if summary is not None else [],
                    'total_records': len(combined_data),
                    'total_properties': len(all_data)
                }
                
                extraction_status[task_id]['status'] = 'completed'
                extraction_status[task_id]['progress'] = 100
            else:
                extraction_results[task_id] = {
                    'success': False,
                    'error': 'No data extracted from any properties'
                }
                extraction_status[task_id]['status'] = 'failed'
                
        except Exception as e:
            extraction_results[task_id] = {
                'success': False,
                'error': str(e)
            }
            extraction_status[task_id]['status'] = 'failed'
            self.logger.error(f"Extraction failed: {str(e)}")

# Initialize the app manager
app_manager = WebAppManager()

@app.route('/')
def index():
    """Main page"""
    global discovered_properties
    
    if not discovered_properties:
        return render_template('index.html', needs_discovery=True)
    
    # Prepare data for display
    total_properties = 0
    accounts_summary = []
    
    for auth_account, data in discovered_properties.items():
        account_properties = sum(len(acc['properties']) for acc in data['accounts'])
        total_properties += account_properties
        
        accounts_summary.append({
            'auth_account': auth_account,
            'email': data['account_email'],
            'properties': account_properties,
            'ga_accounts': len(data['accounts'])
        })
    
    return render_template('index.html', 
                         discovered_properties=discovered_properties,
                         accounts_summary=accounts_summary,
                         total_properties=total_properties)

@app.route('/discover')
def discover():
    """Discover properties"""
    if app_manager.discover_properties():
        flash('Properties discovered successfully!', 'success')
    else:
        flash('Failed to discover properties. Check authentication.', 'error')
    
    return redirect(url_for('index'))

@app.route('/properties')
def properties():
    """Properties listing page"""
    global discovered_properties
    
    if not discovered_properties:
        flash('No properties discovered. Please discover properties first.', 'warning')
        return redirect(url_for('index'))
    
    # Flatten properties for easier display
    all_properties = []
    for auth_account, data in discovered_properties.items():
        for ga_account in data['accounts']:
            for prop in ga_account['properties']:
                all_properties.append({
                    'auth_account': auth_account,
                    'auth_email': data['account_email'],
                    'ga_account_name': ga_account['account_name'],
                    'property_id': prop['property_id'],
                    'property_name': prop['property_name'],
                    'website_url': prop.get('website_url', ''),
                    'create_time': prop.get('create_time', '')
                })
    
    return render_template('properties.html', properties=all_properties)

@app.route('/extract', methods=['GET', 'POST'])
def extract():
    """Data extraction page"""
    if request.method == 'GET':
        return render_template('extract.html')
    
    # Handle POST - start extraction
    selected_property_ids = request.form.getlist('selected_properties')
    start_date = request.form.get('start_date', '30daysAgo')
    end_date = request.form.get('end_date', 'today')
    
    if not selected_property_ids:
        flash('Please select at least one property.', 'warning')
        return redirect(url_for('extract'))
    
    # Find selected properties in discovered data
    selected_properties = []
    for auth_account, data in discovered_properties.items():
        for ga_account in data['accounts']:
            for prop in ga_account['properties']:
                if prop['property_id'] in selected_property_ids:
                    selected_properties.append({
                        'auth_account': auth_account,
                        'property_id': prop['property_id'],
                        'property_name': prop['property_name'],
                        'appointment_event': 'book_appointments'  # Default - could be made configurable
                    })
    
    if not selected_properties:
        flash('Selected properties not found.', 'error')
        return redirect(url_for('extract'))
    
    # Generate task ID and start extraction in background
    task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    date_range = {'start_date': start_date, 'end_date': end_date}
    
    thread = threading.Thread(
        target=app_manager.extract_data_for_properties,
        args=(selected_properties, date_range, task_id)
    )
    thread.daemon = True
    thread.start()
    
    return redirect(url_for('extraction_status', task_id=task_id))

@app.route('/status/<task_id>')
def extraction_status_page(task_id):
    """Extraction status page"""
    global extraction_status
    
    if task_id not in extraction_status:
        flash('Task not found.', 'error')
        return redirect(url_for('index'))
    
    return render_template('status.html', task_id=task_id)

@app.route('/api/status/<task_id>')
def extraction_status_api(task_id):
    """API endpoint for extraction status"""
    global extraction_status, extraction_results
    
    if task_id not in extraction_status:
        return jsonify({'error': 'Task not found'}), 404
    
    status = extraction_status[task_id].copy()
    
    # Add results if completed
    if task_id in extraction_results:
        status['results'] = extraction_results[task_id]
    
    return jsonify(status)

@app.route('/download/<task_id>/<file_type>')
def download_file(task_id, file_type):
    """Download extracted files"""
    global extraction_results
    
    if task_id not in extraction_results:
        flash('Task not found.', 'error')
        return redirect(url_for('index'))
    
    results = extraction_results[task_id]
    if not results.get('success'):
        flash('No files to download.', 'error')
        return redirect(url_for('extraction_status_page', task_id=task_id))
    
    exported_files = results.get('exported_files', {})
    if file_type not in exported_files:
        flash(f'File type {file_type} not available.', 'error')
        return redirect(url_for('extraction_status_page', task_id=task_id))
    
    file_path = exported_files[file_type]
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('File not found.', 'error')
        return redirect(url_for('extraction_status_page', task_id=task_id))

@app.route('/api/properties/search')
def search_properties():
    """API endpoint for property search"""
    global discovered_properties
    
    query = request.args.get('q', '').lower()
    auth_account = request.args.get('account', '')
    
    results = []
    
    for account_name, data in discovered_properties.items():
        if auth_account and account_name != auth_account:
            continue
            
        for ga_account in data['accounts']:
            for prop in ga_account['properties']:
                # Search in property name and website URL
                if (query in prop['property_name'].lower() or 
                    query in prop.get('website_url', '').lower()):
                    results.append({
                        'auth_account': account_name,
                        'property_id': prop['property_id'],
                        'property_name': prop['property_name'],
                        'website_url': prop.get('website_url', ''),
                        'ga_account_name': ga_account['account_name']
                    })
    
    return jsonify(results)

@app.route('/custom-report', methods=['GET', 'POST'])
def custom_report():
    """Custom report for new users and appointment events"""
    if request.method == 'GET':
        return render_template('custom_report.html')
    
    # Handle POST - generate custom report
    try:
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('Please select both start and end dates.', 'warning')
            return redirect(url_for('custom_report'))
        
        # Generate custom report data
        report_data = generate_custom_report(start_date, end_date)
        
        if request.form.get('download_csv'):
            # Generate CSV and return as download
            csv_data = generate_csv_report(report_data)
            
            # Create temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                tmp.write(csv_data)
                tmp_path = tmp.name
            
            return send_file(tmp_path, 
                           as_attachment=True, 
                           download_name=f'vision_source_custom_report_{start_date}_{end_date}.csv',
                           mimetype='text/csv')
        else:
            # Display report in browser
            return render_template('custom_report.html', 
                                 report_data=report_data, 
                                 start_date=start_date, 
                                 end_date=end_date)
    
    except Exception as e:
        app.logger.error(f"Error generating custom report: {str(e)}")
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('custom_report'))

def generate_custom_report(start_date, end_date):
    """Generate custom report data for new users and appointment events"""
    global discovered_properties
    
    app.logger.info(f"Starting custom report generation for date range: {start_date} to {end_date}")
    report_data = []
    
    # Initialize GA4 client
    ga4_client = GA4DataClient(app_manager.config_path)
    
    total_properties = sum(len(data['accounts']) for data in discovered_properties.values() for data in [data])
    app.logger.info(f"Found {total_properties} accounts to process")
    
    property_count = 0
    for auth_account, data in discovered_properties.items():
        app.logger.info(f"Processing auth account: {auth_account}")
        try:
            client = ga4_client.get_client_for_account(auth_account)
            
            for ga_account in data['accounts']:
                app.logger.info(f"Processing GA account: {ga_account['account_name']} with {len(ga_account['properties'])} properties")
                
                for prop in ga_account['properties']:
                    property_count += 1
                    property_id = prop['property_id']
                    property_name = prop['property_name']
                    
                    app.logger.info(f"Processing property {property_count}: {property_name} (ID: {property_id})")
                    
                    try:
                        # Get new users data
                        app.logger.info(f"Getting new users data for property {property_id}")
                        new_users_data = get_new_users_data(client, property_id, start_date, end_date)
                        app.logger.info(f"New users for {property_name}: {new_users_data}")
                        
                        # Get appointment events data
                        app.logger.info(f"Getting appointment events data for property {property_id}")
                        appointment_events_data = get_appointment_events_data(client, property_id, start_date, end_date)
                        app.logger.info(f"Appointment events for {property_name}: {appointment_events_data}")
                        
                        report_data.append({
                            'property_name': property_name,
                            'property_id': property_id,
                            'new_users': new_users_data,
                            'appointment_events': appointment_events_data
                        })
                        
                    except Exception as e:
                        app.logger.error(f"Error getting data for property {property_id}: {str(e)}")
                        report_data.append({
                            'property_name': property_name,
                            'property_id': property_id,
                            'new_users': 0,
                            'appointment_events': 0,
                            'error': str(e)
                        })
                        
        except Exception as e:
            app.logger.error(f"Error with auth account {auth_account}: {str(e)}")
            continue
    
    app.logger.info(f"Custom report generation completed. Generated {len(report_data)} records")
    return report_data

def get_new_users_data(client, property_id, start_date, end_date):
    """Get new users data for a property"""
    from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
    
    app.logger.info(f"Making new users API request for property {property_id}")
    
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[],
        metrics=[Metric(name="newUsers")],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)]
    )
    
    try:
        response = client.run_report(request)
        app.logger.info(f"New users API response for {property_id}: {len(response.rows)} rows")
        
        if response.rows:
            result = int(response.rows[0].metric_values[0].value)
            app.logger.info(f"New users result for {property_id}: {result}")
            return result
        else:
            app.logger.info(f"No new users data for property {property_id}")
            return 0
    except Exception as e:
        app.logger.error(f"Error getting new users for property {property_id}: {str(e)}")
        raise

def get_appointment_events_data(client, property_id, start_date, end_date):
    """Get appointment events data for a property"""
    from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange, Filter, FilterExpression
    
    app.logger.info(f"Making appointment events API request for property {property_id}")
    
    # Create filter for events containing "appointment"
    filter_expression = FilterExpression(
        filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.CONTAINS,
                value="appointment",
                case_sensitive=False
            )
        )
    )
    
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimension_filter=filter_expression
    )
    
    try:
        response = client.run_report(request)
        app.logger.info(f"Appointment events API response for {property_id}: {len(response.rows)} rows")
        
        total_events = 0
        if response.rows:
            for row in response.rows:
                event_name = row.dimension_values[0].value
                event_count = int(row.metric_values[0].value)
                app.logger.info(f"Found appointment event '{event_name}': {event_count} events")
                total_events += event_count
        
        app.logger.info(f"Total appointment events for {property_id}: {total_events}")
        return total_events
    except Exception as e:
        app.logger.error(f"Error getting appointment events for property {property_id}: {str(e)}")
        return 0

def generate_csv_report(report_data):
    """Generate CSV content from report data"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Property Name', 'Property ID', 'New Users', 'Appointment Events', 'Error'])
    
    # Write data rows
    for row in report_data:
        writer.writerow([
            row['property_name'],
            row['property_id'],
            row['new_users'],
            row['appointment_events'],
            row.get('error', '')
        ])
    
    return output.getvalue()

if __name__ == '__main__':
    # Load properties on startup
    app_manager.load_discovered_properties()
    
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print("🌐 Vision Source GA4 Property Selection Web App")
    print("=" * 50)
    print("📝 Make sure you have:")
    print("  1. Authenticated your accounts: python vision_source_pull.py --authenticate")
    print("  2. Run property discovery: python property_discovery.py --discover")
    print("")
    print("🚀 Starting web server at: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)