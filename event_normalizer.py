import re
from typing import Dict, List, Set
import logging

class EventNormalizer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Define standard event categories and their variations
        self.event_patterns = {
            'appointment_booking': [
                'book_appointments',
                'book_appoinments',  # Common misspelling
                'schedule_appointment',
                'schedule_appointments', 
                'make_appointments',
                'make_appointment',
                'appointment_booking',
                'appointment_book',
                'book_appt',
                'schedule_appt',
                'appt_booking',
                'appointment_scheduled',
                'appointment_booked',
                'booking_appointment',
                'reserve_appointment',
                'appointment_reservation'
            ],
            'contact_form': [
                'contact_form_submit',
                'contact_form_submission',
                'contact_us',
                'form_submit',
                'inquiry_form',
                'contact_inquiry'
            ],
            'phone_call': [
                'phone_call',
                'call_now',
                'phone_click',
                'call_button',
                'phone_number_click'
            ]
        }
        
        # Create reverse mapping for quick lookup
        self.event_mapping = {}
        for standard_name, variations in self.event_patterns.items():
            for variation in variations:
                self.event_mapping[variation.lower()] = standard_name

    def normalize_event_name(self, event_name: str) -> str:
        """
        Normalize an event name to a standard format
        
        Args:
            event_name: The original event name from GA4
            
        Returns:
            Standardized event name
        """
        if not event_name:
            return 'unknown_event'
            
        # Convert to lowercase for matching
        clean_name = event_name.lower().strip()
        
        # Direct mapping lookup
        if clean_name in self.event_mapping:
            return self.event_mapping[clean_name]
        
        # Fuzzy matching for variations
        normalized = self._fuzzy_match(clean_name)
        if normalized:
            return normalized
            
        # If no match found, return original with cleaning
        return self._clean_event_name(event_name)

    def _fuzzy_match(self, event_name: str) -> str:
        """
        Perform fuzzy matching for event names that might have slight variations
        """
        # Remove common prefixes/suffixes
        cleaned = re.sub(r'^(event_|ga_|gtm_)', '', event_name)
        cleaned = re.sub(r'(_event|_click|_submit)$', '', cleaned)
        
        # Check for partial matches
        for standard_name, variations in self.event_patterns.items():
            for variation in variations:
                # Check if the cleaned name contains key terms
                if self._contains_key_terms(cleaned, variation):
                    return standard_name
                    
                # Check if variation contains the cleaned name
                if cleaned in variation.lower() or variation.lower() in cleaned:
                    return standard_name
        
        return None

    def _contains_key_terms(self, event_name: str, pattern: str) -> bool:
        """
        Check if event name contains key terms from the pattern
        """
        # Split pattern into key terms
        key_terms = re.split(r'[_\-\s]+', pattern.lower())
        
        # Check if event name contains most key terms
        matches = sum(1 for term in key_terms if term in event_name)
        return matches >= len(key_terms) * 0.7  # 70% of terms must match

    def _clean_event_name(self, event_name: str) -> str:
        """
        Clean an event name by standardizing format
        """
        # Convert to lowercase and replace spaces/hyphens with underscores
        cleaned = re.sub(r'[\s\-]+', '_', event_name.lower())
        
        # Remove special characters except underscores
        cleaned = re.sub(r'[^a-z0-9_]', '', cleaned)
        
        # Remove multiple consecutive underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        
        # Remove leading/trailing underscores
        cleaned = cleaned.strip('_')
        
        return cleaned

    def add_custom_mapping(self, event_name: str, standard_name: str):
        """
        Add a custom mapping for a specific event name
        """
        self.event_mapping[event_name.lower()] = standard_name
        self.logger.info(f"Added custom mapping: {event_name} -> {standard_name}")

    def get_appointment_events(self) -> List[str]:
        """
        Get all known appointment-related event variations
        """
        return self.event_patterns['appointment_booking']

    def analyze_events(self, event_names: List[str]) -> Dict:
        """
        Analyze a list of event names and provide mapping suggestions
        """
        analysis = {
            'mapped': {},
            'unmapped': [],
            'suggestions': {}
        }
        
        for event_name in set(event_names):  # Remove duplicates
            normalized = self.normalize_event_name(event_name)
            
            if normalized in self.event_patterns:
                analysis['mapped'][event_name] = normalized
            elif normalized == self._clean_event_name(event_name):
                analysis['unmapped'].append(event_name)
                # Suggest potential category
                analysis['suggestions'][event_name] = self._suggest_category(event_name)
            else:
                analysis['mapped'][event_name] = normalized
        
        return analysis

    def _suggest_category(self, event_name: str) -> str:
        """
        Suggest a category for an unmapped event name
        """
        name_lower = event_name.lower()
        
        # Check for appointment-related keywords
        appointment_keywords = ['book', 'schedule', 'appt', 'appointment', 'reserve']
        if any(keyword in name_lower for keyword in appointment_keywords):
            return 'appointment_booking'
        
        # Check for contact-related keywords
        contact_keywords = ['contact', 'form', 'inquiry', 'submit']
        if any(keyword in name_lower for keyword in contact_keywords):
            return 'contact_form'
        
        # Check for phone-related keywords
        phone_keywords = ['phone', 'call', 'tel', 'dial']
        if any(keyword in name_lower for keyword in phone_keywords):
            return 'phone_call'
        
        return 'other'

    def export_mapping_report(self, event_names: List[str], output_file: str = None):
        """
        Export a mapping report for manual review
        """
        analysis = self.analyze_events(event_names)
        
        report = f"""
Event Normalization Report
==========================

Mapped Events ({len(analysis['mapped'])}):
{'-' * 40}
"""
        for original, normalized in analysis['mapped'].items():
            report += f"{original} -> {normalized}\n"
        
        report += f"""
Unmapped Events ({len(analysis['unmapped'])}):
{'-' * 40}
"""
        for event in analysis['unmapped']:
            suggestion = analysis['suggestions'].get(event, 'unknown')
            report += f"{event} (suggested: {suggestion})\n"
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            self.logger.info(f"Mapping report exported to {output_file}")
        
        return report