#!/usr/bin/env python3
"""
Vision Source Health Monitor
System health checks and monitoring utilities
"""

import yaml
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

from auth_manager import AuthManager
from ga4_client import GA4DataClient

@dataclass
class HealthStatus:
    component: str
    status: str  # 'healthy', 'warning', 'error'
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class HealthMonitor:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
        except Exception as e:
            self.config = None
            self.config_error = str(e)
        
        self.setup_logging()
        self.health_checks = []

    def setup_logging(self):
        """Setup logging for health monitor"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def check_configuration(self) -> HealthStatus:
        """Check configuration file validity"""
        if self.config is None:
            return HealthStatus(
                component="Configuration",
                status="error",
                message=f"Configuration file error: {getattr(self, 'config_error', 'Unknown error')}"
            )
        
        required_sections = ['oauth', 'accounts', 'event_mapping', 'data_config']
        missing_sections = [section for section in required_sections if section not in self.config]
        
        if missing_sections:
            return HealthStatus(
                component="Configuration",
                status="error",
                message=f"Missing required sections: {missing_sections}"
            )
        
        # Check OAuth configuration
        oauth_config = self.config.get('oauth', {})
        required_oauth_fields = ['client_id', 'client_secret', 'redirect_uri', 'scopes']
        missing_oauth_fields = [field for field in required_oauth_fields if not oauth_config.get(field)]
        
        if missing_oauth_fields:
            return HealthStatus(
                component="Configuration",
                status="error",
                message=f"Missing OAuth fields: {missing_oauth_fields}"
            )
        
        # Count properties
        total_properties = sum(
            len(account.get('properties', []))
            for account in self.config['accounts'].values()
        )
        
        return HealthStatus(
            component="Configuration",
            status="healthy",
            message=f"Configuration valid with {total_properties} properties",
            details={'total_properties': total_properties}
        )

    def check_authentication(self) -> List[HealthStatus]:
        """Check authentication status for all accounts"""
        statuses = []
        
        if not self.config:
            return [HealthStatus(
                component="Authentication",
                status="error",
                message="Cannot check authentication - configuration error"
            )]
        
        try:
            auth_manager = AuthManager(self.config_path)
            
            for account_name, account_config in self.config['accounts'].items():
                try:
                    credentials = auth_manager.get_credentials(account_name)
                    
                    if credentials and credentials.valid:
                        statuses.append(HealthStatus(
                            component=f"Auth-{account_name}",
                            status="healthy",
                            message=f"Authentication valid for {account_config['email']}"
                        ))
                    elif credentials:
                        statuses.append(HealthStatus(
                            component=f"Auth-{account_name}",
                            status="warning",
                            message=f"Authentication needs refresh for {account_config['email']}"
                        ))
                    else:
                        statuses.append(HealthStatus(
                            component=f"Auth-{account_name}",
                            status="error",
                            message=f"No valid authentication for {account_config['email']}"
                        ))
                        
                except Exception as e:
                    statuses.append(HealthStatus(
                        component=f"Auth-{account_name}",
                        status="error",
                        message=f"Authentication error for {account_config['email']}: {str(e)}"
                    ))
            
        except Exception as e:
            statuses.append(HealthStatus(
                component="Authentication",
                status="error",
                message=f"Authentication system error: {str(e)}"
            ))
        
        return statuses

    def check_api_connectivity(self) -> List[HealthStatus]:
        """Test GA4 API connectivity for each account"""
        statuses = []
        
        if not self.config:
            return [HealthStatus(
                component="API Connectivity",
                status="error",
                message="Cannot check API - configuration error"
            )]
        
        try:
            ga4_client = GA4DataClient(self.config_path)
            
            for account_name, account_config in self.config['accounts'].items():
                properties = account_config.get('properties', [])
                if not properties:
                    statuses.append(HealthStatus(
                        component=f"API-{account_name}",
                        status="warning",
                        message=f"No properties configured for {account_name}"
                    ))
                    continue
                
                try:
                    client = ga4_client.get_client_for_account(account_name)
                    
                    # Test with first property
                    test_property = properties[0]
                    property_id = test_property['property_id']
                    
                    # Simple metadata request to test connectivity
                    from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
                    
                    test_request = RunReportRequest(
                        property=f"properties/{property_id}",
                        dimensions=[Dimension(name="date")],
                        metrics=[Metric(name="activeUsers")],
                        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
                        limit=1
                    )
                    
                    response = client.run_report(test_request)
                    
                    statuses.append(HealthStatus(
                        component=f"API-{account_name}",
                        status="healthy",
                        message=f"API connectivity verified for {account_name}",
                        details={
                            'test_property': property_id,
                            'response_rows': len(response.rows)
                        }
                    ))
                    
                except Exception as e:
                    statuses.append(HealthStatus(
                        component=f"API-{account_name}",
                        status="error",
                        message=f"API error for {account_name}: {str(e)}"
                    ))
        
        except Exception as e:
            statuses.append(HealthStatus(
                component="API Connectivity",
                status="error",
                message=f"API system error: {str(e)}"
            ))
        
        return statuses

    def check_export_directory(self) -> HealthStatus:
        """Check export directory status"""
        try:
            export_path = self.config.get('export', {}).get('output_path', './exports/')
            export_dir = Path(export_path)
            
            if not export_dir.exists():
                return HealthStatus(
                    component="Export Directory",
                    status="warning",
                    message=f"Export directory does not exist: {export_path}"
                )
            
            if not export_dir.is_dir():
                return HealthStatus(
                    component="Export Directory",
                    status="error",
                    message=f"Export path is not a directory: {export_path}"
                )
            
            # Check write permissions
            test_file = export_dir / "health_check_test.tmp"
            try:
                test_file.write_text("test")
                test_file.unlink()
                writable = True
            except:
                writable = False
            
            if not writable:
                return HealthStatus(
                    component="Export Directory",
                    status="error",
                    message=f"Export directory not writable: {export_path}"
                )
            
            # Count existing files
            existing_files = list(export_dir.glob("vision_source_data_*"))
            
            return HealthStatus(
                component="Export Directory",
                status="healthy",
                message=f"Export directory ready: {export_path}",
                details={
                    'path': str(export_path),
                    'existing_files': len(existing_files)
                }
            )
            
        except Exception as e:
            return HealthStatus(
                component="Export Directory",
                status="error",
                message=f"Export directory check error: {str(e)}"
            )

    def check_recent_exports(self) -> HealthStatus:
        """Check for recent export files"""
        try:
            export_path = Path(self.config.get('export', {}).get('output_path', './exports/'))
            
            if not export_path.exists():
                return HealthStatus(
                    component="Recent Exports",
                    status="warning",
                    message="Export directory does not exist"
                )
            
            # Find recent files (last 7 days)
            cutoff_date = datetime.now() - timedelta(days=7)
            recent_files = []
            
            for file in export_path.glob("vision_source_data_*"):
                if file.stat().st_mtime > cutoff_date.timestamp():
                    recent_files.append(file)
            
            if not recent_files:
                return HealthStatus(
                    component="Recent Exports",
                    status="warning",
                    message="No recent export files found (last 7 days)"
                )
            
            # Get most recent file info
            most_recent = max(recent_files, key=lambda f: f.stat().st_mtime)
            last_export = datetime.fromtimestamp(most_recent.stat().st_mtime)
            
            return HealthStatus(
                component="Recent Exports",
                status="healthy",
                message=f"Found {len(recent_files)} recent exports",
                details={
                    'recent_files': len(recent_files),
                    'last_export': last_export.isoformat(),
                    'latest_file': most_recent.name
                }
            )
            
        except Exception as e:
            return HealthStatus(
                component="Recent Exports",
                status="error",
                message=f"Recent exports check error: {str(e)}"
            )

    def run_all_checks(self) -> List[HealthStatus]:
        """Run all health checks"""
        all_statuses = []
        
        self.logger.info("Running health checks...")
        
        # Configuration check
        all_statuses.append(self.check_configuration())
        
        # Authentication checks
        all_statuses.extend(self.check_authentication())
        
        # API connectivity checks
        all_statuses.extend(self.check_api_connectivity())
        
        # Export directory check
        all_statuses.append(self.check_export_directory())
        
        # Recent exports check
        all_statuses.append(self.check_recent_exports())
        
        return all_statuses

    def print_health_report(self, statuses: List[HealthStatus]):
        """Print formatted health report"""
        print("\n🏥 Vision Source GA4 System Health Report")
        print("=" * 60)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Summary counts
        healthy_count = sum(1 for s in statuses if s.status == 'healthy')
        warning_count = sum(1 for s in statuses if s.status == 'warning')
        error_count = sum(1 for s in statuses if s.status == 'error')
        
        print(f"\n📊 Summary: {healthy_count} Healthy, {warning_count} Warnings, {error_count} Errors")
        
        # Group by status
        for status_type in ['error', 'warning', 'healthy']:
            components = [s for s in statuses if s.status == status_type]
            if not components:
                continue
            
            emoji = {'healthy': '✅', 'warning': '⚠️', 'error': '❌'}[status_type]
            print(f"\n{emoji} {status_type.upper()} ({len(components)})")
            print("-" * 40)
            
            for component in components:
                print(f"  {component.component}: {component.message}")
                if component.details:
                    for key, value in component.details.items():
                        print(f"    {key}: {value}")

    def export_health_report(self, statuses: List[HealthStatus], output_file: str = None):
        """Export health report to JSON"""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"health_report_{timestamp}.json"
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_checks': len(statuses),
                'healthy': sum(1 for s in statuses if s.status == 'healthy'),
                'warnings': sum(1 for s in statuses if s.status == 'warning'),
                'errors': sum(1 for s in statuses if s.status == 'error')
            },
            'checks': [
                {
                    'component': s.component,
                    'status': s.status,
                    'message': s.message,
                    'details': s.details,
                    'timestamp': s.timestamp.isoformat()
                }
                for s in statuses
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        self.logger.info(f"Health report exported to {output_file}")
        return output_file

def main():
    parser = argparse.ArgumentParser(description="Vision Source Health Monitor")
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--export', help='Export report to JSON file')
    parser.add_argument('--check', choices=['config', 'auth', 'api', 'exports'], 
                       help='Run specific check only')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    
    args = parser.parse_args()
    
    monitor = HealthMonitor(args.config)
    
    # Run specific check or all checks
    if args.check == 'config':
        statuses = [monitor.check_configuration()]
    elif args.check == 'auth':
        statuses = monitor.check_authentication()
    elif args.check == 'api':
        statuses = monitor.check_api_connectivity()
    elif args.check == 'exports':
        statuses = [monitor.check_export_directory(), monitor.check_recent_exports()]
    else:
        statuses = monitor.run_all_checks()
    
    # Print report
    if not args.quiet:
        monitor.print_health_report(statuses)
    
    # Export if requested
    if args.export:
        monitor.export_health_report(statuses, args.export)
    
    # Exit with error code if there are any errors
    error_count = sum(1 for s in statuses if s.status == 'error')
    exit(1 if error_count > 0 else 0)

if __name__ == "__main__":
    main()