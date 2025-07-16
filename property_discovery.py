#!/usr/bin/env python3
"""
Property Discovery for Vision Source GA4 System
Dynamically discovers all GA4 properties across authenticated accounts
"""

import yaml
import logging
import json
from typing import Dict, List, Optional
from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient
from google.analytics.admin_v1alpha.types import ListAccountsRequest, ListPropertiesRequest
from auth_manager import AuthManager

class PropertyDiscovery:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.auth_manager = AuthManager(config_path)
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def get_admin_client(self, account_name):
        """Get authenticated Analytics Admin client for an account"""
        credentials = self.auth_manager.get_credentials(account_name)
        
        # Update scopes to include admin API
        if "https://www.googleapis.com/auth/analytics.edit" not in credentials.scopes:
            self.logger.warning(f"Admin API scope not found for {account_name}. You may need to re-authenticate with admin permissions.")
        
        return AnalyticsAdminServiceClient(credentials=credentials)

    def discover_accounts_and_properties(self, account_name):
        """Discover all accounts and properties for a given authenticated account"""
        self.logger.info(f"Discovering properties for {account_name}...")
        
        try:
            client = self.get_admin_client(account_name)
            
            # List all accounts the user has access to
            accounts_request = ListAccountsRequest()
            accounts_response = client.list_accounts(request=accounts_request)
            
            discovered_data = {
                'account_email': self.config['accounts'][account_name]['email'],
                'accounts': []
            }
            
            for account in accounts_response.accounts:
                account_data = {
                    'account_id': account.name.split('/')[-1],
                    'account_name': account.display_name,
                    'account_full_name': account.name,
                    'properties': []
                }
                
                # List properties for this account
                try:
                    self.logger.info(f"Listing properties for account: {account.display_name} (ID: {account.name})")
                    properties_request = ListPropertiesRequest(filter=f"parent:{account.name}")
                    properties_response = client.list_properties(request=properties_request)
                    
                    total_properties_found = len(list(properties_response.properties))
                    self.logger.info(f"Found {total_properties_found} total properties for account {account.display_name}")
                    
                    ga4_count = 0
                    ua_count = 0
                    
                    for property_obj in properties_response.properties:
                        original_property_type = property_obj.property_type.name
                        
                        # Override: Treat all properties as GA4 since they've been migrated
                        # The API is incorrectly reporting them as PROPERTY_TYPE_ORDINARY
                        property_type = 'PROPERTY_TYPE_GA4'
                        
                        # Count as GA4 properties (since they all are)
                        ga4_count += 1
                        
                        # Include ALL properties in the results (treating them as GA4)
                        property_data = {
                            'property_id': property_obj.name.split('/')[-1],
                            'property_name': property_obj.display_name,
                            'property_full_name': property_obj.name,
                            'property_type': property_type,
                            'original_api_type': original_property_type,  # Keep track of what API reported
                            'website_url': getattr(property_obj, 'website_url', ''),
                            'industry_category': getattr(property_obj, 'industry_category', ''),
                            'time_zone': getattr(property_obj, 'time_zone', ''),
                            'currency_code': getattr(property_obj, 'currency_code', ''),
                            'create_time': property_obj.create_time.isoformat() if property_obj.create_time else None
                        }
                        account_data['properties'].append(property_data)
                        
                        # Log each property showing the override
                        self.logger.info(f"  Property: {property_obj.display_name} (ID: {property_obj.name.split('/')[-1]}) - API Type: {original_property_type} -> Treated as: {property_type}")
                    
                    self.logger.info(f"Found {ga4_count} GA4 properties (all properties treated as GA4) in account: {account.display_name}")
                    
                except Exception as e:
                    self.logger.error(f"Error listing properties for account {account.display_name}: {str(e)}")
                
                # Add all accounts, even if they don't have GA4 properties (for debugging)
                discovered_data['accounts'].append(account_data)
            
            total_properties = sum(len(acc['properties']) for acc in discovered_data['accounts'])
            self.logger.info(f"Total GA4 properties discovered for {account_name}: {total_properties}")
            
            return discovered_data
            
        except Exception as e:
            self.logger.error(f"Error discovering properties for {account_name}: {str(e)}")
            return None

    def discover_all_accounts(self):
        """Discover properties for all configured accounts"""
        all_discovered_data = {}
        
        for account_name, account_config in self.config['accounts'].items():
            if not account_config.get('enabled', True):
                self.logger.info(f"Skipping disabled account: {account_name}")
                continue
                
            if not account_config.get('refresh_token'):
                self.logger.warning(f"No refresh token found for {account_name}. Please authenticate first.")
                continue
            
            discovered_data = self.discover_accounts_and_properties(account_name)
            if discovered_data:
                all_discovered_data[account_name] = discovered_data
        
        return all_discovered_data

    def save_discovered_properties(self, discovered_data, filename="discovered_properties.json"):
        """Save discovered properties to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(discovered_data, f, indent=2, default=str)
        
        self.logger.info(f"Discovered properties saved to: {filename}")

    def get_property_summary(self, discovered_data):
        """Generate a summary of discovered properties"""
        summary = {
            'total_authenticated_accounts': len(discovered_data),
            'total_ga_accounts': 0,
            'total_properties': 0,
            'properties_by_account': {},
            'sample_properties': []
        }
        
        for auth_account, data in discovered_data.items():
            account_count = len(data['accounts'])
            property_count = sum(len(acc['properties']) for acc in data['accounts'])
            
            summary['total_ga_accounts'] += account_count
            summary['total_properties'] += property_count
            summary['properties_by_account'][auth_account] = {
                'email': data['account_email'],
                'ga_accounts': account_count,
                'properties': property_count
            }
            
            # Add sample properties
            for account in data['accounts'][:1]:  # Just first account
                for prop in account['properties'][:3]:  # First 3 properties
                    summary['sample_properties'].append({
                        'auth_account': auth_account,
                        'property_id': prop['property_id'],
                        'property_name': prop['property_name'],
                        'website_url': prop['website_url']
                    })
        
        return summary

    def filter_properties_by_name(self, discovered_data, name_filter="vision"):
        """Filter properties by name (useful for Vision Source properties)"""
        filtered_data = {}
        
        for auth_account, data in discovered_data.items():
            filtered_accounts = []
            
            for account in data['accounts']:
                filtered_properties = []
                
                for prop in account['properties']:
                    prop_name = prop['property_name'].lower()
                    website_url = prop.get('website_url', '').lower()
                    
                    if (name_filter.lower() in prop_name or 
                        name_filter.lower() in website_url):
                        filtered_properties.append(prop)
                
                if filtered_properties:
                    filtered_account = account.copy()
                    filtered_account['properties'] = filtered_properties
                    filtered_accounts.append(filtered_account)
            
            if filtered_accounts:
                filtered_data[auth_account] = data.copy()
                filtered_data[auth_account]['accounts'] = filtered_accounts
        
        return filtered_data

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vision Source Property Discovery")
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--discover', action='store_true', help='Discover all properties')
    parser.add_argument('--summary', action='store_true', help='Show summary of discovered properties')
    parser.add_argument('--filter', default='', help='Filter properties by name')
    parser.add_argument('--save', default='discovered_properties.json', help='Save results to file')
    
    args = parser.parse_args()
    
    discovery = PropertyDiscovery(args.config)
    
    if args.discover:
        print("🔍 Discovering properties across all accounts...")
        discovered_data = discovery.discover_all_accounts()
        
        if discovered_data:
            # Save to file
            discovery.save_discovered_properties(discovered_data, args.save)
            
            # Apply filter if specified
            if args.filter:
                print(f"🔍 Filtering properties containing '{args.filter}'...")
                discovered_data = discovery.filter_properties_by_name(discovered_data, args.filter)
                filter_filename = f"filtered_{args.save}"
                discovery.save_discovered_properties(discovered_data, filter_filename)
                print(f"📁 Filtered results saved to: {filter_filename}")
            
            # Show summary
            summary = discovery.get_property_summary(discovered_data)
            print("\n📊 Discovery Summary:")
            print(f"  Authenticated accounts: {summary['total_authenticated_accounts']}")
            print(f"  Total GA accounts: {summary['total_ga_accounts']}")
            print(f"  Total GA4 properties: {summary['total_properties']}")
            
            print("\n📋 Properties by account:")
            for account, info in summary['properties_by_account'].items():
                print(f"  {account} ({info['email']}): {info['properties']} properties")
            
            if summary['sample_properties']:
                print("\n🔎 Sample properties found:")
                for prop in summary['sample_properties']:
                    print(f"  {prop['property_name']} (ID: {prop['property_id']})")
                    if prop['website_url']:
                        print(f"    URL: {prop['website_url']}")
        else:
            print("❌ No properties discovered. Check authentication and permissions.")
    
    elif args.summary:
        try:
            with open(args.save, 'r') as f:
                discovered_data = json.load(f)
            
            summary = discovery.get_property_summary(discovered_data)
            print("📊 Summary from saved data:")
            print(f"  Total properties: {summary['total_properties']}")
            for account, info in summary['properties_by_account'].items():
                print(f"  {account}: {info['properties']} properties")
        except FileNotFoundError:
            print(f"❌ File not found: {args.save}. Run with --discover first.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()