"""
Rate Limiting
Protect API endpoints from abuse
"""

from typing import Optional, Dict
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from loguru import logger

from config import settings


class RateLimiter:
    """
    In-memory rate limiter
    For production, use Redis for distributed rate limiting
    """

    def __init__(self):
        # Store: {identifier: {endpoint: [(timestamp, count)]}}
        self.requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self.cleanup_task = None

    def _get_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting"""
        # Try to get user from request state (set by auth middleware)
        if hasattr(request.state, 'user') and request.state.user:
            return f"user:{request.state.user.id}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")

        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return f"ip:{client_ip}"

    def _cleanup_old_requests(self):
        """Remove expired request records"""
        try:
            now = datetime.utcnow()
            cutoff_minute = now - timedelta(minutes=1)
            cutoff_hour = now - timedelta(hours=1)

            for identifier in list(self.requests.keys()):
                for endpoint in list(self.requests[identifier].keys()):
                    # Keep only requests within the hour
                    self.requests[identifier][endpoint] = [
                        (ts, count) for ts, count in self.requests[identifier][endpoint]
                        if ts > cutoff_hour
                    ]

                    # Remove empty endpoints
                    if not self.requests[identifier][endpoint]:
                        del self.requests[identifier][endpoint]

                # Remove empty identifiers
                if not self.requests[identifier]:
                    del self.requests[identifier]

            logger.debug(f"Rate limiter cleanup: {len(self.requests)} active identifiers")

        except Exception as e:
            logger.error(f"Error in rate limiter cleanup: {e}")

    async def check_rate_limit(
        self,
        request: Request,
        max_per_minute: Optional[int] = None,
        max_per_hour: Optional[int] = None
    ) -> bool:
        """
        Check if request should be rate limited

        Args:
            request: FastAPI request
            max_per_minute: Max requests per minute (default from config)
            max_per_hour: Max requests per hour (default from config)

        Returns:
            True if allowed, raises HTTPException if rate limited
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True

        try:
            identifier = self._get_identifier(request)
            endpoint = request.url.path
            now = datetime.utcnow()

            # Get request history
            history = self.requests[identifier][endpoint]

            # Count requests in last minute
            minute_ago = now - timedelta(minutes=1)
            requests_last_minute = sum(
                count for ts, count in history if ts > minute_ago
            )

            # Count requests in last hour
            hour_ago = now - timedelta(hours=1)
            requests_last_hour = sum(
                count for ts, count in history if ts > hour_ago
            )

            # Check limits
            max_minute = max_per_minute or settings.RATE_LIMIT_PER_MINUTE
            max_hour = max_per_hour or settings.RATE_LIMIT_PER_HOUR

            if requests_last_minute >= max_minute:
                logger.warning(f"Rate limit exceeded (minute) for {identifier} on {endpoint}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {max_minute} requests per minute. Try again in 60 seconds.",
                    headers={"Retry-After": "60"}
                )

            if requests_last_hour >= max_hour:
                logger.warning(f"Rate limit exceeded (hour) for {identifier} on {endpoint}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {max_hour} requests per hour. Try again later.",
                    headers={"Retry-After": "3600"}
                )

            # Record this request
            history.append((now, 1))

            # Periodic cleanup
            if len(self.requests) > 1000:  # Cleanup when many identifiers
                self._cleanup_old_requests()

            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Allow request on error (fail open)
            return True

    def get_rate_limit_info(self, request: Request) -> Dict:
        """
        Get rate limit information for identifier

        Args:
            request: FastAPI request

        Returns:
            Dict with rate limit info
        """
        try:
            identifier = self._get_identifier(request)
            endpoint = request.url.path
            now = datetime.utcnow()

            history = self.requests[identifier].get(endpoint, [])

            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)

            requests_last_minute = sum(
                count for ts, count in history if ts > minute_ago
            )
            requests_last_hour = sum(
                count for ts, count in history if ts > hour_ago
            )

            return {
                "identifier": identifier,
                "endpoint": endpoint,
                "requests_last_minute": requests_last_minute,
                "requests_last_hour": requests_last_hour,
                "limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
                "limit_per_hour": settings.RATE_LIMIT_PER_HOUR,
                "remaining_minute": max(0, settings.RATE_LIMIT_PER_MINUTE - requests_last_minute),
                "remaining_hour": max(0, settings.RATE_LIMIT_PER_HOUR - requests_last_hour)
            }

        except Exception as e:
            logger.error(f"Error getting rate limit info: {e}")
            return {}

    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("Rate limiter cleanup task started")

    async def _periodic_cleanup(self):
        """Periodic cleanup every 5 minutes"""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                self._cleanup_old_requests()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Rate limiter cleanup task stopped")


# Global instance
rate_limiter = RateLimiter()


# Dependency for FastAPI routes
async def check_rate_limit(request: Request):
    """FastAPI dependency for rate limiting"""
    await rate_limiter.check_rate_limit(request)


# Dependency with custom limits
def rate_limit(max_per_minute: int = None, max_per_hour: int = None):
    """Create rate limit dependency with custom limits"""
    async def _check(request: Request):
        await rate_limiter.check_rate_limit(
            request=request,
            max_per_minute=max_per_minute,
            max_per_hour=max_per_hour
        )
    return _check
