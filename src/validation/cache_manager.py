"""
DynamoDB cache manager for validated addresses.

Caches previously validated addresses to reduce API costs.
Target: 70%+ cache hit rate on repeat runs.
"""

import json
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError


class CacheManager:
    """Manage address validation cache in DynamoDB."""

    def __init__(
        self,
        table_name: str,
        ttl_days: int = 90,
        region_name: str = 'us-east-1'
    ):
        """
        Initialize cache manager.

        Args:
            table_name: DynamoDB table name
            ttl_days: Time-to-live for cache entries (days)
            region_name: AWS region
        """
        self.table_name = table_name
        self.ttl_days = ttl_days
        self.region_name = region_name

        # Initialize DynamoDB client
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_writes = 0

    def get_cached_address(self, address_hash: str) -> Optional[Dict]:
        """
        Retrieve cached validated address.

        Args:
            address_hash: Hash of normalized address

        Returns:
            Cached validation result or None if not found/expired
        """
        try:
            response = self.table.get_item(
                Key={'address_hash': address_hash}
            )

            if 'Item' in response:
                item = response['Item']

                # Check if expired
                if self._is_expired(item.get('ttl')):
                    self.cache_misses += 1
                    return None

                self.cache_hits += 1
                return self._deserialize_item(item)
            else:
                self.cache_misses += 1
                return None

        except ClientError as e:
            print(f"Error retrieving from cache: {e}")
            self.cache_misses += 1
            return None

    def put_cached_address(
        self,
        address_hash: str,
        validated_address: Dict,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Store validated address in cache.

        Args:
            address_hash: Hash of normalized address
            validated_address: Validated address data
            metadata: Optional metadata (API response code, timestamp, etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate TTL (Unix timestamp)
            ttl = int((datetime.now() + timedelta(days=self.ttl_days)).timestamp())

            item = {
                'address_hash': address_hash,
                'validated_address': json.dumps(validated_address),
                'ttl': ttl,
                'cached_at': datetime.now().isoformat(),
            }

            if metadata:
                item['metadata'] = json.dumps(metadata)

            self.table.put_item(Item=item)
            self.cache_writes += 1
            return True

        except ClientError as e:
            print(f"Error writing to cache: {e}")
            return False

    def batch_get_cached_addresses(
        self,
        address_hashes: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """
        Retrieve multiple cached addresses in batch.

        Args:
            address_hashes: List of address hashes

        Returns:
            Dictionary mapping hash to cached result (None if not found)
        """
        results = {}

        # DynamoDB BatchGetItem limit is 100 items
        batch_size = 100
        for i in range(0, len(address_hashes), batch_size):
            batch = address_hashes[i:i + batch_size]

            try:
                response = self.dynamodb.batch_get_item(
                    RequestItems={
                        self.table_name: {
                            'Keys': [{'address_hash': h} for h in batch]
                        }
                    }
                )

                for item in response.get('Responses', {}).get(self.table_name, []):
                    if not self._is_expired(item.get('ttl')):
                        hash_key = item['address_hash']
                        results[hash_key] = self._deserialize_item(item)
                        self.cache_hits += 1

            except ClientError as e:
                print(f"Error in batch get: {e}")

        # Mark misses
        for hash_key in address_hashes:
            if hash_key not in results:
                results[hash_key] = None
                self.cache_misses += 1

        return results

    def batch_put_cached_addresses(
        self,
        cache_entries: List[Dict]
    ) -> int:
        """
        Store multiple validated addresses in batch.

        Args:
            cache_entries: List of dicts with 'address_hash' and 'validated_address'

        Returns:
            Number of successfully cached entries
        """
        success_count = 0
        ttl = int((datetime.now() + timedelta(days=self.ttl_days)).timestamp())

        # DynamoDB BatchWriteItem limit is 25 items
        batch_size = 25
        for i in range(0, len(cache_entries), batch_size):
            batch = cache_entries[i:i + batch_size]

            try:
                with self.table.batch_writer() as writer:
                    for entry in batch:
                        item = {
                            'address_hash': entry['address_hash'],
                            'validated_address': json.dumps(entry['validated_address']),
                            'ttl': ttl,
                            'cached_at': datetime.now().isoformat(),
                        }

                        if 'metadata' in entry:
                            item['metadata'] = json.dumps(entry['metadata'])

                        writer.put_item(Item=item)
                        success_count += 1
                        self.cache_writes += 1

            except ClientError as e:
                print(f"Error in batch write: {e}")

        return success_count

    def get_cache_statistics(self) -> Dict:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'cache_writes': self.cache_writes,
            'ttl_days': self.ttl_days
        }

    def reset_statistics(self):
        """Reset cache statistics counters."""
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_writes = 0

    def _is_expired(self, ttl: Optional[int]) -> bool:
        """
        Check if cache entry is expired.

        Args:
            ttl: Unix timestamp

        Returns:
            True if expired, False otherwise
        """
        if ttl is None:
            return False

        return int(time.time()) > ttl

    def _deserialize_item(self, item: Dict) -> Dict:
        """
        Deserialize DynamoDB item to Python dict.

        Args:
            item: DynamoDB item

        Returns:
            Deserialized data
        """
        result = {
            'address_hash': item['address_hash'],
            'validated_address': json.loads(item['validated_address']),
            'cached_at': item['cached_at']
        }

        if 'metadata' in item:
            result['metadata'] = json.loads(item['metadata'])

        return result

    def delete_cached_address(self, address_hash: str) -> bool:
        """
        Delete cached address.

        Args:
            address_hash: Hash of address to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.delete_item(Key={'address_hash': address_hash})
            return True
        except ClientError as e:
            print(f"Error deleting from cache: {e}")
            return False

    def clear_expired_entries(self) -> int:
        """
        Scan and delete expired cache entries.

        Note: This is expensive for large tables.
        Consider using DynamoDB TTL feature instead.

        Returns:
            Number of entries deleted
        """
        deleted_count = 0
        current_time = int(time.time())

        try:
            # Scan for expired items
            response = self.table.scan(
                FilterExpression='#ttl < :current_time',
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={':current_time': current_time}
            )

            # Delete expired items
            with self.table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={'address_hash': item['address_hash']})
                    deleted_count += 1

        except ClientError as e:
            print(f"Error clearing expired entries: {e}")

        return deleted_count
