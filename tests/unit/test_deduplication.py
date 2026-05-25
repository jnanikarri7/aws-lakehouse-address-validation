"""Unit tests for address deduplication."""

import pytest
from src.preprocessing.deduplication import AddressDeduplicator


class TestAddressDeduplicator:
    """Test AddressDeduplicator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deduper = AddressDeduplicator()

    def test_hash_address_consistent(self):
        """Test that same address always produces same hash."""
        addr = '123MAINST|BALTIMORE|MD|21201'
        hash1 = self.deduper.hash_address(addr)
        hash2 = self.deduper.hash_address(addr)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_hash_address_different_for_different_addresses(self):
        """Test that different addresses produce different hashes."""
        addr1 = '123MAINST|BALTIMORE|MD|21201'
        addr2 = '456OAKAVE|BALTIMORE|MD|21202'

        hash1 = self.deduper.hash_address(addr1)
        hash2 = self.deduper.hash_address(addr2)

        assert hash1 != hash2

    def test_deduplicate_batch_no_duplicates(self):
        """Test deduplication with no duplicates."""
        addresses = [
            {'address_line1': '123 Main St', 'normalized_address': '123MAINST|BALTIMORE|MD|21201'},
            {'address_line1': '456 Oak Ave', 'normalized_address': '456OAKAVE|BALTIMORE|MD|21202'},
            {'address_line1': '789 Elm St', 'normalized_address': '789ELMST|BALTIMORE|MD|21203'},
        ]

        unique, hash_map = self.deduper.deduplicate_batch(addresses)

        assert len(unique) == 3
        assert len(hash_map) == 3

    def test_deduplicate_batch_with_duplicates(self):
        """Test deduplication with duplicates."""
        addresses = [
            {'address_line1': '123 Main St', 'normalized_address': 'A'},
            {'address_line1': '123 Main Street', 'normalized_address': 'A'},  # Duplicate
            {'address_line1': '456 Oak Ave', 'normalized_address': 'B'},
            {'address_line1': '123 MAIN ST', 'normalized_address': 'A'},  # Duplicate
            {'address_line1': '789 Elm St', 'normalized_address': 'C'},
        ]

        unique, hash_map = self.deduper.deduplicate_batch(addresses)

        # Should have 3 unique addresses (A, B, C)
        assert len(unique) == 3

        # Check hash map
        hash_a = self.deduper.hash_address('A')
        hash_b = self.deduper.hash_address('B')
        hash_c = self.deduper.hash_address('C')

        assert len(hash_map[hash_a]) == 3  # Indices 0, 1, 3
        assert len(hash_map[hash_b]) == 1  # Index 2
        assert len(hash_map[hash_c]) == 1  # Index 4

    def test_calculate_deduplication_rate(self):
        """Test deduplication rate calculation."""
        # 1000 total, 600 unique = 40% duplicates
        rate = self.deduper.calculate_deduplication_rate(1000, 600)
        assert rate == 0.4

        # 100 total, 100 unique = 0% duplicates
        rate = self.deduper.calculate_deduplication_rate(100, 100)
        assert rate == 0.0

        # 100 total, 50 unique = 50% duplicates
        rate = self.deduper.calculate_deduplication_rate(100, 50)
        assert rate == 0.5

    def test_get_duplicate_indices(self):
        """Test getting duplicate index groups."""
        hash_map = {
            'abc123': [0, 1, 5],  # 3 duplicates
            'def456': [2],        # 1 unique
            'ghi789': [3, 4],     # 2 duplicates
            'jkl012': [6]         # 1 unique
        }

        duplicate_groups = self.deduper.get_duplicate_indices(hash_map)

        # Should only return groups with 2+ items
        assert len(duplicate_groups) == 2
        assert [0, 1, 5] in duplicate_groups
        assert [3, 4] in duplicate_groups

    def test_apply_validation_results(self):
        """Test applying validation results back to original addresses."""
        # Original addresses (indices 0-3)
        validated_addresses = [
            {'normalized_address': 'A', 'validated': True, 'dpv': 'Y'},
            {'normalized_address': 'B', 'validated': True, 'dpv': 'Y'}
        ]

        # Indices 0, 1, 3 map to address A; index 2 maps to address B
        hash_map = {
            self.deduper.hash_address('A'): [0, 1, 3],
            self.deduper.hash_address('B'): [2]
        }

        results = self.deduper.apply_validation_results(
            validated_addresses,
            hash_map,
            'normalized_address'
        )

        # Should have 4 results (original count)
        assert len(results) == 4

        # Check that duplicates get same result
        assert results[0]['validated'] is True
        assert results[1]['validated'] is True
        assert results[3]['validated'] is True
        assert results[2]['validated'] is True

        # Check that address A result is replicated
        assert results[0]['dpv'] == 'Y'
        assert results[1]['dpv'] == 'Y'
        assert results[3]['dpv'] == 'Y'

    def test_get_statistics(self):
        """Test getting deduplication statistics."""
        stats = self.deduper.get_statistics()

        assert 'unique_hashes' in stats
        assert 'hash_algorithm' in stats
        assert stats['hash_algorithm'] == 'sha256'

    def test_reset(self):
        """Test resetting deduplicator state."""
        # Add some hashes
        self.deduper.seen_hashes.add('test')
        self.deduper.hash_to_addresses['test'].append({'addr': '123'})

        assert len(self.deduper.seen_hashes) > 0
        assert len(self.deduper.hash_to_addresses) > 0

        # Reset
        self.deduper.reset()

        assert len(self.deduper.seen_hashes) == 0
        assert len(self.deduper.hash_to_addresses) == 0

    def test_different_hash_algorithms(self):
        """Test different hash algorithms."""
        deduper_md5 = AddressDeduplicator('md5')
        deduper_sha1 = AddressDeduplicator('sha1')
        deduper_sha256 = AddressDeduplicator('sha256')

        addr = '123MAINST|BALTIMORE|MD|21201'

        hash_md5 = deduper_md5.hash_address(addr)
        hash_sha1 = deduper_sha1.hash_address(addr)
        hash_sha256 = deduper_sha256.hash_address(addr)

        # Different algorithms should produce different hashes
        assert hash_md5 != hash_sha1
        assert hash_sha1 != hash_sha256
        assert hash_md5 != hash_sha256

        # Check expected lengths
        assert len(hash_md5) == 32   # MD5: 128 bits = 32 hex chars
        assert len(hash_sha1) == 40  # SHA-1: 160 bits = 40 hex chars
        assert len(hash_sha256) == 64  # SHA-256: 256 bits = 64 hex chars
