"""
Address standardization and normalization.

Prepares raw addresses for validation by:
- Trimming whitespace
- Uppercasing
- Expanding abbreviations
- Removing special characters
- Normalizing unit designators
"""

import re
from typing import Dict, Optional


class AddressStandardizer:
    """Standardize addresses before validation."""

    # Common abbreviations (expand before sending to API)
    STREET_TYPES = {
        'AVE': 'AVENUE',
        'BLVD': 'BOULEVARD',
        'CIR': 'CIRCLE',
        'CT': 'COURT',
        'DR': 'DRIVE',
        'LN': 'LANE',
        'PKWY': 'PARKWAY',
        'PL': 'PLACE',
        'RD': 'ROAD',
        'ST': 'STREET',
        'TER': 'TERRACE',
        'WAY': 'WAY',
    }

    DIRECTIONALS = {
        'N': 'NORTH',
        'S': 'SOUTH',
        'E': 'EAST',
        'W': 'WEST',
        'NE': 'NORTHEAST',
        'NW': 'NORTHWEST',
        'SE': 'SOUTHEAST',
        'SW': 'SOUTHWEST',
    }

    UNIT_DESIGNATORS = {
        'APT': 'APARTMENT',
        'BLDG': 'BUILDING',
        'FL': 'FLOOR',
        'STE': 'SUITE',
        'UNIT': 'UNIT',
        'RM': 'ROOM',
        '#': 'NUMBER',
    }

    # State abbreviations
    STATES = {
        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT',
        'DELAWARE': 'DE', 'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI',
        'IDAHO': 'ID', 'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA',
        'KANSAS': 'KS', 'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME',
        'MARYLAND': 'MD', 'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI',
        'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO',
        'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
        'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM',
        'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND',
        'OHIO': 'OH', 'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA',
        'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD',
        'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT',
        'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
        'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC',
    }

    def __init__(self):
        """Initialize standardizer."""
        pass

    def standardize_address(self, address: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        """
        Standardize an address dictionary.

        Args:
            address: Dictionary with keys: address_line1, address_line2, city, state, zip_code

        Returns:
            Standardized address dictionary

        Example:
            >>> standardizer = AddressStandardizer()
            >>> address = {
            ...     'address_line1': '  123 main st apt 5b  ',
            ...     'city': 'silver spring',
            ...     'state': 'maryland',
            ...     'zip_code': '20910'
            ... }
            >>> standardizer.standardize_address(address)
            {
                'address_line1': '123 MAIN STREET',
                'address_line2': 'APT 5B',
                'city': 'SILVER SPRING',
                'state': 'MD',
                'zip_code': '20910'
            }
        """
        standardized = {}

        # Standardize address line 1
        if address.get('address_line1'):
            line1 = self._clean_string(address['address_line1'])
            standardized['address_line1'] = line1

        # Standardize address line 2 (unit designator)
        if address.get('address_line2'):
            line2 = self._clean_string(address['address_line2'])
            standardized['address_line2'] = line2
        else:
            standardized['address_line2'] = None

        # Standardize city
        if address.get('city'):
            standardized['city'] = self._clean_string(address['city'])
        else:
            standardized['city'] = None

        # Standardize state (convert full name to abbreviation)
        if address.get('state'):
            state = self._clean_string(address['state'])
            standardized['state'] = self._standardize_state(state)
        else:
            standardized['state'] = None

        # Standardize ZIP code (extract 5 or 9 digits)
        if address.get('zip_code'):
            standardized['zip_code'] = self._standardize_zip(address['zip_code'])
        else:
            standardized['zip_code'] = None

        return standardized

    def _clean_string(self, s: str) -> str:
        """Clean and normalize a string."""
        if not s:
            return ''

        # Strip whitespace
        s = s.strip()

        # Convert to uppercase
        s = s.upper()

        # Remove multiple spaces
        s = re.sub(r'\s+', ' ', s)

        return s

    def _standardize_state(self, state: str) -> str:
        """
        Standardize state to 2-letter abbreviation.

        Args:
            state: State name or abbreviation

        Returns:
            2-letter state abbreviation
        """
        if not state:
            return ''

        state = state.upper().strip()

        # If already 2 letters, return as-is
        if len(state) == 2 and state.isalpha():
            return state

        # Convert full name to abbreviation
        if state in self.STATES:
            return self.STATES[state]

        # Return as-is if not found
        return state

    def _standardize_zip(self, zip_code: str) -> str:
        """
        Standardize ZIP code to 5-digit or 9-digit format.

        Args:
            zip_code: ZIP code string

        Returns:
            Standardized ZIP code (5 or 9 digits)

        Examples:
            '20910' -> '20910'
            '20910-1234' -> '20910-1234'
            '209101234' -> '20910-1234'
            '20910 1234' -> '20910-1234'
        """
        if not zip_code:
            return ''

        # Remove all non-digits
        digits = re.sub(r'\D', '', zip_code)

        if len(digits) == 5:
            return digits
        elif len(digits) == 9:
            # Format as ZIP+4
            return f"{digits[:5]}-{digits[5:]}"
        elif len(digits) > 0:
            # Return first 5 digits if longer
            return digits[:5]
        else:
            return ''

    def extract_unit_number(self, address_line: str) -> tuple[str, Optional[str]]:
        """
        Extract unit number from address line.

        Args:
            address_line: Full address line

        Returns:
            Tuple of (street_address, unit_number)

        Examples:
            '123 MAIN ST APT 5B' -> ('123 MAIN ST', 'APT 5B')
            '123 MAIN ST #5B' -> ('123 MAIN ST', '#5B')
            '123 MAIN ST' -> ('123 MAIN ST', None)
        """
        if not address_line:
            return '', None

        address_line = self._clean_string(address_line)

        # Patterns for unit designators
        patterns = [
            r'\s+(APT|APARTMENT)\s+(\w+)$',
            r'\s+(STE|SUITE)\s+(\w+)$',
            r'\s+(UNIT)\s+(\w+)$',
            r'\s+(#)(\w+)$',
            r'\s+(BLDG|BUILDING)\s+(\w+)$',
            r'\s+(FL|FLOOR)\s+(\w+)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, address_line, re.IGNORECASE)
            if match:
                unit = f"{match.group(1)} {match.group(2)}"
                street = address_line[:match.start()].strip()
                return street, unit

        return address_line, None

    def is_valid_address(self, address: Dict[str, Optional[str]]) -> bool:
        """
        Check if address has minimum required fields.

        Args:
            address: Address dictionary

        Returns:
            True if address has required fields, False otherwise
        """
        required_fields = ['address_line1', 'city', 'state', 'zip_code']

        for field in required_fields:
            if not address.get(field) or not str(address[field]).strip():
                return False

        return True

    def normalize_for_comparison(self, address: Dict[str, Optional[str]]) -> str:
        """
        Normalize address to a canonical form for comparison/hashing.

        Args:
            address: Address dictionary

        Returns:
            Normalized address string for comparison

        Example:
            >>> standardizer = AddressStandardizer()
            >>> address = {'address_line1': '123 Main St', 'city': 'Baltimore', 'state': 'MD', 'zip_code': '21201'}
            >>> standardizer.normalize_for_comparison(address)
            '123MAINST|BALTIMORE|MD|21201'
        """
        parts = []

        # Address line 1 (remove all spaces and special chars)
        if address.get('address_line1'):
            addr = address['address_line1'].upper().strip()
            addr = re.sub(r'[^A-Z0-9]', '', addr)
            parts.append(addr)

        # City
        if address.get('city'):
            city = address['city'].upper().strip()
            city = re.sub(r'[^A-Z]', '', city)
            parts.append(city)

        # State
        if address.get('state'):
            parts.append(address['state'].upper().strip())

        # ZIP (first 5 digits only)
        if address.get('zip_code'):
            zip_code = re.sub(r'\D', '', address['zip_code'])
            if len(zip_code) >= 5:
                parts.append(zip_code[:5])

        return '|'.join(parts)
