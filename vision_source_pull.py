#!/usr/bin/env python3
"""
Vision Source GA4 Data Pull System
Automated data extraction for 500+ Vision Source locations across multiple GA4 accounts
"""

import yaml
import argparse
import logging
import sys
import time
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

from auth_manager import AuthManager
from ga4_client import GA4DataClient
from event_normalizer import EventNormalizer
from data_exporter import DataExporter

class VisionSourceDataPull:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.setup_logging()
        
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing configuration file: {e}")
            sys.exit(1)
        
        # Initialize components
        self.auth_manager = AuthManager(config_path)
        self.ga4_client = GA4DataClient(config_path)
        self.event_normalizer = EventNormalizer()
        self.data_exporter = DataExporter(self.config)
        
        # Configuration
        self.retry_attempts = 3
        self.retry_delay = 5  # seconds

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('vision_source_pull.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def authenticate_all_accounts(self):
        """Authenticate all configured accounts"""
        self.logger.info("Starting authentication for all accounts...")
        
        for account_name in self.config['accounts']:
            try:
                self.logger.info(f"Authenticating {account_name}...")
                credentials = self.auth_manager.get_credentials(account_name)
                if credentials:
                    self.logger.info(f"✓ {account_name} authenticated successfully")
                else:
                    self.logger.error(f"✗ Failed to authenticate {account_name}")
            except Exception as e:
                self.logger.error(f"✗ Authentication failed for {account_name}: {str(e)}")

    def validate_configuration(self) -> bool:
        """Validate the configuration file"""
        self.logger.info("Validating configuration...")
        
        required_sections = ['oauth', 'accounts', 'event_mapping', 'data_config']
        for section in required_sections:
            if section not in self.config:
                self.logger.error(f"Missing required configuration section: {section}")
                return False
        
        # Validate OAuth configuration
        oauth_config = self.config['oauth']
        required_oauth_fields = ['client_id', 'client_secret', 'redirect_uri', 'scopes']
        for field in required_oauth_fields:
            if field not in oauth_config:
                self.logger.error(f"Missing OAuth configuration field: {field}")
                return False
        
        # Count total properties
        total_properties = 0
        for account_name, account_config in self.config['accounts'].items():
            if 'properties' in account_config:
                total_properties += len(account_config['properties'])
        
        self.logger.info(f"Configuration valid. Found {total_properties} properties across {len(self.config['accounts'])} accounts")
        return True

    def extract_data_with_retry(self, max_retries: int = None) -> Optional[pd.DataFrame]:
        """Extract data with retry logic"""
        max_retries = max_retries or self.retry_attempts
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Data extraction attempt {attempt + 1}/{max_retries}")
                data = self.ga4_client.extract_all_data()
                
                if not data.empty:
                    self.logger.info(f"✓ Successfully extracted data: {len(data)} records")
                    return data
                else:
                    self.logger.warning("No data extracted")
                    
            except Exception as e:
                self.logger.error(f"Data extraction attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error("All extraction attempts failed")
        
        return None

    def run_full_extraction(self, export_formats: List[str] = None) -> Dict[str, str]:
        """Run complete data extraction and export process"""
        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("Starting Vision Source GA4 Data Pull")
        self.logger.info("=" * 60)
        
        # Validate configuration
        if not self.validate_configuration():
            self.logger.error("Configuration validation failed")
            return {}
        
        # Extract data
        data = self.extract_data_with_retry()
        if data is None or data.empty:
            self.logger.error("No data extracted. Exiting.")
            return {}
        
        # Analyze event names
        self.logger.info("Analyzing event names...")
        unique_events = data['original_event_name'].unique().tolist()
        event_analysis = self.event_normalizer.analyze_events(unique_events)
        
        self.logger.info(f"Event analysis: {len(event_analysis['mapped'])} mapped, {len(event_analysis['unmapped'])} unmapped")
        
        # Export data
        export_formats = export_formats or ['xlsx', 'csv']
        exported_files = self.data_exporter.export_multiple_formats(data, export_formats)
        
        # Generate summary
        summary = self.ga4_client.get_summary_report(data)
        if summary is not None:
            self.logger.info("\nTop 10 Locations by Appointments:")
            top_10 = summary.nlargest(10, 'event_count')
            for _, row in top_10.iterrows():
                self.logger.info(f"  {row['location_name']}: {row['event_count']} appointments ({row['conversion_rate']}% conversion)")
        
        # Execution summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        self.logger.info("=" * 60)
        self.logger.info("Data Pull Complete")
        self.logger.info("=" * 60)
        self.logger.info(f"Execution time: {duration}")
        self.logger.info(f"Records extracted: {len(data)}")
        self.logger.info(f"Locations processed: {data['location_name'].nunique()}")
        self.logger.info(f"Files exported: {list(exported_files.keys())}")
        
        return exported_files

    def setup_new_configuration(self):
        """Interactive setup for new configuration"""
        print("Vision Source GA4 Data Pull - Configuration Setup")
        print("=" * 50)
        
        # This would be an interactive setup process
        # For now, just provide instructions
        print("""
To complete the setup:

1. Set up OAuth2 credentials in Google Cloud Console:
   - Enable Google Analytics Data API
   - Create OAuth2 credentials
   - Add redirect URI: http://localhost:8080

2. Update config.yaml with your:
   - OAuth client_id and client_secret
   - Account emails (luxoticasupport@eulerity.com, etc.)
   - Property IDs for each location
   - Event names for each property

3. Run authentication:
   python vision_source_pull.py --authenticate

4. Run data extraction:
   python vision_source_pull.py --extract
        """)

def main():
    parser = argparse.ArgumentParser(description="Vision Source GA4 Data Pull System")
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--authenticate', action='store_true', help='Authenticate all accounts')
    parser.add_argument('--extract', action='store_true', help='Extract data from all properties')
    parser.add_argument('--setup', action='store_true', help='Setup new configuration')
    parser.add_argument('--formats', nargs='+', default=['xlsx', 'csv'], 
                       choices=['xlsx', 'csv', 'json'], help='Export formats')
    parser.add_argument('--validate', action='store_true', help='Validate configuration only')
    
    args = parser.parse_args()
    
    # Create the data pull system
    try:
        system = VisionSourceDataPull(args.config)
    except SystemExit:
        return
    
    # Execute based on arguments
    if args.setup:
        system.setup_new_configuration()
    elif args.authenticate:
        system.authenticate_all_accounts()
    elif args.validate:
        system.validate_configuration()
    elif args.extract:
        exported_files = system.run_full_extraction(args.formats)
        if exported_files:
            print("\nExported files:")
            for format_type, filepath in exported_files.items():
                print(f"  {format_type}: {filepath}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()