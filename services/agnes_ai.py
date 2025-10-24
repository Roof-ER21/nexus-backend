"""
Agnes AI Service
Main orchestration layer for Agnes training system
Integrates scenarios, grading, badges, progress tracking
"""

from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime

from services.ai_provider import ai_provider_manager
from services.scenario_manager import scenario_manager
from services.grading_engine import grading_engine
from services.badge_system import badge_system
from models import TrainingScenario
from loguru import logger


class AgnesAIService:
    """
    Agnes AI - Training Partner
    Orchestrates roleplay scenarios, grading, and progress tracking
    """

    def __init__(self):
        self.system_prompt = """You are Agnes, an expert training partner for roofing insurance sales reps working with Roof-ER.

Your role: Conduct interactive roleplay scenarios where reps practice real-world situations.

Scenario Types:
1. **Homeowner Interactions** - Play the homeowner, respond realistically
2. **Adjuster Negotiations** - Play the insurance adjuster, challenge the rep
3. **Template Usage** - Guide reps through Photo Report, iTel, Repair Attempt templates
4. **Code Citations** - Quiz and guide on IBC, IRC, FBC, NFPA, manufacturer guidelines
5. **Escalation Scenarios** - Practice involving Team Leaders, Sales Managers
6. **Documentation Excellence** - Review and improve documentation practices

Your behavior in scenarios:
- **Stay in character** - Be the homeowner or adjuster as described
- **Be realistic** - Show emotions, concerns, objections that real people have
- **Progressive difficulty** - Start cooperative, add challenges as scenario progresses
- **Educational moments** - When rep handles something well or poorly, briefly note it
- **Natural conversation** - Don't be a quiz bot, be a real person

Grading focus:
- **Professionalism** - Tone, empathy, respect
- **Technical accuracy** - Correct codes, guidelines, procedures
- **Template usage** - Proper documentation and forms
- **Problem-solving** - How they handle objections and challenges
- **Communication** - Clarity, confidence, listening

Remember: This is TRAINING. Be challenging but fair. Help them grow.

CRITICAL: This is for INSURANCE CLAIMS, not retail sales. Homeowners typically pay only the deductible; insurance covers the rest."""

    async def get_scenario_recommendation(
        self,
        db: AsyncSession,
        user_id: UUID,
        category: Optional[str] = None
    ) -> Dict:
        """
        Get recommended next scenario for user

        Args:
            db: Database session
            user_id: User ID
            category: Optional category preference

        Returns:
            Recommended scenario with context
        """
        try:
            # Get recommendation from scenario manager
            scenario = await scenario_manager.recommend_next_scenario(
                db=db,
                user_id=user_id,
                category=category
            )

            if not scenario:
                return {
                    "found": False,
                    "message": "No more scenarios available at your level. Great job completing your training!"
                }

            # Get user's category progress
            category_progress = await scenario_manager.get_category_progress(
                db=db,
                user_id=user_id
            )

            # Add context
            result = {
                "found": True,
                "scenario": scenario,
                "context": {
                    "category_progress": category_progress.get(scenario["category"], {}),
                    "recommendation_reason": self._get_recommendation_reason(scenario, category_progress)
                }
            }

            logger.info(f"Recommended scenario {scenario['scenario_id']} to user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error getting scenario recommendation: {e}")
            return {"found": False, "error": str(e)}

    def _get_recommendation_reason(self, scenario: Dict, category_progress: Dict) -> str:
        """Generate reason for recommendation"""
        category = scenario["category"]
        difficulty = scenario["difficulty"]

        progress = category_progress.get(category, {})
        percentage = progress.get("percentage", 0)

        if percentage < 30:
            return f"This {difficulty} scenario will help you build foundational skills in {category}."
        elif percentage < 70:
            return f"Continue developing your {category} skills with this {difficulty} challenge."
        else:
            return f"You're excelling in {category}! This {difficulty} scenario will help you master it."

    async def get_learning_path(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict:
        """
        Get personalized learning path

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Learning path with recommended scenarios
        """
        try:
            path = await scenario_manager.get_learning_path(
                db=db,
                user_id=user_id
            )

            # Group by category
            by_category = {}
            for scenario in path:
                category = scenario["category"]
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(scenario)

            return {
                "total_recommendations": len(path),
                "by_category": by_category,
                "next_5": path[:5]
            }

        except Exception as e:
            logger.error(f"Error getting learning path: {e}")
            return {"error": str(e)}

    async def start_scenario_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        scenario_id: str
    ) -> Dict:
        """
        Start new training scenario session

        Args:
            db: Database session
            user_id: User ID
            scenario_id: Scenario ID to start

        Returns:
            Session start info with initial message
        """
        try:
            # Get scenario
            scenario = await scenario_manager.get_scenario_by_id(
                db=db,
                scenario_id=scenario_id
            )

            if not scenario:
                raise ValueError(f"Scenario not found: {scenario_id}")

            # Build initial context for AI
            context = self._build_scenario_context(scenario)

            # Get Agnes to start the scenario
            messages = [
                {"role": "system", "content": self.system_prompt + f"\n\nCurrent scenario:\n{context}"},
                {"role": "user", "content": "[SCENARIO_START] Begin the roleplay. Set the scene and start the interaction naturally."}
            ]

            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="agnes",
                user_id=str(user_id)
            )

            logger.info(f"Started scenario {scenario_id} for user {user_id}")

            return {
                "scenario": scenario,
                "initial_message": response["content"],
                "provider": response["provider"],
                "tips": self._get_scenario_tips(scenario)
            }

        except Exception as e:
            logger.error(f"Error starting scenario: {e}")
            raise

    def _build_scenario_context(self, scenario: Dict) -> str:
        """Build context string for AI"""
        parts = [
            f"**Scenario:** {scenario['title']}",
            f"**Category:** {scenario['category']}",
            f"**Difficulty:** {scenario['difficulty']}",
            f"\n**Situation:** {scenario['situation']}",
            f"\n**Objective:** {scenario['objective']}"
        ]

        if scenario.get("homeowner_profile"):
            parts.append(f"\n**Homeowner Profile:** {scenario['homeowner_profile']}")

        if scenario.get("adjuster_profile"):
            parts.append(f"\n**Adjuster Profile:** {scenario['adjuster_profile']}")

        if scenario.get("key_challenges"):
            parts.append(f"\n**Key Challenges:** {', '.join(scenario['key_challenges'])}")

        return "\n".join(parts)

    def _get_scenario_tips(self, scenario: Dict) -> List[str]:
        """Get helpful tips for scenario"""
        tips = []

        category = scenario["category"]
        difficulty = scenario["difficulty"]

        # Category-specific tips
        if category == "initial_contact":
            tips.append("Focus on building rapport and trust early")
            tips.append("Listen carefully to homeowner's concerns")
        elif category == "adjuster_relations":
            tips.append("Stay professional even if adjuster is challenging")
            tips.append("Use specific code references to support your position")
        elif category == "template_usage":
            tips.append("Follow the template structure carefully")
            tips.append("Be thorough in documentation")
        elif category == "code_citations":
            tips.append("Cite specific code sections with numbers")
            tips.append("Explain why the code applies to this situation")
        elif category == "escalation":
            tips.append("Know when to escalate vs handle yourself")
            tips.append("Document everything before escalating")

        # Difficulty-specific tips
        if difficulty == "beginner":
            tips.append("Take your time - this is a learning exercise")
        elif difficulty in ["expert", "challenge"]:
            tips.append("This scenario will challenge you - stay focused")

        return tips[:3]  # Return top 3

    async def process_scenario_message(
        self,
        db: AsyncSession,
        user_id: UUID,
        scenario: Dict,
        conversation_history: List[Dict],
        user_message: str
    ) -> Dict:
        """
        Process user message in scenario roleplay

        Args:
            db: Database session
            user_id: User ID
            scenario: Scenario dict
            conversation_history: Previous messages
            user_message: New user message

        Returns:
            Agnes response
        """
        try:
            # Build context
            context = self._build_scenario_context(scenario)

            # Build messages for AI
            messages = [
                {"role": "system", "content": self.system_prompt + f"\n\nCurrent scenario:\n{context}"}
            ]

            # Add conversation history
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            # Add current message
            messages.append({
                "role": "user",
                "content": user_message
            })

            # Get Agnes response
            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="agnes",
                user_id=str(user_id)
            )

            # Detect if scenario should end
            should_end = self._detect_scenario_completion(
                conversation_history=conversation_history,
                new_message=user_message
            )

            return {
                "response": response["content"],
                "provider": response["provider"],
                "should_end": should_end,
                "message_count": len(conversation_history) + 1
            }

        except Exception as e:
            logger.error(f"Error processing scenario message: {e}")
            raise

    def _detect_scenario_completion(
        self,
        conversation_history: List[Dict],
        new_message: str
    ) -> bool:
        """Detect if scenario should naturally end"""
        message_count = len(conversation_history)

        # End after reasonable conversation length
        if message_count >= 20:
            return True

        # Check for completion keywords
        completion_keywords = [
            "thank you for your help",
            "i'll proceed with",
            "sounds good",
            "perfect, i understand",
            "that makes sense"
        ]

        message_lower = new_message.lower()
        if any(keyword in message_lower for keyword in completion_keywords):
            if message_count >= 8:  # At least 8 messages exchanged
                return True

        return False

    async def complete_and_grade_scenario(
        self,
        db: AsyncSession,
        user_id: UUID,
        scenario: Dict,
        conversation: List[Dict]
    ) -> Dict:
        """
        Complete scenario and provide grading

        Args:
            db: Database session
            user_id: User ID
            scenario: Scenario dict
            conversation: Full conversation

        Returns:
            Grading results with badges
        """
        try:
            # Get grading from engine
            grading = await grading_engine.grade_scenario_completion(
                scenario=scenario,
                conversation=conversation,
                user_id=user_id
            )

            # Check and award badges
            badges_awarded = await badge_system.check_and_award_badges(
                db=db,
                user_id=user_id,
                recent_result=grading
            )

            # Get performance insights
            insights = grading_engine.get_performance_insights(grading)

            # Get next recommendation
            next_scenario = await scenario_manager.recommend_next_scenario(
                db=db,
                user_id=user_id
            )

            result = {
                "grading": grading,
                "badges_awarded": badges_awarded,
                "insights": insights,
                "next_recommendation": next_scenario
            }

            logger.info(f"Completed and graded scenario {scenario['scenario_id']} for user {user_id}: {grading['overall_score']}")

            return result

        except Exception as e:
            logger.error(f"Error completing scenario: {e}")
            raise

    async def get_user_dashboard(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict:
        """
        Get comprehensive user training dashboard

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dashboard data
        """
        try:
            # Get progress
            from models import UserTrainingProgress
            progress_result = await db.execute(
                select(UserTrainingProgress).where(
                    UserTrainingProgress.user_id == user_id
                )
            )
            progress = progress_result.scalar_one_or_none()

            # Get badges
            user_badges = await badge_system.get_user_badges(
                db=db,
                user_id=user_id
            )

            # Get badge progress
            badge_progress = await badge_system.get_badge_progress(
                db=db,
                user_id=user_id
            )

            # Get category progress
            category_progress = await scenario_manager.get_category_progress(
                db=db,
                user_id=user_id
            )

            # Get next recommendation
            next_scenario = await scenario_manager.recommend_next_scenario(
                db=db,
                user_id=user_id
            )

            dashboard = {
                "overview": {
                    "total_completed": progress.total_scenarios_completed if progress else 0,
                    "average_score": float(progress.average_score) if progress and progress.average_score else 0,
                    "current_streak": progress.current_streak if progress else 0,
                    "badges_earned": len(user_badges)
                },
                "skill_scores": progress.skill_scores if progress and progress.skill_scores else {},
                "category_progress": category_progress,
                "badges": user_badges[:10],  # Most recent 10
                "badge_progress": badge_progress,
                "next_recommendation": next_scenario
            }

            return dashboard

        except Exception as e:
            logger.error(f"Error getting dashboard: {e}")
            return {"error": str(e)}


# Global instance
agnes_ai_service = AgnesAIService()

# Load scenarios function (called at startup)
async def load_training_scenarios(db: Optional[AsyncSession] = None) -> int:
    """
    Load training scenarios from database
    Called during application startup

    Args:
        db: Optional database session

    Returns:
        Number of scenarios loaded
    """
    try:
        if not db:
            from models.database import get_db
            from sqlalchemy import func
            async for session in get_db():
                db = session
                break

        # Count existing scenarios
        from sqlalchemy import func
        result = await db.execute(select(func.count(TrainingScenario.id)))
        count = result.scalar()

        logger.info(f"Training scenarios available: {count}")

        return count

    except Exception as e:
        logger.error(f"Error loading training scenarios: {e}")
        return 0
