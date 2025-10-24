"""
Scenario Manager
Load, manage, and recommend training scenarios for Agnes
"""

from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from uuid import UUID
from datetime import datetime

from models import (
    TrainingScenario, ScenarioResult, UserTrainingProgress,
    ScenarioDifficulty, ScenarioCategory
)
from loguru import logger


class ScenarioManager:
    """
    Manage training scenarios
    Load from database, recommend next scenarios, track progress
    """

    def __init__(self):
        # Scenario categories for the 115 scenarios
        self.categories = {
            "initial_contact": "Initial Homeowner Contact (20 scenarios)",
            "adjuster_relations": "Adjuster Negotiations (30 scenarios)",
            "template_usage": "Roof-ER Template Usage (20 scenarios)",
            "code_citations": "Building Code Citations (15 scenarios)",
            "escalation": "Escalation Processes (20 scenarios)",
            "documentation": "Documentation Excellence (10 scenarios)"
        }

        # Difficulty progression
        self.difficulties = ["beginner", "intermediate", "expert", "challenge"]

    async def get_scenario_by_id(
        self,
        db: AsyncSession,
        scenario_id: str
    ) -> Optional[Dict]:
        """
        Get specific scenario by ID

        Args:
            db: Database session
            scenario_id: Scenario ID (e.g., "scenario_1_1")

        Returns:
            Scenario dict or None
        """
        try:
            result = await db.execute(
                select(TrainingScenario).where(
                    TrainingScenario.scenario_id == scenario_id
                )
            )
            scenario = result.scalar_one_or_none()

            if not scenario:
                return None

            return self._scenario_to_dict(scenario)

        except Exception as e:
            logger.error(f"Error getting scenario {scenario_id}: {e}")
            return None

    async def get_scenarios_by_category(
        self,
        db: AsyncSession,
        category: str,
        difficulty: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get scenarios by category

        Args:
            db: Database session
            category: Category name
            difficulty: Optional difficulty filter
            limit: Max results

        Returns:
            List of scenario dicts
        """
        try:
            query = select(TrainingScenario).where(
                TrainingScenario.category == category
            )

            if difficulty:
                query = query.where(TrainingScenario.difficulty == difficulty)

            query = query.order_by(TrainingScenario.scenario_id).limit(limit)

            result = await db.execute(query)
            scenarios = result.scalars().all()

            return [self._scenario_to_dict(s) for s in scenarios]

        except Exception as e:
            logger.error(f"Error getting scenarios by category: {e}")
            return []

    async def recommend_next_scenario(
        self,
        db: AsyncSession,
        user_id: UUID,
        category: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Recommend next scenario based on user's progress

        Args:
            db: Database session
            user_id: User ID
            category: Optional category preference

        Returns:
            Recommended scenario or None
        """
        try:
            # Get user progress
            progress_result = await db.execute(
                select(UserTrainingProgress).where(
                    UserTrainingProgress.user_id == user_id
                )
            )
            progress = progress_result.scalar_one_or_none()

            completed_scenarios = progress.completed_scenarios if progress else []
            skill_scores = progress.skill_scores if progress else {}
            avg_score = float(progress.average_score) if progress and progress.average_score else 0

            # Determine appropriate difficulty
            difficulty = self._determine_difficulty(avg_score, len(completed_scenarios))

            # Build query for uncompleted scenarios
            query = select(TrainingScenario)

            # Filter out completed
            if completed_scenarios:
                query = query.where(
                    TrainingScenario.scenario_id.notin_(completed_scenarios)
                )

            # Filter by difficulty
            query = query.where(TrainingScenario.difficulty == difficulty)

            # Filter by category if specified
            if category:
                query = query.where(TrainingScenario.category == category)
            else:
                # Recommend based on weakest skill
                weakest_category = self._get_weakest_category(skill_scores)
                if weakest_category:
                    query = query.where(TrainingScenario.category == weakest_category)

            # Get random scenario
            query = query.order_by(func.random()).limit(1)

            result = await db.execute(query)
            scenario = result.scalar_one_or_none()

            if scenario:
                logger.info(f"Recommended scenario {scenario.scenario_id} for user {user_id}")
                return self._scenario_to_dict(scenario)

            # If no scenario found at this difficulty, try easier
            if difficulty != "beginner":
                logger.info(f"No {difficulty} scenarios available, trying easier")
                return await self.recommend_next_scenario(
                    db=db,
                    user_id=user_id,
                    category=category
                )

            return None

        except Exception as e:
            logger.error(f"Error recommending scenario: {e}")
            return None

    def _determine_difficulty(self, avg_score: float, completed_count: int) -> str:
        """
        Determine appropriate difficulty based on performance

        Args:
            avg_score: User's average score
            completed_count: Number of scenarios completed

        Returns:
            Difficulty level
        """
        # New users start with beginner
        if completed_count < 3:
            return "beginner"

        # Progression based on average score and count
        if completed_count < 10:
            return "beginner" if avg_score < 70 else "intermediate"

        if completed_count < 25:
            if avg_score < 60:
                return "beginner"
            elif avg_score < 75:
                return "intermediate"
            else:
                return "expert"

        # Experienced users
        if avg_score < 65:
            return "intermediate"
        elif avg_score < 80:
            return "expert"
        else:
            return "challenge"

    def _get_weakest_category(self, skill_scores: Dict) -> Optional[str]:
        """Get category with lowest skill score"""
        if not skill_scores:
            return None

        # Map skills to categories
        skill_to_category = {
            "professionalism": "initial_contact",
            "technical_accuracy": "code_citations",
            "communication": "adjuster_relations",
            "problem_solving": "escalation",
            "documentation": "documentation"
        }

        # Find weakest skill
        weakest_skill = min(skill_scores, key=skill_scores.get)

        return skill_to_category.get(weakest_skill)

    async def get_category_progress(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict[str, Dict]:
        """
        Get user's progress by category

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict mapping category to progress info
        """
        try:
            # Get all scenarios by category
            result = await db.execute(
                select(
                    TrainingScenario.category,
                    func.count(TrainingScenario.id).label('total')
                ).group_by(TrainingScenario.category)
            )
            category_totals = {row.category: row.total for row in result.all()}

            # Get user's completed scenarios
            progress_result = await db.execute(
                select(UserTrainingProgress).where(
                    UserTrainingProgress.user_id == user_id
                )
            )
            progress = progress_result.scalar_one_or_none()

            if not progress:
                return {
                    cat: {"completed": 0, "total": total, "percentage": 0}
                    for cat, total in category_totals.items()
                }

            # Get completed scenarios by category
            completed_by_category = {}

            if progress.completed_scenarios:
                for scenario_id in progress.completed_scenarios:
                    # Get scenario category
                    scenario_result = await db.execute(
                        select(TrainingScenario.category).where(
                            TrainingScenario.scenario_id == scenario_id
                        )
                    )
                    category = scenario_result.scalar_one_or_none()

                    if category:
                        completed_by_category[category] = completed_by_category.get(category, 0) + 1

            # Build progress dict
            progress_dict = {}
            for category, total in category_totals.items():
                completed = completed_by_category.get(category, 0)
                progress_dict[category] = {
                    "completed": completed,
                    "total": total,
                    "percentage": int((completed / total) * 100) if total > 0 else 0
                }

            return progress_dict

        except Exception as e:
            logger.error(f"Error getting category progress: {e}")
            return {}

    async def get_learning_path(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> List[Dict]:
        """
        Generate recommended learning path for user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of recommended scenarios in order
        """
        try:
            # Get user progress
            progress_result = await db.execute(
                select(UserTrainingProgress).where(
                    UserTrainingProgress.user_id == user_id
                )
            )
            progress = progress_result.scalar_one_or_none()

            completed_scenarios = progress.completed_scenarios if progress else []
            completed_count = len(completed_scenarios)

            learning_path = []

            # Beginner path (first 10 scenarios)
            if completed_count < 10:
                # Start with initial contact
                scenarios = await self.get_scenarios_by_category(
                    db=db,
                    category="initial_contact",
                    difficulty="beginner",
                    limit=5
                )
                learning_path.extend([s for s in scenarios if s['scenario_id'] not in completed_scenarios][:3])

                # Add some template usage
                scenarios = await self.get_scenarios_by_category(
                    db=db,
                    category="template_usage",
                    difficulty="beginner",
                    limit=5
                )
                learning_path.extend([s for s in scenarios if s['scenario_id'] not in completed_scenarios][:2])

            # Intermediate path (10-30 scenarios)
            elif completed_count < 30:
                # Focus on adjuster relations and codes
                for category in ["adjuster_relations", "code_citations"]:
                    scenarios = await self.get_scenarios_by_category(
                        db=db,
                        category=category,
                        difficulty="intermediate",
                        limit=5
                    )
                    learning_path.extend([s for s in scenarios if s['scenario_id'] not in completed_scenarios][:3])

            # Advanced path
            else:
                # Work on escalation and challenges
                for category in ["escalation", "documentation"]:
                    scenarios = await self.get_scenarios_by_category(
                        db=db,
                        category=category,
                        limit=5
                    )
                    learning_path.extend([s for s in scenarios if s['scenario_id'] not in completed_scenarios][:2])

                # Add challenge scenarios
                query = select(TrainingScenario).where(
                    and_(
                        TrainingScenario.difficulty == "challenge",
                        TrainingScenario.scenario_id.notin_(completed_scenarios)
                    )
                ).limit(3)

                result = await db.execute(query)
                challenges = result.scalars().all()
                learning_path.extend([self._scenario_to_dict(s) for s in challenges])

            logger.info(f"Generated learning path with {len(learning_path)} scenarios for user {user_id}")

            return learning_path[:10]  # Return next 10 recommendations

        except Exception as e:
            logger.error(f"Error generating learning path: {e}")
            return []

    def _scenario_to_dict(self, scenario: TrainingScenario) -> Dict:
        """Convert scenario model to dict"""
        return {
            "id": str(scenario.id),
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "category": scenario.category,
            "difficulty": scenario.difficulty,
            "situation": scenario.situation,
            "objective": scenario.objective,
            "homeowner_profile": scenario.homeowner_profile,
            "adjuster_profile": scenario.adjuster_profile,
            "key_challenges": scenario.key_challenges,
            "learning_objectives": scenario.learning_objectives,
            "grading_criteria": scenario.grading_criteria,
            "templates_referenced": scenario.templates_referenced,
            "codes_referenced": scenario.codes_referenced,
            "estimated_duration_minutes": scenario.estimated_duration_minutes
        }

    async def get_scenario_statistics(
        self,
        db: AsyncSession,
        scenario_id: str
    ) -> Dict:
        """
        Get statistics for a specific scenario

        Args:
            db: Database session
            scenario_id: Scenario ID

        Returns:
            Statistics dict
        """
        try:
            # Get scenario
            scenario_result = await db.execute(
                select(TrainingScenario).where(
                    TrainingScenario.scenario_id == scenario_id
                )
            )
            scenario = scenario_result.scalar_one_or_none()

            if not scenario:
                return {}

            # Get all results for this scenario
            results_query = await db.execute(
                select(ScenarioResult).where(
                    ScenarioResult.scenario_id == scenario.id
                )
            )
            results = results_query.scalars().all()

            if not results:
                return {
                    "scenario_id": scenario_id,
                    "attempts": 0,
                    "avg_score": 0,
                    "completion_rate": 0
                }

            # Calculate statistics
            scores = [r.score for r in results]
            durations = [r.duration_minutes for r in results if r.duration_minutes]

            stats = {
                "scenario_id": scenario_id,
                "attempts": len(results),
                "avg_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "avg_duration_minutes": sum(durations) / len(durations) if durations else None,
                "completion_rate": 100  # All in results table are completed
            }

            logger.debug(f"Statistics for {scenario_id}: {stats['attempts']} attempts, avg {stats['avg_score']:.1f}")

            return stats

        except Exception as e:
            logger.error(f"Error getting scenario statistics: {e}")
            return {}


# Global instance
scenario_manager = ScenarioManager()
