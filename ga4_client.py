import yaml
import pandas as pd
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
from auth_manager import AuthManager
import logging

class GA4DataClient:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.auth_manager = AuthManager(config_path)
        self.event_mapping = self.config['event_mapping']['appointment_events']
        self.data_config = self.config['data_config']
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def normalize_event_name(self, event_name):
        """Normalize appointment event names to a standard format"""
        if event_name.lower() in [e.lower() for e in self.event_mapping]:
            return "appointment_booking"
        return event_name

    def get_client_for_account(self, account_name):
        """Get authenticated GA4 client for a specific account"""
        credentials = self.auth_manager.get_credentials(account_name)
        return BetaAnalyticsDataClient(credentials=credentials)

    def extract_data_for_property(self, client, property_id, appointment_event_name, location_name):
        """Extract data for a single GA4 property"""
        self.logger.info(f"Extracting data for {location_name} (Property: {property_id})")
        
        try:
            # New Users Report
            new_users_request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="newUsers")],
                date_ranges=[DateRange(
                    start_date=self.data_config['date_range']['start_date'],
                    end_date=self.data_config['date_range']['end_date']
                )]
            )
            
            new_users_response = client.run_report(new_users_request)
            
            # Appointment Events Report
            events_request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[
                    Dimension(name="date"),
                    Dimension(name="eventName")
                ],
                metrics=[Metric(name="eventCount")],
                date_ranges=[DateRange(
                    start_date=self.data_config['date_range']['start_date'],
                    end_date=self.data_config['date_range']['end_date']
                )],
                dimension_filter={
                    "filter": {
                        "field_name": "eventName",
                        "string_filter": {
                            "match_type": "EXACT",
                            "value": appointment_event_name
                        }
                    }
                }
            )
            
            events_response = client.run_report(events_request)
            
            # Process responses
            data = self._process_responses(
                new_users_response, 
                events_response, 
                location_name, 
                property_id,
                appointment_event_name
            )
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error extracting data for {location_name}: {str(e)}")
            return None

    def _process_responses(self, new_users_response, events_response, location_name, property_id, appointment_event_name):
        """Process GA4 API responses into structured data"""
        
        # Process new users data
        new_users_data = []
        for row in new_users_response.rows:
            date = row.dimension_values[0].value
            new_users = int(row.metric_values[0].value)
            new_users_data.append({
                'date': date,
                'new_users': new_users
            })
        
        # Process events data
        events_data = []
        for row in events_response.rows:
            date = row.dimension_values[0].value
            event_name = row.dimension_values[1].value
            event_count = int(row.metric_values[0].value)
            events_data.append({
                'date': date,
                'event_name': self.normalize_event_name(event_name),
                'event_count': event_count
            })
        
        # Combine data
        new_users_df = pd.DataFrame(new_users_data)
        events_df = pd.DataFrame(events_data)
        
        # Merge on date
        if not events_df.empty:
            combined_df = pd.merge(new_users_df, events_df, on='date', how='left')
        else:
            combined_df = new_users_df.copy()
            combined_df['event_name'] = 'appointment_booking'
            combined_df['event_count'] = 0
        
        # Add metadata
        combined_df['location_name'] = location_name
        combined_df['property_id'] = property_id
        combined_df['original_event_name'] = appointment_event_name
        combined_df['event_count'] = combined_df['event_count'].fillna(0)
        
        return combined_df

    def extract_all_data(self):
        """Extract data for all properties across all accounts"""
        all_data = []
        
        for account_name, account_config in self.config['accounts'].items():
            if not account_config.get('properties'):
                self.logger.info(f"No properties configured for {account_name}")
                continue
                
            self.logger.info(f"Processing account: {account_name}")
            
            try:
                client = self.get_client_for_account(account_name)
                
                for property_config in account_config['properties']:
                    property_id = property_config['property_id']
                    location_name = property_config['location_name']
                    appointment_event_name = property_config['appointment_event_name']
                    
                    data = self.extract_data_for_property(
                        client, 
                        property_id, 
                        appointment_event_name, 
                        location_name
                    )
                    
                    if data is not None:
                        all_data.append(data)
                
            except Exception as e:
                self.logger.error(f"Error processing account {account_name}: {str(e)}")
                continue
        
        if all_data:
            combined_data = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Successfully extracted data for {len(all_data)} properties")
            return combined_data
        else:
            self.logger.warning("No data extracted")
            return pd.DataFrame()

    def get_summary_report(self, data):
        """Generate summary statistics"""
        if data.empty:
            return None
            
        summary = data.groupby('location_name').agg({
            'new_users': 'sum',
            'event_count': 'sum'
        }).reset_index()
        
        summary['conversion_rate'] = (summary['event_count'] / summary['new_users'] * 100).round(2)
        summary = summary.fillna(0)
        
        return summary