"""
Configuration loader for address validation pipeline.

Loads configuration from YAML file and environment variables.
Environment variables take precedence over config file values.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigLoader:
    """Load and manage pipeline configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Path to YAML config file. Defaults to config.yaml in same directory.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        self.config_path = config_path
        self.config = self._load_config()
        self._apply_env_overrides()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration."""
        # API configuration
        if os.getenv('SMARTYSTREETS_AUTH_ID'):
            self.config['api']['auth_id'] = os.getenv('SMARTYSTREETS_AUTH_ID')
        if os.getenv('SMARTYSTREETS_AUTH_TOKEN'):
            self.config['api']['auth_token'] = os.getenv('SMARTYSTREETS_AUTH_TOKEN')
        if os.getenv('BATCH_SIZE'):
            self.config['api']['batch_size'] = int(os.getenv('BATCH_SIZE'))

        # Cache configuration
        if os.getenv('DYNAMODB_CACHE_TABLE'):
            self.config['cache']['table_name'] = os.getenv('DYNAMODB_CACHE_TABLE')
        if os.getenv('CACHE_ENABLED'):
            self.config['cache']['enabled'] = os.getenv('CACHE_ENABLED').lower() == 'true'

        # AWS configuration
        if os.getenv('AWS_REGION'):
            self.config['aws_region'] = os.getenv('AWS_REGION')
        if os.getenv('S3_BUCKET'):
            self.config['s3_bucket'] = os.getenv('S3_BUCKET')

        # Logging
        if os.getenv('LOG_LEVEL'):
            self.config['logging']['level'] = os.getenv('LOG_LEVEL')

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'api.batch_size')
            default: Default value if key not found

        Returns:
            Configuration value

        Example:
            >>> config = ConfigLoader()
            >>> batch_size = config.get('api.batch_size', 100)
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration section."""
        return self.config.get('api', {})

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration section."""
        return self.config.get('cache', {})

    def get_deduplication_config(self) -> Dict[str, Any]:
        """Get deduplication configuration section."""
        return self.config.get('deduplication', {})

    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration section."""
        return self.config.get('output', {})

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.get('cache.enabled', True)

    def is_deduplication_enabled(self) -> bool:
        """Check if deduplication is enabled."""
        return self.get('deduplication.enabled', True)

    def get_batch_size(self) -> int:
        """Get API batch size."""
        return self.get('api.batch_size', 100)

    def get_max_retries(self) -> int:
        """Get max retry attempts."""
        return self.get('api.max_retries', 3)

    def __repr__(self) -> str:
        return f"ConfigLoader(config_path='{self.config_path}')"
