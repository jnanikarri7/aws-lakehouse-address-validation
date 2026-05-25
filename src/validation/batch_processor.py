"""
Batch processor for address validation pipeline.

Orchestrates the complete workflow:
1. Standardize addresses
2. Deduplicate
3. Check cache
4. Call API for uncached addresses
5. Update cache
6. Apply results back to all addresses
"""

from typing import List, Dict, Optional
from src.preprocessing import AddressStandardizer, AddressDeduplicator
from src.validation import CacheManager, SmartyStreetsClient


class BatchProcessor:
    """Orchestrate address validation workflow."""

    def __init__(
        self,
        smartystreets_client: SmartyStreetsClient,
        cache_manager: Optional[CacheManager] = None,
        enable_deduplication: bool = True,
        enable_caching: bool = True
    ):
        """
        Initialize batch processor.

        Args:
            smartystreets_client: SmartyStreets API client
            cache_manager: DynamoDB cache manager (optional)
            enable_deduplication: Whether to deduplicate before validation
            enable_caching: Whether to use cache
        """
        self.api_client = smartystreets_client
        self.cache_manager = cache_manager
        self.enable_deduplication = enable_deduplication
        self.enable_caching = enable_caching and cache_manager is not None

        # Initialize standardizer and deduplicator
        self.standardizer = AddressStandardizer()
        self.deduplicator = AddressDeduplicator()

        # Statistics
        self.total_processed = 0
        self.cache_hits = 0
        self.api_calls = 0
        self.dedup_savings = 0

    def process_batch(self, addresses: List[Dict]) -> List[Dict]:
        """
        Process a batch of addresses through the complete pipeline.

        Args:
            addresses: List of raw address dictionaries

        Returns:
            List of validated addresses with enrichment in original order

        Pipeline:
        1. Standardize addresses
        2. Deduplicate (optional)
        3. Check cache (optional)
        4. Call API for uncached addresses
        5. Update cache
        6. Apply results back to all original addresses
        """
        self.total_processed += len(addresses)

        # Step 1: Standardize addresses
        standardized_addresses = []
        for addr in addresses:
            std_addr = self.standardizer.standardize_address(addr)
            std_addr['original_address'] = addr  # Keep original for reference
            std_addr['normalized_address'] = self.standardizer.normalize_for_comparison(std_addr)
            standardized_addresses.append(std_addr)

        # Step 2: Deduplicate (optional)
        if self.enable_deduplication:
            unique_addresses, hash_to_indices = self.deduplicator.deduplicate_batch(
                standardized_addresses,
                normalized_key='normalized_address'
            )
            dedup_savings = len(standardized_addresses) - len(unique_addresses)
            self.dedup_savings += dedup_savings
            print(f"Deduplication: {len(standardized_addresses)} -> {len(unique_addresses)} "
                  f"({dedup_savings} duplicates removed)")
        else:
            unique_addresses = standardized_addresses
            hash_to_indices = None

        # Step 3: Check cache (optional)
        addresses_to_validate = []
        cached_results = {}

        if self.enable_caching:
            # Get hashes for cache lookup
            address_hashes = [
                self.deduplicator.hash_address(addr['normalized_address'])
                for addr in unique_addresses
            ]

            # Batch get from cache
            cache_lookup = self.cache_manager.batch_get_cached_addresses(address_hashes)

            for i, addr in enumerate(unique_addresses):
                addr_hash = address_hashes[i]
                cached = cache_lookup.get(addr_hash)

                if cached:
                    # Cache hit
                    cached_results[i] = cached['validated_address']
                    self.cache_hits += 1
                else:
                    # Cache miss - need to validate
                    addresses_to_validate.append((i, addr))

            print(f"Cache: {len(cached_results)} hits, {len(addresses_to_validate)} misses")
        else:
            # No caching - validate all
            addresses_to_validate = list(enumerate(unique_addresses))

        # Step 4: Call API for uncached addresses
        validated_results = {}
        if addresses_to_validate:
            indices_to_validate = [idx for idx, _ in addresses_to_validate]
            addrs_to_validate = [addr for _, addr in addresses_to_validate]

            # Validate via API
            api_results = self.api_client.validate_batch(addrs_to_validate)
            self.api_calls += len(api_results)

            # Map results back to indices
            for idx, result in zip(indices_to_validate, api_results):
                validated_results[idx] = result

            print(f"API calls: {len(api_results)} addresses validated")

        # Step 5: Update cache
        if self.enable_caching and validated_results:
            cache_entries = []
            for idx, result in validated_results.items():
                addr = unique_addresses[idx]
                addr_hash = self.deduplicator.hash_address(addr['normalized_address'])

                cache_entries.append({
                    'address_hash': addr_hash,
                    'validated_address': result,
                    'metadata': {
                        'validation_status': result.get('validation_status'),
                        'cached_from_api': True
                    }
                })

            cached_count = self.cache_manager.batch_put_cached_addresses(cache_entries)
            print(f"Cached {cached_count} new validations")

        # Step 6: Combine cache hits and API results
        all_results = {**cached_results, **validated_results}

        # Step 7: Apply results back to original addresses (handle duplicates)
        if self.enable_deduplication and hash_to_indices:
            # Need to map unique results back to all original addresses
            final_results = []
            for i, std_addr in enumerate(standardized_addresses):
                addr_hash = self.deduplicator.hash_address(std_addr['normalized_address'])

                # Find which unique index this maps to
                unique_idx = None
                for hash_key, indices in hash_to_indices.items():
                    if i in indices:
                        # Find the first index in unique_addresses with this hash
                        for u_idx, u_addr in enumerate(unique_addresses):
                            u_hash = self.deduplicator.hash_address(u_addr['normalized_address'])
                            if u_hash == hash_key:
                                unique_idx = u_idx
                                break
                        break

                if unique_idx is not None and unique_idx in all_results:
                    result = all_results[unique_idx].copy()
                    result['original_address'] = std_addr['original_address']
                    final_results.append(result)
                else:
                    # No validation result (shouldn't happen)
                    final_results.append({
                        'validation_status': 'error',
                        'original_address': std_addr['original_address'],
                        'error': 'No validation result found'
                    })
        else:
            # No deduplication - results are 1:1
            final_results = [
                {**all_results.get(i, {}), 'original_address': std_addr['original_address']}
                for i, std_addr in enumerate(standardized_addresses)
            ]

        return final_results

    def get_statistics(self) -> Dict:
        """
        Get processing statistics.

        Returns:
            Dictionary with statistics
        """
        cache_hit_rate = (self.cache_hits / self.total_processed * 100) if self.total_processed > 0 else 0.0
        api_call_rate = (self.api_calls / self.total_processed * 100) if self.total_processed > 0 else 0.0

        stats = {
            'total_addresses_processed': self.total_processed,
            'cache_hits': self.cache_hits,
            'api_calls': self.api_calls,
            'deduplication_savings': self.dedup_savings,
            'cache_hit_rate_percent': round(cache_hit_rate, 2),
            'api_call_rate_percent': round(api_call_rate, 2),
        }

        # Add cache manager stats
        if self.cache_manager:
            stats['cache_manager'] = self.cache_manager.get_cache_statistics()

        # Add API client stats
        if self.api_client:
            stats['api_client'] = self.api_client.get_statistics()

        return stats

    def reset_statistics(self):
        """Reset all statistics counters."""
        self.total_processed = 0
        self.cache_hits = 0
        self.api_calls = 0
        self.dedup_savings = 0

        if self.cache_manager:
            self.cache_manager.reset_statistics()
        if self.api_client:
            self.api_client.reset_statistics()
