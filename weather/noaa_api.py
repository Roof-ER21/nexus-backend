"""
NOAA Weather API Integration
Verify storm events for insurance claims
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from models import WeatherEvent
from loguru import logger


class NOAAWeatherAPI:
    """
    Interface with NOAA Storm Events Database
    Verify weather events for insurance claims
    """

    def __init__(self):
        self.base_url = "https://www.ncei.noaa.gov/access/services/data/v1"
        self.storm_events_url = f"{self.base_url}?dataset=storm-events"

        # NOAA dataset endpoints
        self.endpoints = {
            "storm_events": "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
        }

    async def verify_storm_event(
        self,
        location: Dict,
        date: datetime,
        event_type: Optional[str] = None,
        radius_miles: int = 25
    ) -> Dict:
        """
        Verify if a storm event occurred near location on given date

        Args:
            location: Dict with 'lat', 'lon', 'state', 'county'
            date: Date of alleged event
            event_type: Type of event (hail, wind, tornado, etc.)
            radius_miles: Search radius in miles

        Returns:
            Dict with verification results
        """
        try:
            # Search date range (±3 days for reporting delays)
            start_date = date - timedelta(days=3)
            end_date = date + timedelta(days=3)

            # Query NOAA database
            events = await self._query_storm_events(
                state=location.get('state'),
                county=location.get('county'),
                start_date=start_date,
                end_date=end_date,
                event_type=event_type
            )

            # Find events matching criteria
            matching_events = []

            for event in events:
                # Check date proximity
                event_date = datetime.fromisoformat(event['date'])
                date_diff = abs((event_date - date).days)

                if date_diff <= 3:
                    # Calculate distance if coordinates available
                    distance = None
                    if 'lat' in location and 'lon' in location and 'lat' in event and 'lon' in event:
                        distance = self._calculate_distance(
                            location['lat'], location['lon'],
                            event['lat'], event['lon']
                        )

                    if distance is None or distance <= radius_miles:
                        matching_events.append({
                            **event,
                            "date_difference_days": date_diff,
                            "distance_miles": distance
                        })

            # Build verification result
            verification = {
                "verified": len(matching_events) > 0,
                "search_date": date.isoformat(),
                "search_location": location,
                "matching_events": matching_events,
                "event_count": len(matching_events),
                "confidence": self._calculate_confidence(matching_events, date, location)
            }

            if matching_events:
                # Get closest/most severe event
                best_match = max(
                    matching_events,
                    key=lambda e: (
                        -e['date_difference_days'],
                        -e.get('distance_miles', 999),
                        e.get('magnitude', 0)
                    )
                )
                verification['best_match'] = best_match

            logger.info(f"Storm verification: {len(matching_events)} events found near {location.get('county', 'unknown')}, {location.get('state', 'unknown')}")

            return verification

        except Exception as e:
            logger.error(f"Error verifying storm event: {e}", exc_info=True)
            return {
                "verified": False,
                "error": str(e),
                "search_date": date.isoformat(),
                "matching_events": []
            }

    async def _query_storm_events(
        self,
        state: Optional[str] = None,
        county: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Query NOAA storm events database
        Note: This is a simplified implementation
        Real implementation would use NOAA's API or CSV files

        Args:
            state: State abbreviation
            county: County name
            start_date: Start date
            end_date: End date
            event_type: Event type filter

        Returns:
            List of storm events
        """
        try:
            # In production, this would query NOAA's actual database
            # For now, return simulated data structure
            # Real implementation: Parse CSV files from NOAA or use their API

            events = []

            # NOTE: This is a placeholder
            # Real implementation would:
            # 1. Download CSV files from NOAA
            # 2. Parse and filter by criteria
            # 3. Return structured event data

            logger.info(f"Queried NOAA for events: {state}, {county}, {start_date} to {end_date}")

            return events

        except Exception as e:
            logger.error(f"Error querying NOAA database: {e}")
            return []

    async def save_weather_event(
        self,
        db: AsyncSession,
        user_id: UUID,
        event_data: Dict,
        claim_reference: Optional[str] = None
    ) -> UUID:
        """
        Save verified weather event to database

        Args:
            db: Database session
            user_id: User saving the event
            event_data: Event data from verification
            claim_reference: Associated claim number

        Returns:
            UUID of created weather event
        """
        try:
            weather_event = WeatherEvent(
                user_id=user_id,
                event_type=event_data.get('event_type', 'storm'),
                event_date=datetime.fromisoformat(event_data['date']),
                location=event_data.get('location', {}),
                severity=event_data.get('severity'),
                description=event_data.get('description'),
                noaa_reference=event_data.get('noaa_event_id'),
                verification_data=event_data,
                claim_reference=claim_reference
            )

            db.add(weather_event)
            await db.flush()

            logger.info(f"Saved weather event: {weather_event.event_type} on {weather_event.event_date}")

            return weather_event.id

        except Exception as e:
            logger.error(f"Error saving weather event: {e}")
            raise

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula

        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate

        Returns:
            Distance in miles
        """
        try:
            from math import radians, cos, sin, asin, sqrt

            # Convert to radians
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

            # Haversine formula
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))

            # Radius of earth in miles
            r = 3956

            return c * r

        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return None

    def _calculate_confidence(
        self,
        events: List[Dict],
        target_date: datetime,
        target_location: Dict
    ) -> float:
        """
        Calculate confidence score for verification

        Args:
            events: List of matching events
            target_date: Target date
            target_location: Target location

        Returns:
            Confidence score (0-1)
        """
        if not events:
            return 0.0

        try:
            scores = []

            for event in events:
                score = 1.0

                # Date proximity (0.4 weight)
                event_date = datetime.fromisoformat(event['date'])
                date_diff = abs((event_date - target_date).days)
                date_score = max(0, 1 - (date_diff / 3))
                score *= (0.4 + 0.6 * date_score)

                # Distance proximity (0.3 weight)
                if event.get('distance_miles') is not None:
                    distance_score = max(0, 1 - (event['distance_miles'] / 25))
                    score *= (0.3 + 0.7 * distance_score)

                # Event magnitude (0.3 weight)
                if event.get('magnitude'):
                    # Higher magnitude = higher confidence
                    magnitude_score = min(1.0, event['magnitude'] / 100)
                    score *= (0.3 + 0.7 * magnitude_score)

                scores.append(score)

            # Return highest confidence
            return max(scores)

        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5

    async def get_historical_events(
        self,
        location: Dict,
        years: int = 5
    ) -> List[Dict]:
        """
        Get historical storm events for a location

        Args:
            location: Dict with location info
            years: Number of years to look back

        Returns:
            List of historical events
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * years)

            events = await self._query_storm_events(
                state=location.get('state'),
                county=location.get('county'),
                start_date=start_date,
                end_date=end_date
            )

            logger.info(f"Retrieved {len(events)} historical events for {location.get('county')}, {location.get('state')}")

            return events

        except Exception as e:
            logger.error(f"Error getting historical events: {e}")
            return []

    async def generate_weather_report(
        self,
        location: Dict,
        date: datetime,
        event_type: Optional[str] = None
    ) -> Dict:
        """
        Generate comprehensive weather report for claim

        Args:
            location: Location dict
            date: Date of event
            event_type: Type of event

        Returns:
            Dict with comprehensive weather report
        """
        try:
            # Verify event
            verification = await self.verify_storm_event(
                location=location,
                date=date,
                event_type=event_type
            )

            # Get historical context
            historical = await self.get_historical_events(
                location=location,
                years=2
            )

            # Build report
            report = {
                "location": location,
                "date": date.isoformat(),
                "verification": verification,
                "historical_context": {
                    "similar_events_2_years": len(historical),
                    "recent_events": historical[:5] if historical else []
                },
                "report_generated": datetime.utcnow().isoformat(),
                "confidence": verification.get('confidence', 0)
            }

            # Add narrative
            if verification['verified']:
                best_match = verification.get('best_match', {})
                report['narrative'] = (
                    f"Weather event verified: {best_match.get('event_type', 'Storm')} "
                    f"occurred on {best_match.get('date', date.isoformat())} "
                    f"in {location.get('county', 'the area')}, {location.get('state', '')}. "
                    f"Event magnitude: {best_match.get('magnitude', 'N/A')}. "
                    f"Verification confidence: {verification['confidence']:.0%}."
                )
            else:
                report['narrative'] = (
                    f"No verified weather events found within 3 days of {date.isoformat()} "
                    f"in {location.get('county', 'the area')}, {location.get('state', '')}. "
                    f"Historical data shows {len(historical)} similar events in the past 2 years."
                )

            logger.info(f"Generated weather report for {location.get('county')}, {location.get('state')}")

            return report

        except Exception as e:
            logger.error(f"Error generating weather report: {e}")
            return {"error": str(e)}


# Global instance
noaa_weather_api = NOAAWeatherAPI()
