# Vision Source GA4 Data Pull System

Automated data extraction system for 500+ Vision Source locations across multiple Google Analytics 4 accounts.

## Features

- **Multi-Account Authentication**: OAuth2 authentication for multiple GA4 accounts
- **Event Name Normalization**: Handles inconsistent appointment event names across properties
- **Automated Data Extraction**: Pulls new users and appointment booking data
- **Multiple Export Formats**: CSV, Excel, and JSON exports with summary sheets
- **Error Handling**: Retry logic and comprehensive error handling
- **Scheduling**: Automated daily/weekly data pulls
- **Logging**: Comprehensive logging for monitoring and debugging

## Quick Start

### 1. Installation

```bash
# Clone or download the project
cd vision-source-pull

# Install dependencies
pip install -r requirements.txt
```

### 2. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Analytics Data API
4. Create OAuth2 credentials:
   - Go to Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: Web application
   - Add redirect URI: `http://localhost:8080`
5. Download the client configuration

### 3. Configuration

Update `config.yaml` with your settings:

```yaml
oauth:
  client_id: "your-client-id.googleusercontent.com"
  client_secret: "your-client-secret"

accounts:
  account1:
    email: "luxoticasupport@eulerity.com"
    properties:
      - property_id: "123456789"
        location_name: "Vision Source Location 1"
        appointment_event_name: "book_appointments"
```

### 4. Authentication

```bash
# Authenticate all accounts
python vision_source_pull.py --authenticate
```

### 5. Extract Data

```bash
# Run data extraction
python vision_source_pull.py --extract

# Extract with specific formats
python vision_source_pull.py --extract --formats xlsx csv json
```

## Commands

### Data Extraction
```bash
# Basic extraction
python vision_source_pull.py --extract

# Validate configuration
python vision_source_pull.py --validate

# Setup new configuration
python vision_source_pull.py --setup
```

### Scheduling
```bash
# Run scheduler (continuous)
python scheduler.py --run

# Test daily pull
python scheduler.py --test-daily

# Generate cron jobs
python scheduler.py --cron

# Generate systemd service
python scheduler.py --systemd
```

## Configuration Guide

### Adding New Locations

1. Get the GA4 Property ID from Google Analytics
2. Identify the appointment event name used by that property
3. Add to `config.yaml`:

```yaml
accounts:
  account1:
    properties:
      - property_id: "YOUR_PROPERTY_ID"
        location_name: "Location Name"
        appointment_event_name: "book_appointments"
```

### Event Name Mapping

The system automatically normalizes these appointment event variations:
- `book_appointments`
- `book_appoinments` (misspelling)
- `schedule_appointment`
- `make_appointments`
- `appointment_booking`
- And more...

To add custom mappings, modify `event_normalizer.py`.

### Data Configuration

```yaml
data_config:
  metrics:
    - "newUsers"
    - "eventCount"
  date_range:
    start_date: "30daysAgo"  # or "7daysAgo", "yesterday"
    end_date: "today"
```

## Automation Setup

### Option 1: Cron Jobs (Linux/Mac)
```bash
# Generate cron entries
python scheduler.py --cron

# Add to crontab
crontab -e
```

### Option 2: Systemd Service (Linux)
```bash
# Generate service file
python scheduler.py --systemd

# Install as root
sudo systemctl daemon-reload
sudo systemctl enable vision-source-pull.service
sudo systemctl start vision-source-pull.service
```

### Option 3: Task Scheduler (Windows)
1. Use Task Scheduler to run `python vision_source_pull.py --extract`
2. Set desired frequency (daily/weekly)

## Output Files

### Excel Export (`vision_source_data_YYYYMMDD_HHMMSS.xlsx`)
- **Raw Data**: All extracted data
- **Location Summary**: Performance by location
- **Daily Summary**: Performance by date
- **Top Performers**: Best performing locations
- **Event Analysis**: Event name usage analysis

### CSV Export
- Raw data in comma-separated format

### JSON Export
- Structured data with metadata and summaries

## Troubleshooting

### Authentication Issues
```bash
# Clear stored credentials
python -c "import yaml; config = yaml.safe_load(open('config.yaml')); [config['accounts'][acc].update({'refresh_token': None}) for acc in config['accounts']]; yaml.dump(config, open('config.yaml', 'w'))"

# Re-authenticate
python vision_source_pull.py --authenticate
```

### Property Access Issues
- Ensure the account email has read access to the GA4 property
- Verify the Property ID is correct (numbers only)
- Check that the property is GA4 (not Universal Analytics)

### Event Not Found
- Check the exact event name in GA4
- Add variations to `event_normalizer.py`
- Use the event analysis report to identify unmapped events

### Rate Limiting
- The system includes retry logic with delays
- Google Analytics API has quotas - ensure you're within limits
- Consider spreading requests across time for large property counts

## Monitoring

### Log Files
- `vision_source_pull.log`: Main application logs
- `scheduler.log`: Scheduler logs

### Health Checks
```bash
# Validate configuration
python vision_source_pull.py --validate

# Test authentication
python vision_source_pull.py --authenticate

# Test extraction for one property
# (modify config temporarily to test single property)
```

## Security Notes

- Store OAuth credentials securely
- Never commit `config.yaml` with real credentials to version control
- Use environment variables for production deployments
- Regularly rotate OAuth refresh tokens
- Monitor access logs in Google Cloud Console

## Support

For issues:
1. Check the log files for error details
2. Verify configuration with `--validate`
3. Test authentication with `--authenticate`
4. Review Google Analytics API quotas and limits

## File Structure

```
vision-source-pull/
├── config.yaml              # Main configuration
├── vision_source_pull.py     # Main application
├── auth_manager.py          # OAuth2 authentication
├── ga4_client.py            # GA4 API client
├── event_normalizer.py      # Event name normalization
├── data_exporter.py         # Data export functionality
├── scheduler.py             # Automation scheduler
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── exports/                # Export directory
    ├── vision_source_data_*.xlsx
    ├── vision_source_data_*.csv
    └── vision_source_data_*.json
```