"""
Badge System
Achievement tracking and badge awarding for training progress
"""

from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime

from models import (
    TrainingBadge, UserBadge, UserTrainingProgress,
    ScenarioResult, TrainingSession
)
from loguru import logger


class BadgeSystem:
    """
    Manage achievement badges
    Track progress and award badges based on milestones
    """

    def __init__(self):
        # Badge categories
        self.categories = {
            "milestone": "Milestone Achievements",
            "skill": "Skill Mastery",
            "streak": "Consistency & Dedication",
            "special": "Special Achievements",
            "mastery": "Expert Level"
        }

    async def check_and_award_badges(
        self,
        db: AsyncSession,
        user_id: UUID,
        recent_result: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Check all badge conditions and award eligible badges

        Args:
            db: Database session
            user_id: User ID
            recent_result: Recent scenario result that triggered this check

        Returns:
            List of newly awarded badges
        """
        try:
            # Get user progress
            progress_result = await db.execute(
                select(UserTrainingProgress).where(
                    UserTrainingProgress.user_id == user_id
                )
            )
            progress = progress_result.scalar_one_or_none()

            if not progress:
                return []

            # Get already earned badges
            earned_result = await db.execute(
                select(UserBadge.badge_id).where(
                    UserBadge.user_id == user_id
                )
            )
            earned_badge_ids = [row[0] for row in earned_result.all()]

            # Get all available badges
            badges_result = await db.execute(select(TrainingBadge))
            all_badges = badges_result.scalars().all()

            # Check each badge
            newly_awarded = []

            for badge in all_badges:
                # Skip if already earned
                if badge.id in earned_badge_ids:
                    continue

                # Check if user qualifies
                if await self._check_badge_criteria(
                    db=db,
                    user_id=user_id,
                    badge=badge,
                    progress=progress,
                    recent_result=recent_result
                ):
                    # Award badge
                    user_badge = UserBadge(
                        user_id=user_id,
                        badge_id=badge.id
                    )
                    db.add(user_badge)
                    await db.flush()

                    newly_awarded.append({
                        "badge_id": badge.badge_id,
                        "name": badge.name,
                        "description": badge.description,
                        "category": badge.category,
                        "icon": badge.icon,
                        "rarity": badge.rarity
                    })

                    logger.info(f"Awarded badge '{badge.name}' to user {user_id}")

            if newly_awarded:
                await db.commit()

            return newly_awarded

        except Exception as e:
            logger.error(f"Error checking and awarding badges: {e}", exc_info=True)
            await db.rollback()
            return []

    async def _check_badge_criteria(
        self,
        db: AsyncSession,
        user_id: UUID,
        badge: TrainingBadge,
        progress: UserTrainingProgress,
        recent_result: Optional[Dict] = None
    ) -> bool:
        """
        Check if user meets badge criteria

        Args:
            db: Database session
            user_id: User ID
            badge: Badge to check
            progress: User's training progress
            recent_result: Recent scenario result

        Returns:
            True if criteria met
        """
        try:
            criteria = badge.criteria

            # Milestone badges (scenario completion count)
            if badge.category == "milestone":
                required_count = criteria.get("scenarios_completed", 0)
                return progress.total_scenarios_completed >= required_count

            # Skill badges (specific skill score threshold)
            elif badge.category == "skill":
                skill_name = criteria.get("skill")
                required_score = criteria.get("min_score", 0)

                if skill_name and progress.skill_scores:
                    skill_score = progress.skill_scores.get(skill_name, 0)
                    return skill_score >= required_score

            # Streak badges
            elif badge.category == "streak":
                required_streak = criteria.get("streak_days", 0)
                return progress.current_streak >= required_streak

            # Perfect score badges
            elif criteria.get("perfect_score"):
                if recent_result:
                    return recent_result.get("score", 0) >= 100

            # Category completion badges
            elif criteria.get("category_complete"):
                category = criteria.get("category")
                if category and progress.completed_scenarios:
                    # Get total scenarios in category
                    total_result = await db.execute(
                        select(func.count(TrainingScenario.id))
                        .where(TrainingScenario.category == category)
                    )
                    total = total_result.scalar()

                    # Count completed in category
                    completed = len([
                        s for s in progress.completed_scenarios
                        if s.startswith(f"scenario_{category}")
                    ])

                    return completed >= total

            # Average score badges
            elif criteria.get("min_average_score"):
                required_avg = criteria.get("min_average_score")
                return float(progress.average_score or 0) >= required_avg

            # Challenge completion badges
            elif criteria.get("challenge_scenarios"):
                required_challenges = criteria.get("challenge_scenarios")

                # Count completed challenge scenarios
                challenge_result = await db.execute(
                    select(func.count(ScenarioResult.id))
                    .join(TrainingScenario, ScenarioResult.scenario_id == TrainingScenario.id)
                    .where(
                        ScenarioResult.user_id == user_id,
                        TrainingScenario.difficulty == "challenge"
                    )
                )
                challenge_count = challenge_result.scalar()

                return challenge_count >= required_challenges

            # Time-based badges (fast completion)
            elif criteria.get("max_duration_minutes"):
                if recent_result:
                    max_duration = criteria.get("max_duration_minutes")
                    duration = recent_result.get("duration_minutes", 999)
                    return duration <= max_duration

            # Special badges (custom criteria)
            elif badge.category == "special":
                # Handle special badge logic
                return await self._check_special_badge(
                    db=db,
                    user_id=user_id,
                    badge=badge,
                    progress=progress
                )

            return False

        except Exception as e:
            logger.error(f"Error checking badge criteria for {badge.badge_id}: {e}")
            return False

    async def _check_special_badge(
        self,
        db: AsyncSession,
        user_id: UUID,
        badge: TrainingBadge,
        progress: UserTrainingProgress
    ) -> bool:
        """Check special badge criteria"""
        try:
            badge_id = badge.badge_id

            # First scenario completion
            if badge_id == "first_scenario":
                return progress.total_scenarios_completed >= 1

            # Early bird (complete scenario before 9am)
            elif badge_id == "early_bird":
                # Check recent session times
                recent_sessions = await db.execute(
                    select(TrainingSession)
                    .where(TrainingSession.user_id == user_id)
                    .order_by(TrainingSession.completed_at.desc())
                    .limit(10)
                )
                for session in recent_sessions.scalars():
                    if session.completed_at and session.completed_at.hour < 9:
                        return True

            # Night owl (complete scenario after 10pm)
            elif badge_id == "night_owl":
                recent_sessions = await db.execute(
                    select(TrainingSession)
                    .where(TrainingSession.user_id == user_id)
                    .order_by(TrainingSession.completed_at.desc())
                    .limit(10)
                )
                for session in recent_sessions.scalars():
                    if session.completed_at and session.completed_at.hour >= 22:
                        return True

            # Comeback kid (improve score by 20+ points)
            elif badge_id == "comeback_kid":
                # Get last two results for same scenario
                # (Complex query - simplified for now)
                return False  # Implement if needed

            # Perfectionist (3 perfect scores in a row)
            elif badge_id == "perfectionist":
                recent_results = await db.execute(
                    select(ScenarioResult)
                    .where(ScenarioResult.user_id == user_id)
                    .order_by(ScenarioResult.completed_at.desc())
                    .limit(3)
                )
                results = recent_results.scalars().all()

                if len(results) >= 3:
                    return all(r.score >= 100 for r in results)

            return False

        except Exception as e:
            logger.error(f"Error checking special badge: {e}")
            return False

    async def get_user_badges(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> List[Dict]:
        """
        Get all badges earned by user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of earned badges
        """
        try:
            result = await db.execute(
                select(UserBadge, TrainingBadge)
                .join(TrainingBadge, UserBadge.badge_id == TrainingBadge.id)
                .where(UserBadge.user_id == user_id)
                .order_by(UserBadge.earned_at.desc())
            )

            badges = []
            for user_badge, training_badge in result.all():
                badges.append({
                    "badge_id": training_badge.badge_id,
                    "name": training_badge.name,
                    "description": training_badge.description,
                    "category": training_badge.category,
                    "icon": training_badge.icon,
                    "rarity": training_badge.rarity,
                    "earned_at": user_badge.earned_at.isoformat()
                })

            return badges

        except Exception as e:
            logger.error(f"Error getting user badges: {e}")
            return []

    async def get_badge_progress(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict:
        """
        Get progress toward unearned badges

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with progress info for each badge
        """
        try:
            # Get user progress
            progress_result = await db.execute(
                select(UserTrainingProgress).where(
                    UserTrainingProgress.user_id == user_id
                )
            )
            progress = progress_result.scalar_one_or_none()

            if not progress:
                return {}

            # Get earned badges
            earned_result = await db.execute(
                select(UserBadge.badge_id).where(
                    UserBadge.user_id == user_id
                )
            )
            earned_badge_ids = [row[0] for row in earned_result.all()]

            # Get unearned badges
            badges_result = await db.execute(
                select(TrainingBadge).where(
                    TrainingBadge.id.notin_(earned_badge_ids) if earned_badge_ids else True
                )
            )
            unearned_badges = badges_result.scalars().all()

            badge_progress = {}

            for badge in unearned_badges:
                progress_info = await self._calculate_badge_progress(
                    db=db,
                    user_id=user_id,
                    badge=badge,
                    progress=progress
                )

                badge_progress[badge.badge_id] = {
                    "name": badge.name,
                    "description": badge.description,
                    "category": badge.category,
                    "progress": progress_info["progress"],
                    "target": progress_info["target"],
                    "percentage": progress_info["percentage"]
                }

            return badge_progress

        except Exception as e:
            logger.error(f"Error getting badge progress: {e}")
            return {}

    async def _calculate_badge_progress(
        self,
        db: AsyncSession,
        user_id: UUID,
        badge: TrainingBadge,
        progress: UserTrainingProgress
    ) -> Dict:
        """Calculate progress toward a specific badge"""
        try:
            criteria = badge.criteria

            # Scenario completion badges
            if "scenarios_completed" in criteria:
                target = criteria["scenarios_completed"]
                current = progress.total_scenarios_completed
                return {
                    "progress": current,
                    "target": target,
                    "percentage": min(100, int((current / target) * 100))
                }

            # Skill score badges
            elif "skill" in criteria and "min_score" in criteria:
                skill = criteria["skill"]
                target = criteria["min_score"]
                current = progress.skill_scores.get(skill, 0) if progress.skill_scores else 0
                return {
                    "progress": int(current),
                    "target": target,
                    "percentage": min(100, int((current / target) * 100))
                }

            # Streak badges
            elif "streak_days" in criteria:
                target = criteria["streak_days"]
                current = progress.current_streak
                return {
                    "progress": current,
                    "target": target,
                    "percentage": min(100, int((current / target) * 100))
                }

            # Default
            return {"progress": 0, "target": 1, "percentage": 0}

        except Exception as e:
            logger.error(f"Error calculating badge progress: {e}")
            return {"progress": 0, "target": 1, "percentage": 0}

    def get_badge_categories(self) -> Dict[str, str]:
        """Get all badge categories"""
        return self.categories


# Global instance
badge_system = BadgeSystem()
