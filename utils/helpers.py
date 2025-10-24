"""
Helper Utilities
Common utility functions used across the application
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, date
import hashlib
import secrets
import string
from loguru import logger


class Helpers:
    """
    Collection of utility functions
    """

    @staticmethod
    def generate_random_string(length: int = 32, include_punctuation: bool = False) -> str:
        """
        Generate random string

        Args:
            length: Length of string
            include_punctuation: Include special characters

        Returns:
            Random string
        """
        characters = string.ascii_letters + string.digits
        if include_punctuation:
            characters += string.punctuation

        return ''.join(secrets.choice(characters) for _ in range(length))

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate secure random token

        Args:
            length: Token length

        Returns:
            URL-safe token
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def hash_string(text: str, algorithm: str = 'sha256') -> str:
        """
        Hash string using specified algorithm

        Args:
            text: Text to hash
            algorithm: Hash algorithm (sha256, sha512, md5)

        Returns:
            Hex digest of hash
        """
        if algorithm == 'sha256':
            return hashlib.sha256(text.encode()).hexdigest()
        elif algorithm == 'sha512':
            return hashlib.sha512(text.encode()).hexdigest()
        elif algorithm == 'md5':
            return hashlib.md5(text.encode()).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    @staticmethod
    def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate string to max length

        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add when truncated

        Returns:
            Truncated string
        """
        if len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def calculate_percentage(part: float, total: float, decimals: int = 1) -> float:
        """
        Calculate percentage

        Args:
            part: Part value
            total: Total value
            decimals: Decimal places

        Returns:
            Percentage
        """
        if total == 0:
            return 0.0

        percentage = (part / total) * 100
        return round(percentage, decimals)

    @staticmethod
    def format_currency(amount: float, currency: str = "USD") -> str:
        """
        Format amount as currency

        Args:
            amount: Amount to format
            currency: Currency code

        Returns:
            Formatted currency string
        """
        if currency == "USD":
            return f"${amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"

    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Format seconds as human-readable duration

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            return f"{hours}h"

    @staticmethod
    def calculate_streak(dates: List[date]) -> int:
        """
        Calculate current streak from list of dates

        Args:
            dates: List of dates (activity dates)

        Returns:
            Current streak count
        """
        if not dates:
            return 0

        # Sort dates in descending order
        sorted_dates = sorted(dates, reverse=True)

        # Check if today or yesterday is in the list
        today = date.today()
        yesterday = today - timedelta(days=1)

        if sorted_dates[0] not in [today, yesterday]:
            return 0

        # Count consecutive days
        streak = 1
        expected_date = sorted_dates[0] - timedelta(days=1)

        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == expected_date:
                streak += 1
                expected_date -= timedelta(days=1)
            else:
                break

        return streak

    @staticmethod
    def paginate_list(items: List[Any], page: int = 1, per_page: int = 20) -> Dict:
        """
        Paginate list of items

        Args:
            items: List of items
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Dict with paginated data
        """
        total = len(items)
        total_pages = (total + per_page - 1) // per_page

        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages if total_pages > 0 else 1

        start = (page - 1) * per_page
        end = start + per_page

        return {
            "items": items[start:end],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }

    @staticmethod
    def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        Split list into chunks

        Args:
            items: List to split
            chunk_size: Size of each chunk

        Returns:
            List of chunks
        """
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    @staticmethod
    def merge_dicts(dict1: Dict, dict2: Dict, deep: bool = False) -> Dict:
        """
        Merge two dictionaries

        Args:
            dict1: First dictionary
            dict2: Second dictionary (takes precedence)
            deep: Deep merge nested dicts

        Returns:
            Merged dictionary
        """
        result = dict1.copy()

        for key, value in dict2.items():
            if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Helpers.merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value

        return result

    @staticmethod
    def safe_get(data: Dict, path: str, default: Any = None) -> Any:
        """
        Safely get nested dictionary value

        Args:
            data: Dictionary
            path: Dot-separated path (e.g., "user.profile.name")
            default: Default value if not found

        Returns:
            Value or default
        """
        try:
            keys = path.split('.')
            value = data

            for key in keys:
                value = value[key]

            return value
        except (KeyError, TypeError):
            return default

    @staticmethod
    def calculate_elapsed_time(start: datetime, end: Optional[datetime] = None) -> Dict:
        """
        Calculate elapsed time between dates

        Args:
            start: Start datetime
            end: End datetime (default: now)

        Returns:
            Dict with elapsed time breakdown
        """
        if end is None:
            end = datetime.utcnow()

        delta = end - start

        days = delta.days
        seconds = delta.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60

        return {
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "total_seconds": int(delta.total_seconds()),
            "human_readable": Helpers.format_duration(int(delta.total_seconds()))
        }

    @staticmethod
    def deduplicate_list(items: List[Any], key: Optional[str] = None) -> List[Any]:
        """
        Remove duplicates from list

        Args:
            items: List of items
            key: Key to use for comparison (for dicts)

        Returns:
            List without duplicates
        """
        if not items:
            return []

        if key:
            seen = set()
            result = []
            for item in items:
                value = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
                if value not in seen:
                    seen.add(value)
                    result.append(item)
            return result
        else:
            # For simple types
            return list(dict.fromkeys(items))

    @staticmethod
    def group_by(items: List[Dict], key: str) -> Dict[Any, List[Dict]]:
        """
        Group list of dicts by key

        Args:
            items: List of dictionaries
            key: Key to group by

        Returns:
            Dict mapping key values to lists of items
        """
        result = {}

        for item in items:
            value = item.get(key)
            if value not in result:
                result[value] = []
            result[value].append(item)

        return result

    @staticmethod
    def filter_dict(data: Dict, allowed_keys: List[str]) -> Dict:
        """
        Filter dictionary to only allowed keys

        Args:
            data: Dictionary to filter
            allowed_keys: List of allowed keys

        Returns:
            Filtered dictionary
        """
        return {k: v for k, v in data.items() if k in allowed_keys}

    @staticmethod
    def is_recent(timestamp: datetime, minutes: int = 5) -> bool:
        """
        Check if timestamp is recent

        Args:
            timestamp: Datetime to check
            minutes: How many minutes is considered recent

        Returns:
            True if within last N minutes
        """
        if not timestamp:
            return False

        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return timestamp > cutoff

    @staticmethod
    def format_relative_time(timestamp: datetime) -> str:
        """
        Format timestamp as relative time (e.g., "2 hours ago")

        Args:
            timestamp: Datetime to format

        Returns:
            Relative time string
        """
        now = datetime.utcnow()
        delta = now - timestamp

        seconds = int(delta.total_seconds())

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            months = seconds // 2592000
            return f"{months} month{'s' if months != 1 else ''} ago"


# Global instance
helpers = Helpers()


# Convenience exports
generate_random_string = helpers.generate_random_string
generate_token = helpers.generate_token
hash_string = helpers.hash_string
truncate_string = helpers.truncate_string
calculate_percentage = helpers.calculate_percentage
format_currency = helpers.format_currency
format_duration = helpers.format_duration
calculate_streak = helpers.calculate_streak
paginate_list = helpers.paginate_list
