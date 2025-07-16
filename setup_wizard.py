#!/usr/bin/env python3
"""
Vision Source GA4 Setup Wizard
Interactive setup for new installations
"""

import os
import yaml
import json
import requests
from pathlib import Path

class SetupWizard:
    def __init__(self):
        self.config = {
            'oauth': {},
            'accounts': {},
            'event_mapping': {
                'appointment_events': [
                    'book_appointments',
                    'book_appoinments',
                    'schedule_appointment',
                    'schedule_appointments',
                    'make_appointments',
                    'make_appointment',
                    'appointment_booking'
                ]
            },
            'data_config': {
                'metrics': ['newUsers', 'eventCount'],
                'date_range': {
                    'start_date': '30daysAgo',
                    'end_date': 'today'
                }
            },
            'export': {
                'format': 'xlsx',
                'output_path': './exports/',
                'filename_template': 'vision_source_data_{date}.{format}'
            }
        }

    def run_setup(self):
        """Run the complete setup wizard"""
        print("🔧 Vision Source GA4 Data Pull - Setup Wizard")
        print("=" * 60)
        
        # Step 1: OAuth Configuration
        print("\n📋 Step 1: OAuth2 Configuration")
        self.setup_oauth()
        
        # Step 2: Account Configuration
        print("\n👥 Step 2: Account Configuration")
        self.setup_accounts()
        
        # Step 3: Property Configuration
        print("\n🏢 Step 3: Property Configuration")
        self.setup_properties()
        
        # Step 4: Export Configuration
        print("\n📊 Step 4: Export Configuration")
        self.setup_export()
        
        # Step 5: Save Configuration
        print("\n💾 Step 5: Save Configuration")
        self.save_config()
        
        # Step 6: Next Steps
        print("\n✅ Setup Complete!")
        self.show_next_steps()

    def setup_oauth(self):
        """Setup OAuth2 configuration"""
        print("""
To get OAuth2 credentials:
1. Go to https://console.cloud.google.com/
2. Create/select a project
3. Enable Google Analytics Data API
4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID
5. Application type: Web application
6. Add redirect URI: http://localhost:8080
""")
        
        client_id = input("Enter your OAuth2 Client ID: ").strip()
        client_secret = input("Enter your OAuth2 Client Secret: ").strip()
        
        self.config['oauth'] = {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': 'http://localhost:8080',
            'scopes': ['https://www.googleapis.com/auth/analytics.readonly']
        }
        
        print("✅ OAuth2 configuration saved")

    def setup_accounts(self):
        """Setup GA4 account configuration"""
        accounts = [
            'luxoticasupport@eulerity.com',
            'luxoticasupport2@eulerity.com',
            'luxoticasupport3@eulerity.com',
            'luxoticasupport4@eulerity.com'
        ]
        
        print("Setting up accounts:")
        for i, email in enumerate(accounts, 1):
            print(f"  {i}. {email}")
            
            self.config['accounts'][f'account{i}'] = {
                'email': email,
                'refresh_token': None,
                'properties': []
            }
        
        print("✅ Account structure created")

    def setup_properties(self):
        """Setup property configuration"""
        print("""
Property setup options:
1. Manual entry (for small number of properties)
2. CSV import (recommended for 500+ properties)
3. Skip for now (configure later)
""")
        
        choice = input("Choose option (1/2/3): ").strip()
        
        if choice == '1':
            self.manual_property_setup()
        elif choice == '2':
            self.csv_property_setup()
        else:
            print("⏭️  Property setup skipped - configure manually in config.yaml")

    def manual_property_setup(self):
        """Manual property entry"""
        print("\nEnter properties (press Enter with empty name to finish):")
        
        account_num = 1
        while True:
            property_id = input(f"Property ID: ").strip()
            if not property_id:
                break
                
            location_name = input(f"Location Name: ").strip()
            event_name = input(f"Appointment Event Name: ").strip()
            
            account_key = f'account{account_num}'
            if account_key not in self.config['accounts']:
                account_key = 'account1'
            
            self.config['accounts'][account_key]['properties'].append({
                'property_id': property_id,
                'location_name': location_name,
                'appointment_event_name': event_name
            })
            
            # Rotate accounts
            account_num = (account_num % 4) + 1

    def csv_property_setup(self):
        """CSV property import setup"""
        print("""
Create a CSV file with columns:
- property_id
- location_name
- appointment_event_name
- account_email (optional)

Example:
property_id,location_name,appointment_event_name,account_email
123456789,Vision Source Location 1,book_appointments,luxoticasupport@eulerity.com
""")
        
        csv_path = input("Enter CSV file path (or press Enter to skip): ").strip()
        
        if csv_path and os.path.exists(csv_path):
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                
                # Process CSV
                account_mapping = {
                    'luxoticasupport@eulerity.com': 'account1',
                    'luxoticasupport2@eulerity.com': 'account2',
                    'luxoticasupport3@eulerity.com': 'account3',
                    'luxoticasupport4@eulerity.com': 'account4'
                }
                
                for _, row in df.iterrows():
                    account_key = account_mapping.get(row.get('account_email'), 'account1')
                    
                    self.config['accounts'][account_key]['properties'].append({
                        'property_id': str(row['property_id']),
                        'location_name': row['location_name'],
                        'appointment_event_name': row['appointment_event_name']
                    })
                
                print(f"✅ Imported {len(df)} properties from CSV")
                
            except Exception as e:
                print(f"❌ Error importing CSV: {e}")
        else:
            print("⏭️  CSV import skipped")

    def setup_export(self):
        """Setup export configuration"""
        formats = input("Export formats (xlsx,csv,json) [xlsx,csv]: ").strip()
        if not formats:
            formats = "xlsx,csv"
        
        output_path = input("Output directory [./exports/]: ").strip()
        if not output_path:
            output_path = "./exports/"
        
        self.config['export'] = {
            'format': formats.split(',')[0],  # Primary format
            'output_path': output_path,
            'filename_template': 'vision_source_data_{date}.{format}'
        }
        
        # Create export directory
        os.makedirs(output_path, exist_ok=True)
        print("✅ Export configuration saved")

    def save_config(self):
        """Save configuration to file"""
        with open('config.yaml', 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)
        
        print("✅ Configuration saved to config.yaml")

    def show_next_steps(self):
        """Show next steps after setup"""
        print("""
🎉 Setup completed successfully!

Next steps:
1. Install dependencies:
   pip install -r requirements.txt

2. Authenticate accounts:
   python vision_source_pull.py --authenticate

3. Test data extraction:
   python vision_source_pull.py --extract --formats xlsx

4. Set up automation:
   python scheduler.py --cron

Need help? Check README.md for detailed instructions.
""")

def main():
    wizard = SetupWizard()
    wizard.run_setup()

if __name__ == "__main__":
    main()