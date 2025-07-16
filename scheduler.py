#!/usr/bin/env python3
"""
Vision Source GA4 Data Pull Scheduler
Automated scheduling for regular data extraction
"""

import schedule
import time
import logging
import os
import sys
from datetime import datetime, timedelta
from vision_source_pull import VisionSourceDataPull
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders

class DataPullScheduler:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.setup_logging()
        
        # Load system for validation
        try:
            self.system = VisionSourceDataPull(config_path)
        except Exception as e:
            self.logger.error(f"Failed to initialize data pull system: {e}")
            sys.exit(1)

    def setup_logging(self):
        """Setup logging for scheduler"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scheduler.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def daily_pull(self):
        """Execute daily data pull"""
        self.logger.info("Starting scheduled daily data pull...")
        
        try:
            exported_files = self.system.run_full_extraction(['xlsx', 'csv'])
            
            if exported_files:
                self.logger.info("Daily pull completed successfully")
                self.send_notification("Daily Pull Success", exported_files)
            else:
                self.logger.error("Daily pull failed - no files exported")
                self.send_notification("Daily Pull Failed", {})
                
        except Exception as e:
            self.logger.error(f"Daily pull failed: {str(e)}")
            self.send_notification("Daily Pull Error", {}, str(e))

    def weekly_full_report(self):
        """Execute weekly comprehensive report"""
        self.logger.info("Starting scheduled weekly full report...")
        
        try:
            # Update config for weekly date range
            original_start = self.system.config['data_config']['date_range']['start_date']
            self.system.config['data_config']['date_range']['start_date'] = '7daysAgo'
            
            exported_files = self.system.run_full_extraction(['xlsx', 'csv', 'json'])
            
            # Restore original config
            self.system.config['data_config']['date_range']['start_date'] = original_start
            
            if exported_files:
                self.logger.info("Weekly report completed successfully")
                self.send_notification("Weekly Report Success", exported_files, is_weekly=True)
            else:
                self.logger.error("Weekly report failed")
                self.send_notification("Weekly Report Failed", {})
                
        except Exception as e:
            self.logger.error(f"Weekly report failed: {str(e)}")
            self.send_notification("Weekly Report Error", {}, str(e))

    def send_notification(self, subject: str, exported_files: dict, error_msg: str = None, is_weekly: bool = False):
        """Send email notification about pull results"""
        # This is a placeholder - implement based on your email requirements
        self.logger.info(f"Notification: {subject}")
        if exported_files:
            self.logger.info(f"Files: {list(exported_files.keys())}")
        if error_msg:
            self.logger.error(f"Error: {error_msg}")

    def run_scheduler(self):
        """Run the scheduler"""
        self.logger.info("Starting Vision Source Data Pull Scheduler")
        
        # Schedule daily pulls at 6 AM
        schedule.every().day.at("06:00").do(self.daily_pull)
        
        # Schedule weekly reports on Mondays at 7 AM
        schedule.every().monday.at("07:00").do(self.weekly_full_report)
        
        self.logger.info("Scheduler configured:")
        self.logger.info("  - Daily pulls: 6:00 AM")
        self.logger.info("  - Weekly reports: Monday 7:00 AM")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Scheduler error: {str(e)}")
                time.sleep(300)  # Wait 5 minutes before retrying

def create_systemd_service():
    """Create systemd service file for Linux automation"""
    service_content = f"""[Unit]
Description=Vision Source GA4 Data Pull Scheduler
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'visionuser')}
WorkingDirectory={os.getcwd()}
ExecStart=/usr/bin/python3 {os.path.join(os.getcwd(), 'scheduler.py')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_path = "/etc/systemd/system/vision-source-pull.service"
    
    print("Systemd service file content:")
    print("=" * 50)
    print(service_content)
    print("=" * 50)
    print(f"\nTo install this service, run as root:")
    print(f"1. Save the content above to: {service_path}")
    print("2. sudo systemctl daemon-reload")
    print("3. sudo systemctl enable vision-source-pull.service")
    print("4. sudo systemctl start vision-source-pull.service")

def create_cron_jobs():
    """Generate cron job entries"""
    current_dir = os.getcwd()
    python_path = sys.executable
    
    cron_entries = f"""# Vision Source GA4 Data Pull Cron Jobs
# Daily pull at 6:00 AM
0 6 * * * cd {current_dir} && {python_path} vision_source_pull.py --extract --formats xlsx csv >> /var/log/vision-source-daily.log 2>&1

# Weekly report on Mondays at 7:00 AM  
0 7 * * 1 cd {current_dir} && {python_path} vision_source_pull.py --extract --formats xlsx csv json >> /var/log/vision-source-weekly.log 2>&1
"""
    
    print("Cron job entries:")
    print("=" * 50)
    print(cron_entries)
    print("=" * 50)
    print("\nTo install these cron jobs:")
    print("1. Run: crontab -e")
    print("2. Add the entries above")
    print("3. Save and exit")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vision Source GA4 Data Pull Scheduler")
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--run', action='store_true', help='Run the scheduler')
    parser.add_argument('--systemd', action='store_true', help='Generate systemd service file')
    parser.add_argument('--cron', action='store_true', help='Generate cron job entries')
    parser.add_argument('--test-daily', action='store_true', help='Test daily pull')
    parser.add_argument('--test-weekly', action='store_true', help='Test weekly report')
    
    args = parser.parse_args()
    
    if args.systemd:
        create_systemd_service()
    elif args.cron:
        create_cron_jobs()
    elif args.test_daily:
        scheduler = DataPullScheduler(args.config)
        scheduler.daily_pull()
    elif args.test_weekly:
        scheduler = DataPullScheduler(args.config)
        scheduler.weekly_full_report()
    elif args.run:
        scheduler = DataPullScheduler(args.config)
        scheduler.run_scheduler()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()