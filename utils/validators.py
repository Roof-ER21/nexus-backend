"""
Input Validators
Validate and sanitize user input
"""

import re
from typing import Optional
from datetime import datetime
from loguru import logger

from config import settings


class InputValidator:
    """
    Validate various input types
    """

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email format

        Args:
            email: Email address

        Returns:
            True if valid
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_password(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < settings.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters"

        if settings.REQUIRE_PASSWORD_UPPERCASE and not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"

        if settings.REQUIRE_PASSWORD_LOWERCASE and not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"

        if settings.REQUIRE_PASSWORD_DIGIT and not re.search(r'\d', password):
            return False, "Password must contain at least one digit"

        if settings.REQUIRE_PASSWORD_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"

        return True, None

    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """
        Sanitize string input

        Args:
            text: Input text
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not text:
            return ""

        # Remove null bytes
        text = text.replace('\x00', '')

        # Trim to max length
        text = text[:max_length]

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        Validate phone number format

        Args:
            phone: Phone number

        Returns:
            True if valid format
        """
        # Remove common separators
        cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)

        # Check if it's digits and reasonable length
        return cleaned.isdigit() and 10 <= len(cleaned) <= 15

    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """
        Validate UUID format

        Args:
            uuid_string: UUID string

        Returns:
            True if valid UUID
        """
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(pattern, uuid_string.lower()))

    @staticmethod
    def validate_date(date_string: str, format: str = "%Y-%m-%d") -> tuple[bool, Optional[datetime]]:
        """
        Validate and parse date string

        Args:
            date_string: Date string
            format: Expected date format

        Returns:
            Tuple of (is_valid, parsed_datetime)
        """
        try:
            parsed = datetime.strptime(date_string, format)
            return True, parsed
        except ValueError:
            return False, None

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL format

        Args:
            url: URL string

        Returns:
            True if valid URL
        """
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, url, re.IGNORECASE))

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')

        # Remove null bytes
        filename = filename.replace('\x00', '')

        # Keep only safe characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            name = name[:250]
            filename = f"{name}.{ext}" if ext else name

        return filename

    @staticmethod
    def validate_scenario_id(scenario_id: str) -> bool:
        """
        Validate scenario ID format

        Args:
            scenario_id: Scenario ID (e.g., "scenario_1_1")

        Returns:
            True if valid format
        """
        pattern = r'^scenario_\d+_\d+$'
        return bool(re.match(pattern, scenario_id))

    @staticmethod
    def validate_json_field(data: dict, required_fields: list) -> tuple[bool, Optional[str]]:
        """
        Validate JSON data has required fields

        Args:
            data: JSON data dict
            required_fields: List of required field names

        Returns:
            Tuple of (is_valid, error_message)
        """
        missing = [field for field in required_fields if field not in data]

        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"

        return True, None

    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Remove HTML tags from text

        Args:
            text: Text potentially containing HTML

        Returns:
            Text with HTML removed
        """
        # Simple HTML tag removal (for more robust, use bleach library)
        return re.sub(r'<[^>]+>', '', text)

    @staticmethod
    def validate_score(score: float, min_score: float = 0, max_score: float = 100) -> bool:
        """
        Validate score is within range

        Args:
            score: Score value
            min_score: Minimum valid score
            max_score: Maximum valid score

        Returns:
            True if valid
        """
        return min_score <= score <= max_score

    @staticmethod
    def validate_category(category: str, valid_categories: list) -> bool:
        """
        Validate category is in allowed list

        Args:
            category: Category string
            valid_categories: List of valid categories

        Returns:
            True if valid
        """
        return category in valid_categories

    @staticmethod
    def sanitize_sql_input(text: str) -> str:
        """
        Basic SQL injection prevention (use parameterized queries instead!)

        Args:
            text: Input text

        Returns:
            Sanitized text
        """
        # Remove common SQL injection patterns
        dangerous_patterns = [
            r"';",
            r'";',
            r'--',
            r'/*',
            r'*/',
            r'xp_',
            r'sp_',
            r'exec\s',
            r'execute\s',
            r'union\s',
            r'select\s',
            r'insert\s',
            r'update\s',
            r'delete\s',
            r'drop\s',
            r'create\s',
            r'alter\s'
        ]

        text_lower = text.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, text_lower):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        return text


# Global instance
input_validator = InputValidator()


# Convenience functions
def validate_email(email: str) -> bool:
    """Validate email format"""
    return input_validator.validate_email(email)


def validate_password(password: str) -> tuple[bool, Optional[str]]:
    """Validate password strength"""
    return input_validator.validate_password(password)


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Sanitize string input"""
    return input_validator.sanitize_string(text, max_length)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    return input_validator.sanitize_filename(filename)
