import pandas as pd
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging

class DataExporter:
    def __init__(self, config):
        self.config = config
        self.export_config = config.get('export', {})
        self.output_path = self.export_config.get('output_path', './exports/')
        self.filename_template = self.export_config.get('filename_template', 'vision_source_data_{date}.{format}')
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_path, exist_ok=True)
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def export_data(self, data: pd.DataFrame, format_type: str = None, custom_filename: str = None) -> str:
        """
        Export data to specified format
        
        Args:
            data: DataFrame containing the extracted data
            format_type: Export format ('csv', 'xlsx', 'json')
            custom_filename: Custom filename (optional)
            
        Returns:
            Path to exported file
        """
        if data.empty:
            self.logger.warning("No data to export")
            return None
            
        format_type = format_type or self.export_config.get('format', 'xlsx')
        
        # Generate filename
        if custom_filename:
            filename = custom_filename
        else:
            current_date = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = self.filename_template.format(date=current_date, format=format_type)
        
        filepath = os.path.join(self.output_path, filename)
        
        # Export based on format
        if format_type.lower() == 'csv':
            data.to_csv(filepath, index=False)
        elif format_type.lower() == 'xlsx':
            self._export_excel_with_sheets(data, filepath)
        elif format_type.lower() == 'json':
            self._export_json(data, filepath)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        self.logger.info(f"Data exported to: {filepath}")
        return filepath

    def _export_excel_with_sheets(self, data: pd.DataFrame, filepath: str):
        """Export data to Excel with multiple sheets"""
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Main data sheet
            data.to_excel(writer, sheet_name='Raw Data', index=False)
            
            # Summary by location
            summary_by_location = self._create_location_summary(data)
            if not summary_by_location.empty:
                summary_by_location.to_excel(writer, sheet_name='Location Summary', index=False)
            
            # Summary by date
            summary_by_date = self._create_date_summary(data)
            if not summary_by_date.empty:
                summary_by_date.to_excel(writer, sheet_name='Daily Summary', index=False)
            
            # Top performers
            top_performers = self._create_top_performers(data)
            if not top_performers.empty:
                top_performers.to_excel(writer, sheet_name='Top Performers', index=False)
            
            # Event analysis
            event_analysis = self._create_event_analysis(data)
            if not event_analysis.empty:
                event_analysis.to_excel(writer, sheet_name='Event Analysis', index=False)

    def _export_json(self, data: pd.DataFrame, filepath: str):
        """Export data to JSON with structured format"""
        export_data = {
            'metadata': {
                'export_date': datetime.now().isoformat(),
                'total_locations': data['location_name'].nunique(),
                'date_range': {
                    'start': data['date'].min(),
                    'end': data['date'].max()
                },
                'total_records': len(data)
            },
            'raw_data': data.to_dict('records'),
            'summary': {
                'by_location': self._create_location_summary(data).to_dict('records'),
                'by_date': self._create_date_summary(data).to_dict('records'),
                'top_performers': self._create_top_performers(data).to_dict('records')
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

    def _create_location_summary(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create summary statistics by location"""
        if data.empty:
            return pd.DataFrame()
            
        summary = data.groupby(['location_name', 'property_id']).agg({
            'new_users': 'sum',
            'event_count': 'sum',
            'original_event_name': 'first'
        }).reset_index()
        
        summary['conversion_rate'] = (summary['event_count'] / summary['new_users'] * 100).round(2)
        summary['conversion_rate'] = summary['conversion_rate'].fillna(0)
        
        # Sort by total appointments
        summary = summary.sort_values('event_count', ascending=False)
        
        return summary

    def _create_date_summary(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create summary statistics by date"""
        if data.empty:
            return pd.DataFrame()
            
        summary = data.groupby('date').agg({
            'new_users': 'sum',
            'event_count': 'sum',
            'location_name': 'nunique'
        }).reset_index()
        
        summary.rename(columns={'location_name': 'active_locations'}, inplace=True)
        summary['avg_conversion_rate'] = (summary['event_count'] / summary['new_users'] * 100).round(2)
        summary['avg_conversion_rate'] = summary['avg_conversion_rate'].fillna(0)
        
        # Sort by date
        summary = summary.sort_values('date')
        
        return summary

    def _create_top_performers(self, data: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """Create top performing locations report"""
        if data.empty:
            return pd.DataFrame()
            
        summary = self._create_location_summary(data)
        
        # Top by appointments
        top_appointments = summary.nlargest(top_n, 'event_count')[['location_name', 'event_count', 'conversion_rate']].copy()
        top_appointments['metric'] = 'appointments'
        top_appointments.rename(columns={'event_count': 'value'}, inplace=True)
        
        # Top by conversion rate (min 10 new users)
        top_conversion = summary[summary['new_users'] >= 10].nlargest(top_n, 'conversion_rate')[['location_name', 'conversion_rate', 'event_count']].copy()
        top_conversion['metric'] = 'conversion_rate'
        top_conversion.rename(columns={'conversion_rate': 'value', 'event_count': 'appointments'}, inplace=True)
        
        # Top by new users
        top_users = summary.nlargest(top_n, 'new_users')[['location_name', 'new_users', 'conversion_rate']].copy()
        top_users['metric'] = 'new_users'
        top_users.rename(columns={'new_users': 'value'}, inplace=True)
        
        return pd.concat([top_appointments, top_conversion, top_users], ignore_index=True)

    def _create_event_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create event name analysis report"""
        if data.empty:
            return pd.DataFrame()
            
        analysis = data.groupby(['original_event_name', 'event_name']).agg({
            'location_name': 'nunique',
            'event_count': 'sum'
        }).reset_index()
        
        analysis.rename(columns={
            'location_name': 'locations_using',
            'event_name': 'normalized_name'
        }, inplace=True)
        
        # Sort by usage
        analysis = analysis.sort_values('locations_using', ascending=False)
        
        return analysis

    def export_multiple_formats(self, data: pd.DataFrame, formats: List[str] = None) -> Dict[str, str]:
        """Export data in multiple formats"""
        formats = formats or ['xlsx', 'csv']
        exported_files = {}
        
        for format_type in formats:
            try:
                filepath = self.export_data(data, format_type)
                if filepath:
                    exported_files[format_type] = filepath
            except Exception as e:
                self.logger.error(f"Failed to export {format_type}: {str(e)}")
        
        return exported_files

    def create_dashboard_data(self, data: pd.DataFrame) -> Dict:
        """Create data structure suitable for dashboard/visualization"""
        if data.empty:
            return {}
            
        return {
            'overview': {
                'total_locations': data['location_name'].nunique(),
                'total_new_users': data['new_users'].sum(),
                'total_appointments': data['event_count'].sum(),
                'overall_conversion_rate': round(data['event_count'].sum() / data['new_users'].sum() * 100, 2) if data['new_users'].sum() > 0 else 0,
                'date_range': {
                    'start': data['date'].min(),
                    'end': data['date'].max()
                }
            },
            'daily_trends': self._create_date_summary(data).to_dict('records'),
            'location_performance': self._create_location_summary(data).to_dict('records'),
            'top_performers': self._create_top_performers(data, 10).to_dict('records')
        }