"""
SmartyStreets API client for address validation.

Integrates with SmartyStreets US Street Address API with:
- Intelligent batching (up to 100 addresses per request)
- Exponential backoff retry logic
- Rate limiting (10 requests/second)
- DPV and ZIP+4 enrichment
"""

import time
from typing import List, Dict, Optional
from smartystreets_python_sdk import StaticCredentials, ClientBuilder
from smartystreets_python_sdk.us_street import Lookup as StreetLookup
from smartystreets_python_sdk.exceptions import SmartyException


class SmartyStreetsClient:
    """Client for SmartyStreets address validation API."""

    def __init__(
        self,
        auth_id: str,
        auth_token: str,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: int = 2,
        rate_limit_per_second: int = 10
    ):
        """
        Initialize SmartyStreets client.

        Args:
            auth_id: SmartyStreets auth ID
            auth_token: SmartyStreets auth token
            batch_size: Max addresses per batch (API limit: 100)
            max_retries: Max retry attempts on failure
            retry_delay: Initial retry delay in seconds (exponential backoff)
            rate_limit_per_second: Max requests per second
        """
        self.auth_id = auth_id
        self.auth_token = auth_token
        self.batch_size = min(batch_size, 100)  # API limit
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_per_second = rate_limit_per_second

        # Initialize SmartyStreets client
        credentials = StaticCredentials(auth_id, auth_token)
        self.client = ClientBuilder(credentials).build_us_street_api_client()

        # Statistics
        self.api_calls = 0
        self.successful_validations = 0
        self.failed_validations = 0
        self.total_addresses_processed = 0

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0 / rate_limit_per_second

    def validate_address(self, address: Dict) -> Dict:
        """
        Validate a single address.

        Args:
            address: Dictionary with address_line1, city, state, zip_code

        Returns:
            Dictionary with validation result and enrichment data
        """
        lookup = self._create_lookup(address)

        try:
            # Rate limiting
            self._wait_for_rate_limit()

            # Send to API
            self.client.send_lookup(lookup)
            self.api_calls += 1
            self.total_addresses_processed += 1

            # Process result
            if lookup.result:
                candidate = lookup.result[0]  # First match
                result = self._parse_candidate(candidate)
                result['validation_status'] = 'valid'
                self.successful_validations += 1
                return result
            else:
                # No match found
                self.failed_validations += 1
                return {
                    'validation_status': 'invalid',
                    'original_address': address,
                    'error': 'No match found'
                }

        except SmartyException as e:
            self.failed_validations += 1
            return {
                'validation_status': 'error',
                'original_address': address,
                'error': str(e)
            }

    def validate_batch(
        self,
        addresses: List[Dict],
        with_retry: bool = True
    ) -> List[Dict]:
        """
        Validate a batch of addresses.

        Args:
            addresses: List of address dictionaries
            with_retry: Whether to retry failed batches

        Returns:
            List of validation results in same order as input
        """
        results = []

        # Split into batches of max size
        for i in range(0, len(addresses), self.batch_size):
            batch = addresses[i:i + self.batch_size]
            batch_results = self._validate_batch_with_retry(batch) if with_retry else self._validate_single_batch(batch)
            results.extend(batch_results)

        return results

    def _validate_single_batch(self, batch: List[Dict]) -> List[Dict]:
        """
        Validate a single batch without retry.

        Args:
            batch: List of addresses (max 100)

        Returns:
            List of validation results
        """
        # Create lookups
        lookups = [self._create_lookup(addr) for addr in batch]

        try:
            # Rate limiting
            self._wait_for_rate_limit()

            # Send batch to API
            self.client.send_batch(lookups)
            self.api_calls += 1
            self.total_addresses_processed += len(batch)

            # Process results
            results = []
            for i, lookup in enumerate(lookups):
                if lookup.result:
                    candidate = lookup.result[0]
                    result = self._parse_candidate(candidate)
                    result['validation_status'] = 'valid'
                    self.successful_validations += 1
                    results.append(result)
                else:
                    self.failed_validations += 1
                    results.append({
                        'validation_status': 'invalid',
                        'original_address': batch[i],
                        'error': 'No match found'
                    })

            return results

        except SmartyException as e:
            # Batch failed - mark all as errors
            self.failed_validations += len(batch)
            return [{
                'validation_status': 'error',
                'original_address': addr,
                'error': str(e)
            } for addr in batch]

    def _validate_batch_with_retry(self, batch: List[Dict]) -> List[Dict]:
        """
        Validate batch with exponential backoff retry.

        Args:
            batch: List of addresses

        Returns:
            List of validation results
        """
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                return self._validate_single_batch(batch)
            except Exception as e:
                last_error = e
                retry_count += 1

                if retry_count <= self.max_retries:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** (retry_count - 1))
                    print(f"Retry {retry_count}/{self.max_retries} after {delay}s: {e}")
                    time.sleep(delay)

        # All retries failed
        print(f"Batch validation failed after {self.max_retries} retries: {last_error}")
        self.failed_validations += len(batch)
        return [{
            'validation_status': 'error',
            'original_address': addr,
            'error': f'Failed after {self.max_retries} retries: {last_error}'
        } for addr in batch]

    def _create_lookup(self, address: Dict) -> StreetLookup:
        """
        Create SmartyStreets lookup object from address dict.

        Args:
            address: Address dictionary

        Returns:
            StreetLookup object
        """
        lookup = StreetLookup()
        lookup.street = address.get('address_line1', '')
        lookup.street2 = address.get('address_line2', '')
        lookup.city = address.get('city', '')
        lookup.state = address.get('state', '')
        lookup.zipcode = address.get('zip_code', '')
        lookup.match = 'invalid'  # Return candidates even if not exact match

        return lookup

    def _parse_candidate(self, candidate) -> Dict:
        """
        Parse SmartyStreets candidate to result dictionary.

        Args:
            candidate: SmartyStreets candidate object

        Returns:
            Parsed result dictionary with enrichment
        """
        components = candidate.components
        metadata = candidate.metadata
        analysis = candidate.analysis

        return {
            # Standardized address
            'delivery_line_1': candidate.delivery_line_1 or '',
            'last_line': candidate.last_line or '',
            'city': components.city_name or '',
            'state': components.state_abbreviation or '',
            'zip_code': components.zipcode or '',
            'zip_plus4': components.plus4_code or '',

            # Components
            'primary_number': components.primary_number or '',
            'street_name': components.street_name or '',
            'street_suffix': components.street_suffix or '',
            'secondary_designator': components.secondary_designator or '',
            'secondary_number': components.secondary_number or '',

            # DPV (Delivery Point Validation)
            'dpv_match_code': analysis.dpv_match_code or '',
            'dpv_footnotes': analysis.dpv_footnotes or '',
            'dpv_cmra': analysis.dpv_cmra or '',  # Commercial Mail Receiving Agency

            # Geocoding
            'latitude': metadata.latitude if metadata else None,
            'longitude': metadata.longitude if metadata else None,
            'precision': metadata.precision if metadata else None,

            # Additional metadata
            'county_fips': metadata.county_fips if metadata else '',
            'county_name': metadata.county_name if metadata else '',
            'time_zone': metadata.time_zone if metadata else '',
            'utc_offset': metadata.utc_offset if metadata else None,

            # Record type
            'record_type': metadata.record_type if metadata else '',
            'rdi': metadata.rdi if metadata else '',  # Residential Delivery Indicator

            # Confidence
            'active': analysis.active if analysis else '',
        }

    def _wait_for_rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def get_statistics(self) -> Dict:
        """
        Get API usage statistics.

        Returns:
            Dictionary with statistics
        """
        success_rate = (self.successful_validations / self.total_addresses_processed * 100) if self.total_addresses_processed > 0 else 0.0

        return {
            'api_calls': self.api_calls,
            'total_addresses_processed': self.total_addresses_processed,
            'successful_validations': self.successful_validations,
            'failed_validations': self.failed_validations,
            'success_rate_percent': round(success_rate, 2),
            'batch_size': self.batch_size,
            'rate_limit_per_second': self.rate_limit_per_second
        }

    def reset_statistics(self):
        """Reset statistics counters."""
        self.api_calls = 0
        self.successful_validations = 0
        self.failed_validations = 0
        self.total_addresses_processed = 0
