"""Unit tests for address standardization."""

import pytest
from src.preprocessing.standardization import AddressStandardizer


class TestAddressStandardizer:
    """Test AddressStandardizer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.standardizer = AddressStandardizer()

    def test_clean_string(self):
        """Test string cleaning."""
        assert self.standardizer._clean_string('  hello world  ') == 'HELLO WORLD'
        assert self.standardizer._clean_string('multiple   spaces') == 'MULTIPLE SPACES'
        assert self.standardizer._clean_string('') == ''

    def test_standardize_state_abbreviation(self):
        """Test state abbreviation conversion."""
        assert self.standardizer._standardize_state('Maryland') == 'MD'
        assert self.standardizer._standardize_state('MARYLAND') == 'MD'
        assert self.standardizer._standardize_state('md') == 'MD'
        assert self.standardizer._standardize_state('MD') == 'MD'
        assert self.standardizer._standardize_state('California') == 'CA'

    def test_standardize_zip_code(self):
        """Test ZIP code standardization."""
        assert self.standardizer._standardize_zip('20910') == '20910'
        assert self.standardizer._standardize_zip('20910-1234') == '20910-1234'
        assert self.standardizer._standardize_zip('209101234') == '20910-1234'
        assert self.standardizer._standardize_zip('20910 1234') == '20910-1234'
        assert self.standardizer._standardize_zip('2091') == '2091'
        assert self.standardizer._standardize_zip('') == ''

    def test_extract_unit_number(self):
        """Test unit number extraction."""
        street, unit = self.standardizer.extract_unit_number('123 MAIN ST APT 5B')
        assert street == '123 MAIN ST'
        assert unit == 'APT 5B'

        street, unit = self.standardizer.extract_unit_number('456 OAK AVE #10')
        assert street == '456 OAK AVE'
        assert unit == '# 10'

        street, unit = self.standardizer.extract_unit_number('789 ELM ST')
        assert street == '789 ELM ST'
        assert unit is None

    def test_standardize_address_full(self):
        """Test full address standardization."""
        address = {
            'address_line1': '  123 main st apt 5b  ',
            'address_line2': None,
            'city': 'silver spring',
            'state': 'maryland',
            'zip_code': '20910'
        }

        result = self.standardizer.standardize_address(address)

        assert result['address_line1'] == '123 MAIN ST APT 5B'
        assert result['city'] == 'SILVER SPRING'
        assert result['state'] == 'MD'
        assert result['zip_code'] == '20910'

    def test_standardize_address_with_zip_plus4(self):
        """Test address standardization with ZIP+4."""
        address = {
            'address_line1': '456 oak ave',
            'city': 'Baltimore',
            'state': 'MD',
            'zip_code': '212011234'
        }

        result = self.standardizer.standardize_address(address)

        assert result['address_line1'] == '456 OAK AVE'
        assert result['city'] == 'BALTIMORE'
        assert result['state'] == 'MD'
        assert result['zip_code'] == '21201-1234'

    def test_is_valid_address_complete(self):
        """Test validation of complete address."""
        address = {
            'address_line1': '123 Main St',
            'city': 'Baltimore',
            'state': 'MD',
            'zip_code': '21201'
        }
        assert self.standardizer.is_valid_address(address) is True

    def test_is_valid_address_missing_fields(self):
        """Test validation of incomplete address."""
        address = {
            'address_line1': '123 Main St',
            'city': '',
            'state': 'MD',
            'zip_code': '21201'
        }
        assert self.standardizer.is_valid_address(address) is False

        address = {
            'address_line1': None,
            'city': 'Baltimore',
            'state': 'MD',
            'zip_code': '21201'
        }
        assert self.standardizer.is_valid_address(address) is False

    def test_normalize_for_comparison(self):
        """Test address normalization for comparison."""
        address1 = {
            'address_line1': '123 Main St',
            'city': 'Baltimore',
            'state': 'MD',
            'zip_code': '21201'
        }
        address2 = {
            'address_line1': '123 MAIN STREET',
            'city': 'BALTIMORE',
            'state': 'MD',
            'zip_code': '21201-1234'
        }

        norm1 = self.standardizer.normalize_for_comparison(address1)
        norm2 = self.standardizer.normalize_for_comparison(address2)

        # Should be identical (street abbreviation and ZIP+4 ignored)
        assert norm1 == norm2
        assert norm1 == '123MAINST|BALTIMORE|MD|21201'

    def test_normalize_for_comparison_different_addresses(self):
        """Test that different addresses have different normalized forms."""
        address1 = {
            'address_line1': '123 Main St',
            'city': 'Baltimore',
            'state': 'MD',
            'zip_code': '21201'
        }
        address2 = {
            'address_line1': '456 Oak Ave',
            'city': 'Baltimore',
            'state': 'MD',
            'zip_code': '21201'
        }

        norm1 = self.standardizer.normalize_for_comparison(address1)
        norm2 = self.standardizer.normalize_for_comparison(address2)

        assert norm1 != norm2

    def test_empty_address(self):
        """Test handling of empty address."""
        address = {
            'address_line1': '',
            'city': '',
            'state': '',
            'zip_code': ''
        }

        result = self.standardizer.standardize_address(address)

        assert result['address_line1'] == ''
        assert result['city'] == ''
        assert result['state'] == ''
        assert result['zip_code'] == ''
