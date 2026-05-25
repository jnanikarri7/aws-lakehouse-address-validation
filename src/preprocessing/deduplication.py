"""
Address deduplication to reduce API calls.

Uses hash-based deduplication to identify identical addresses
before sending to validation API, reducing costs by ~40%.
"""

import hashlib
from typing import Dict, List, Set, Optional
from collections import defaultdict


class AddressDeduplicator:
    """Deduplicate addresses to reduce API calls."""

    def __init__(self, hash_algorithm: str = 'sha256'):
        """
        Initialize deduplicator.

        Args:
            hash_algorithm: Hashing algorithm to use (md5, sha1, sha256)
        """
        self.hash_algorithm = hash_algorithm
        self.seen_hashes: Set[str] = set()
        self.hash_to_addresses: Dict[str, List[Dict]] = defaultdict(list)

    def hash_address(self, address_string: str) -> str:
        """
        Generate hash of normalized address string.

        Args:
            address_string: Normalized address string

        Returns:
            Hex digest of hash
        """
        if self.hash_algorithm == 'md5':
            return hashlib.md5(address_string.encode()).hexdigest()
        elif self.hash_algorithm == 'sha1':
            return hashlib.sha1(address_string.encode()).hexdigest()
        else:  # sha256 (default)
            return hashlib.sha256(address_string.encode()).hexdigest()

    def deduplicate_batch(
        self,
        addresses: List[Dict],
        normalized_key: str = 'normalized_address'
    ) -> tuple[List[Dict], Dict[str, List[int]]]:
        """
        Deduplicate a batch of addresses.

        Args:
            addresses: List of address dictionaries
            normalized_key: Key containing normalized address string

        Returns:
            Tuple of (unique_addresses, hash_to_indices_map)

        Example:
            >>> deduper = AddressDeduplicator()
            >>> addresses = [
            ...     {'address_line1': '123 Main St', 'normalized_address': '123MAINST|BALTIMORE|MD|21201'},
            ...     {'address_line1': '123 Main Street', 'normalized_address': '123MAINST|BALTIMORE|MD|21201'},
            ...     {'address_line1': '456 Oak Ave', 'normalized_address': '456OAKAVE|BALTIMORE|MD|21202'},
            ... ]
            >>> unique, hash_map = deduper.deduplicate_batch(addresses)
            >>> len(unique)
            2
        """
        unique_addresses = []
        hash_to_indices = defaultdict(list)
        seen = set()

        for idx, address in enumerate(addresses):
            normalized = address.get(normalized_key, '')
            if not normalized:
                # If no normalized address, include as-is
                unique_addresses.append(address)
                continue

            addr_hash = self.hash_address(normalized)

            # Track which original indices map to this hash
            hash_to_indices[addr_hash].append(idx)

            # Only include first occurrence
            if addr_hash not in seen:
                seen.add(addr_hash)
                unique_addresses.append(address)

        return unique_addresses, dict(hash_to_indices)

    def calculate_deduplication_rate(
        self,
        total_count: int,
        unique_count: int
    ) -> float:
        """
        Calculate deduplication rate.

        Args:
            total_count: Total number of addresses
            unique_count: Number of unique addresses

        Returns:
            Deduplication rate (0.0 to 1.0)

        Example:
            >>> deduper = AddressDeduplicator()
            >>> deduper.calculate_deduplication_rate(1000, 600)
            0.4  # 40% were duplicates
        """
        if total_count == 0:
            return 0.0

        duplicate_count = total_count - unique_count
        return duplicate_count / total_count

    def get_duplicate_indices(
        self,
        hash_to_indices: Dict[str, List[int]]
    ) -> List[List[int]]:
        """
        Get groups of duplicate address indices.

        Args:
            hash_to_indices: Mapping from address hash to original indices

        Returns:
            List of index groups (each group represents duplicates)

        Example:
            >>> hash_map = {
            ...     'abc123': [0, 1, 5],
            ...     'def456': [2],
            ...     'ghi789': [3, 4]
            ... }
            >>> deduper = AddressDeduplicator()
            >>> deduper.get_duplicate_indices(hash_map)
            [[0, 1, 5], [3, 4]]  # Only groups with 2+ items
        """
        duplicate_groups = []

        for indices in hash_to_indices.values():
            if len(indices) > 1:
                duplicate_groups.append(indices)

        return duplicate_groups

    def apply_validation_results(
        self,
        validated_addresses: List[Dict],
        hash_to_indices: Dict[str, List[int]],
        normalized_key: str = 'normalized_address'
    ) -> List[Optional[Dict]]:
        """
        Apply validation results from unique addresses back to all original addresses.

        Args:
            validated_addresses: List of validated unique addresses
            hash_to_indices: Mapping from hash to original indices
            normalized_key: Key containing normalized address string

        Returns:
            List of validation results in original order (with duplicates filled in)

        Example:
            >>> # After validating unique addresses, apply results to all
            >>> deduper = AddressDeduplicator()
            >>> validated = [
            ...     {'normalized': 'A', 'validated': True},
            ...     {'normalized': 'B', 'validated': True}
            ... ]
            >>> hash_map = {'hash_a': [0, 1, 3], 'hash_b': [2]}
            >>> results = deduper.apply_validation_results(validated, hash_map, 'normalized')
            >>> len(results)
            4  # [result_A, result_A, result_B, result_A]
        """
        # Build hash to validation result map
        hash_to_result = {}
        for address in validated_addresses:
            normalized = address.get(normalized_key, '')
            if normalized:
                addr_hash = self.hash_address(normalized)
                hash_to_result[addr_hash] = address

        # Determine total number of original addresses
        max_index = max(max(indices) for indices in hash_to_indices.values())
        results = [None] * (max_index + 1)

        # Apply results to original indices
        for addr_hash, indices in hash_to_indices.items():
            if addr_hash in hash_to_result:
                result = hash_to_result[addr_hash]
                for idx in indices:
                    results[idx] = result.copy()

        return results

    def get_statistics(self) -> Dict[str, any]:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            'unique_hashes': len(self.seen_hashes),
            'hash_algorithm': self.hash_algorithm
        }

    def reset(self):
        """Reset deduplicator state."""
        self.seen_hashes.clear()
        self.hash_to_addresses.clear()
