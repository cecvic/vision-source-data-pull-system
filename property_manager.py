#!/usr/bin/env python3
"""
Vision Source Property Manager
Bulk import and management of GA4 properties
"""

import csv
import yaml
import pandas as pd
import argparse
from typing import List, Dict
import logging

class PropertyManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Account email to key mapping
        self.account_mapping = {}
        for key, account in self.config['accounts'].items():
            self.account_mapping[account['email']] = key

    def import_from_csv(self, csv_file: str, dry_run: bool = False):
        """Import properties from CSV file"""
        try:
            df = pd.read_csv(csv_file)
            required_columns = ['property_id', 'location_name', 'appointment_event_name']
            
            # Validate columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"Missing required columns: {missing_columns}")
                return False
            
            # Process each row
            properties_added = 0
            for index, row in df.iterrows():
                property_data = {
                    'property_id': str(row['property_id']),
                    'location_name': row['location_name'],
                    'appointment_event_name': row['appointment_event_name']
                }
                
                # Determine account
                if 'account_email' in df.columns and pd.notna(row['account_email']):
                    account_key = self.account_mapping.get(row['account_email'])
                    if not account_key:
                        self.logger.warning(f"Unknown account email: {row['account_email']}. Using account1.")
                        account_key = 'account1'
                else:
                    # Distribute across accounts
                    account_key = f"account{(index % 4) + 1}"
                
                if not dry_run:
                    self.config['accounts'][account_key]['properties'].append(property_data)
                
                properties_added += 1
                self.logger.info(f"Added {property_data['location_name']} to {account_key}")
            
            if not dry_run:
                self._save_config()
                self.logger.info(f"Successfully imported {properties_added} properties")
            else:
                self.logger.info(f"Dry run: would import {properties_added} properties")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing CSV: {str(e)}")
            return False

    def export_to_csv(self, output_file: str = "properties_export.csv"):
        """Export all properties to CSV"""
        properties = []
        
        for account_key, account_config in self.config['accounts'].items():
            account_email = account_config['email']
            for prop in account_config.get('properties', []):
                properties.append({
                    'account_key': account_key,
                    'account_email': account_email,
                    'property_id': prop['property_id'],
                    'location_name': prop['location_name'],
                    'appointment_event_name': prop['appointment_event_name']
                })
        
        df = pd.DataFrame(properties)
        df.to_csv(output_file, index=False)
        self.logger.info(f"Exported {len(properties)} properties to {output_file}")
        return output_file

    def generate_template_csv(self, output_file: str = "properties_template.csv"):
        """Generate a template CSV for property import"""
        template_data = [
            {
                'property_id': '123456789',
                'location_name': 'Vision Source Example Location',
                'appointment_event_name': 'book_appointments',
                'account_email': 'luxoticasupport@eulerity.com'
            },
            {
                'property_id': '123456790',
                'location_name': 'Vision Source Another Location',
                'appointment_event_name': 'schedule_appointment',
                'account_email': 'luxoticasupport2@eulerity.com'
            }
        ]
        
        df = pd.DataFrame(template_data)
        df.to_csv(output_file, index=False)
        self.logger.info(f"Template CSV created: {output_file}")
        return output_file

    def validate_properties(self):
        """Validate all configured properties"""
        issues = []
        total_properties = 0
        
        for account_key, account_config in self.config['accounts'].items():
            account_email = account_config['email']
            properties = account_config.get('properties', [])
            total_properties += len(properties)
            
            self.logger.info(f"Validating {account_key} ({account_email}): {len(properties)} properties")
            
            # Check for duplicates within account
            property_ids = [p['property_id'] for p in properties]
            duplicates = set([x for x in property_ids if property_ids.count(x) > 1])
            if duplicates:
                issues.append(f"{account_key}: Duplicate property IDs: {duplicates}")
            
            # Check for missing required fields
            for i, prop in enumerate(properties):
                required_fields = ['property_id', 'location_name', 'appointment_event_name']
                missing_fields = [field for field in required_fields if not prop.get(field)]
                if missing_fields:
                    issues.append(f"{account_key} property {i}: Missing fields: {missing_fields}")
        
        # Check for property IDs used across multiple accounts
        all_property_ids = []
        for account_config in self.config['accounts'].values():
            for prop in account_config.get('properties', []):
                all_property_ids.append(prop['property_id'])
        
        duplicates_across_accounts = set([x for x in all_property_ids if all_property_ids.count(x) > 1])
        if duplicates_across_accounts:
            issues.append(f"Property IDs used in multiple accounts: {duplicates_across_accounts}")
        
        # Report results
        if issues:
            self.logger.warning(f"Validation found {len(issues)} issues:")
            for issue in issues:
                self.logger.warning(f"  - {issue}")
        else:
            self.logger.info(f"✅ Validation passed for all {total_properties} properties")
        
        return len(issues) == 0

    def list_properties(self, account_filter: str = None):
        """List all properties with details"""
        for account_key, account_config in self.config['accounts'].items():
            if account_filter and account_key != account_filter:
                continue
                
            account_email = account_config['email']
            properties = account_config.get('properties', [])
            
            print(f"\n{account_key} ({account_email}):")
            print(f"  Properties: {len(properties)}")
            
            for i, prop in enumerate(properties, 1):
                print(f"    {i:3d}. {prop['property_id']} - {prop['location_name']}")
                print(f"         Event: {prop['appointment_event_name']}")

    def remove_property(self, property_id: str):
        """Remove a property by ID"""
        for account_key, account_config in self.config['accounts'].items():
            properties = account_config.get('properties', [])
            original_count = len(properties)
            
            # Filter out the property
            account_config['properties'] = [
                p for p in properties if p['property_id'] != property_id
            ]
            
            if len(account_config['properties']) < original_count:
                self._save_config()
                self.logger.info(f"Removed property {property_id} from {account_key}")
                return True
        
        self.logger.warning(f"Property {property_id} not found")
        return False

    def get_statistics(self):
        """Get property statistics"""
        stats = {
            'total_properties': 0,
            'properties_by_account': {},
            'event_name_distribution': {},
            'accounts_with_properties': 0
        }
        
        for account_key, account_config in self.config['accounts'].items():
            properties = account_config.get('properties', [])
            count = len(properties)
            stats['total_properties'] += count
            stats['properties_by_account'][account_key] = count
            
            if count > 0:
                stats['accounts_with_properties'] += 1
            
            # Count event names
            for prop in properties:
                event_name = prop['appointment_event_name']
                stats['event_name_distribution'][event_name] = stats['event_name_distribution'].get(event_name, 0) + 1
        
        return stats

    def print_statistics(self):
        """Print property statistics"""
        stats = self.get_statistics()
        
        print("\n📊 Property Statistics")
        print("=" * 40)
        print(f"Total Properties: {stats['total_properties']}")
        print(f"Active Accounts: {stats['accounts_with_properties']}/4")
        
        print("\nProperties by Account:")
        for account_key, count in stats['properties_by_account'].items():
            email = self.config['accounts'][account_key]['email']
            print(f"  {account_key}: {count:3d} ({email})")
        
        print("\nEvent Name Distribution:")
        for event_name, count in sorted(stats['event_name_distribution'].items()):
            percentage = (count / stats['total_properties']) * 100
            print(f"  {event_name}: {count:3d} ({percentage:.1f}%)")

    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file, default_flow_style=False)

def main():
    parser = argparse.ArgumentParser(description="Vision Source Property Manager")
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import properties from CSV')
    import_parser.add_argument('csv_file', help='CSV file to import')
    import_parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without making changes')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export properties to CSV')
    export_parser.add_argument('--output', default='properties_export.csv', help='Output CSV file')
    
    # Template command
    template_parser = subparsers.add_parser('template', help='Generate template CSV')
    template_parser.add_argument('--output', default='properties_template.csv', help='Output template file')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all properties')
    list_parser.add_argument('--account', help='Filter by account key')
    
    # Validate command
    subparsers.add_parser('validate', help='Validate property configuration')
    
    # Statistics command
    subparsers.add_parser('stats', help='Show property statistics')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a property')
    remove_parser.add_argument('property_id', help='Property ID to remove')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = PropertyManager(args.config)
    
    if args.command == 'import':
        manager.import_from_csv(args.csv_file, args.dry_run)
    elif args.command == 'export':
        manager.export_to_csv(args.output)
    elif args.command == 'template':
        manager.generate_template_csv(args.output)
    elif args.command == 'list':
        manager.list_properties(args.account)
    elif args.command == 'validate':
        manager.validate_properties()
    elif args.command == 'stats':
        manager.print_statistics()
    elif args.command == 'remove':
        manager.remove_property(args.property_id)

if __name__ == "__main__":
    main()