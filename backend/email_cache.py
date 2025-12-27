"""
Email Caching Service

Provides in-memory caching for email lists to improve performance and reduce API calls.
Supports TTL-based expiration and manual cache invalidation.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmailCache:
    """In-memory cache for email lists"""

    def __init__(self, ttl_minutes: int = 5):
        """
        Initialize email cache

        Args:
            ttl_minutes: Time-to-live in minutes (default: 5)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}  # {cache_key: {data, timestamp}}
        self.ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"✅ Email Cache initialized (TTL: {ttl_minutes} minutes)")

    def _get_cache_key(self, user_id: str, endpoint: str, **filters) -> str:
        """
        Generate cache key from user_id + endpoint + filters

        Args:
            user_id: User ID
            endpoint: Endpoint name (e.g., 'spam', 'inbox')
            **filters: Additional filter parameters

        Returns:
            Cache key string
        """
        filter_str = json.dumps(filters, sort_keys=True) if filters else "{}"
        return f"{user_id}:{endpoint}:{filter_str}"

    def get(self, user_id: str, endpoint: str, **filters) -> Optional[List]:
        """
        Get cached emails if not expired

        Args:
            user_id: User ID
            endpoint: Endpoint name
            **filters: Additional filter parameters

        Returns:
            Cached email list or None if not found/expired
        """
        cache_key = self._get_cache_key(user_id, endpoint, **filters)

        if cache_key in self.cache:
            entry = self.cache[cache_key]
            age = datetime.now() - entry['timestamp']

            # Check if expired
            if age < self.ttl:
                logger.info(f"Cache HIT for {endpoint} (user: {user_id}, age: {age.total_seconds():.1f}s)")
                return entry['data']
            else:
                # Expired - remove from cache
                logger.debug(f"Cache EXPIRED for {endpoint} (user: {user_id}, age: {age.total_seconds():.1f}s)")
                del self.cache[cache_key]

        logger.info(f"Cache MISS for {endpoint} (user: {user_id})")
        return None

    def set(self, user_id: str, endpoint: str, data: List, **filters):
        """
        Cache emails

        Args:
            user_id: User ID
            endpoint: Endpoint name
            data: Email list to cache
            **filters: Additional filter parameters
        """
        cache_key = self._get_cache_key(user_id, endpoint, **filters)
        self.cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
        logger.info(f"Cached {len(data)} emails for {endpoint} (user: {user_id})")

    def invalidate(self, user_id: str, endpoint: Optional[str] = None):
        """
        Invalidate cache for user (optionally specific endpoint)

        Args:
            user_id: User ID
            endpoint: Optional endpoint name to invalidate specific cache
        """
        if endpoint:
            # Remove specific endpoint cache entries
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{user_id}:{endpoint}:")]
            count = len(keys_to_remove)
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Invalidated {count} cache entries for {endpoint} (user: {user_id})")
        else:
            # Remove all caches for user
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{user_id}:")]
            count = len(keys_to_remove)
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Invalidated {count} cache entries for all endpoints (user: {user_id})")

    def clear_all(self):
        """Clear entire cache (all users, all endpoints)"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared entire cache ({count} entries)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        total_entries = len(self.cache)
        expired_count = 0
        active_count = 0

        for entry in self.cache.values():
            age = datetime.now() - entry['timestamp']
            if age >= self.ttl:
                expired_count += 1
            else:
                active_count += 1

        return {
            'total_entries': total_entries,
            'active_entries': active_count,
            'expired_entries': expired_count,
            'ttl_minutes': self.ttl.total_seconds() / 60
        }

    def cleanup_expired(self):
        """Remove all expired entries from cache"""
        keys_to_remove = []

        for cache_key, entry in self.cache.items():
            age = datetime.now() - entry['timestamp']
            if age >= self.ttl:
                keys_to_remove.append(cache_key)

        for key in keys_to_remove:
            del self.cache[key]

        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} expired cache entries")


# Singleton instance
_email_cache: Optional[EmailCache] = None


def get_email_cache() -> EmailCache:
    """
    Get singleton email cache instance

    Returns:
        EmailCache instance
    """
    global _email_cache
    if _email_cache is None:
        # Get TTL from environment variable or use default
        ttl_minutes = int(os.getenv('EMAIL_CACHE_TTL_MINUTES', '5'))
        _email_cache = EmailCache(ttl_minutes=ttl_minutes)
    return _email_cache
