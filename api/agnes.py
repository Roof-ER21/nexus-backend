"""
Agnes AI Training API
Interactive roleplay training system for roofing insurance reps
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, date
from uuid import UUID
import json

from models import (
    User, TrainingScenario, TrainingSession, TrainingMessage,
    ScenarioResult, UserTrainingProgress, TrainingBadge, UserBadge,
    DailyChallenge, ChallengeCompletion, Leaderboard,
    ScenarioDifficulty, ScenarioCategory, PerformanceTier
)
from models.database import get_db
from api.auth import get_current_user
from services.ai_provider import ai_provider_manager
from loguru import logger

router = APIRouter()

# Pydantic models
class ScenarioFilter(BaseModel):
    category: Optional[str] = None
    difficulty: Optional[str] = None
    limit: int = 50

class ScenarioListItem(BaseModel):
    id: str
    scenario_id: str
    title: str
    category: str
    difficulty: str
    estimated_duration_minutes: int
    is_completed: bool
    best_score: Optional[float]

class StartScenarioRequest(BaseModel):
    scenario_id: str

class StartScenarioResponse(BaseModel):
    session_id: str
    scenario: Dict
    initial_message: str

class MessageRequest(BaseModel):
    message: str

class MessageResponse(BaseModel):
    response: str
    feedback: Optional[str]
    current_score: Optional[float]
    timestamp: datetime

class CompleteScenarioRequest(BaseModel):
    pass  # No body needed

class CompleteScenarioResponse(BaseModel):
    final_score: float
    performance_tier: str
    feedback: Dict
    badges_earned: List[Dict]
    next_recommendation: Optional[str]

class ProgressResponse(BaseModel):
    total_scenarios: int
    completed_scenarios: int
    average_score: float
    skill_scores: Dict
    current_streak: int
    badges: List[Dict]
    recent_completions: List[Dict]

class LeaderboardEntry(BaseModel):
    rank: int
    user_name: str
    score: float
    scenarios_completed: int
    badges_count: int

class LeaderboardResponse(BaseModel):
    period: str
    entries: List[LeaderboardEntry]
    user_rank: Optional[int]

class DailyChallengeResponse(BaseModel):
    challenge_id: str
    scenario: Dict
    bonus_points: int
    expires_at: datetime
    is_completed: bool

# AGNES AI SYSTEM PROMPT
AGNES_SYSTEM_PROMPT = """You are Agnes, an expert training partner for roofing insurance sales reps working with Roof-ER.

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

Current scenario context will be provided in each message."""

# Routes
@router.get("/scenarios", response_model=List[ScenarioListItem])
async def list_scenarios(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List available training scenarios
    Filter by category, difficulty
    Shows completion status and best scores
    """

    # Build query
    query = select(TrainingScenario)

    if category:
        query = query.where(TrainingScenario.category == category)
    if difficulty:
        query = query.where(TrainingScenario.difficulty == difficulty)

    query = query.order_by(TrainingScenario.scenario_id).limit(limit)

    result = await db.execute(query)
    scenarios = result.scalars().all()

    # Get user's completion data
    progress_result = await db.execute(
        select(UserTrainingProgress).where(
            UserTrainingProgress.user_id == current_user.id
        )
    )
    progress = progress_result.scalar_one_or_none()
    completed_scenarios = progress.completed_scenarios if progress else []

    # Get best scores
    results_query = await db.execute(
        select(ScenarioResult).where(
            ScenarioResult.user_id == current_user.id
        )
    )
    results = results_query.scalars().all()
    best_scores = {r.scenario_id: r.score for r in results}

    return [
        ScenarioListItem(
            id=str(scenario.id),
            scenario_id=scenario.scenario_id,
            title=scenario.title,
            category=scenario.category,
            difficulty=scenario.difficulty,
            estimated_duration_minutes=scenario.estimated_duration_minutes,
            is_completed=scenario.scenario_id in completed_scenarios,
            best_score=best_scores.get(scenario.id)
        )
        for scenario in scenarios
    ]

@router.post("/scenarios/start", response_model=StartScenarioResponse)
async def start_scenario(
    request: StartScenarioRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new training scenario
    Creates session and returns initial context
    """

    # Find scenario
    result = await db.execute(
        select(TrainingScenario).where(
            TrainingScenario.scenario_id == request.scenario_id
        )
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Create training session
    session = TrainingSession(
        user_id=current_user.id,
        scenario_id=scenario.id
    )
    db.add(session)
    await db.flush()

    # Build initial context message
    context = {
        "scenario_id": scenario.scenario_id,
        "title": scenario.title,
        "category": scenario.category,
        "difficulty": scenario.difficulty,
        "situation": scenario.situation,
        "homeowner_profile": scenario.homeowner_profile,
        "adjuster_profile": scenario.adjuster_profile,
        "objective": scenario.objective,
        "key_challenges": scenario.key_challenges,
        "templates_referenced": scenario.templates_referenced,
        "codes_referenced": scenario.codes_referenced,
    }

    # Create initial AI message to set the scene
    initial_prompt = f"""You are starting a training scenario.

**Scenario:** {scenario.title}
**Situation:** {scenario.situation}
**Your objective:** {scenario.objective}

"""

    if scenario.homeowner_profile:
        initial_prompt += f"**Homeowner Profile:** {json.dumps(scenario.homeowner_profile, indent=2)}\n\n"

    if scenario.adjuster_profile:
        initial_prompt += f"**Adjuster Profile:** {json.dumps(scenario.adjuster_profile, indent=2)}\n\n"

    initial_prompt += f"**Key Challenges:** {', '.join(scenario.key_challenges)}\n\n"
    initial_prompt += "Begin the scenario with your first response. Stay in character!"

    # Get Agnes to start the scenario
    messages = [
        {"role": "system", "content": AGNES_SYSTEM_PROMPT + f"\n\nCurrent scenario: {json.dumps(context)}"},
        {"role": "user", "content": "[SCENARIO START]"}
    ]

    response = await ai_provider_manager.generate(
        messages=messages,
        ai_type="agnes",
        user_id=str(current_user.id)
    )

    # Save initial message
    agnes_message = TrainingMessage(
        session_id=session.id,
        role="assistant",
        content=response["content"],
        metadata={
            "provider": response["provider"],
            "model": response["model"],
            "type": "scenario_start"
        }
    )
    db.add(agnes_message)

    await db.commit()
    await db.refresh(session)

    logger.info(f"User {current_user.email} started scenario {scenario.scenario_id}")

    return StartScenarioResponse(
        session_id=str(session.id),
        scenario=context,
        initial_message=response["content"]
    )

@router.post("/sessions/{session_id}/message", response_model=MessageResponse)
async def send_message(
    session_id: UUID,
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send message in active training session
    Agnes responds in character with real-time feedback
    """

    # Get session
    result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == session_id,
            TrainingSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Training session not found")

    if session.completed:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Get scenario
    scenario_result = await db.execute(
        select(TrainingScenario).where(TrainingScenario.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one()

    # Save user message
    user_message = TrainingMessage(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_message)

    # Get conversation history
    history_result = await db.execute(
        select(TrainingMessage)
        .where(TrainingMessage.session_id == session_id)
        .order_by(TrainingMessage.created_at)
    )
    history = history_result.scalars().all()

    # Build context for Agnes
    context = {
        "scenario_id": scenario.scenario_id,
        "title": scenario.title,
        "category": scenario.category,
        "situation": scenario.situation,
        "homeowner_profile": scenario.homeowner_profile,
        "adjuster_profile": scenario.adjuster_profile,
        "objective": scenario.objective,
        "grading_criteria": scenario.grading_criteria,
        "templates_referenced": scenario.templates_referenced,
        "codes_referenced": scenario.codes_referenced,
    }

    # Build messages for AI
    messages = [
        {"role": "system", "content": AGNES_SYSTEM_PROMPT + f"\n\nCurrent scenario: {json.dumps(context)}"}
    ]

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    # Get Agnes response
    response = await ai_provider_manager.generate(
        messages=messages,
        ai_type="agnes",
        user_id=str(current_user.id)
    )

    # Save Agnes response
    agnes_message = TrainingMessage(
        session_id=session.id,
        role="assistant",
        content=response["content"],
        metadata={
            "provider": response["provider"],
            "model": response["model"],
            "cost": response["cost"]
        }
    )
    db.add(agnes_message)

    # Update session
    session.message_count += 2
    session.last_activity = datetime.utcnow()

    await db.commit()
    await db.refresh(agnes_message)

    return MessageResponse(
        response=response["content"],
        feedback=None,  # Real-time feedback can be added later
        current_score=None,  # Progressive scoring can be added later
        timestamp=agnes_message.created_at
    )

@router.post("/sessions/{session_id}/complete", response_model=CompleteScenarioResponse)
async def complete_scenario(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete training scenario
    Get final grading, feedback, and badge awards
    """

    # Get session
    result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == session_id,
            TrainingSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Training session not found")

    if session.completed:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Get scenario
    scenario_result = await db.execute(
        select(TrainingScenario).where(TrainingScenario.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one()

    # Get all messages for grading
    history_result = await db.execute(
        select(TrainingMessage)
        .where(TrainingMessage.session_id == session_id)
        .order_by(TrainingMessage.created_at)
    )
    messages = history_result.scalars().all()

    # Build grading prompt
    conversation_text = "\n\n".join([
        f"{'Rep' if msg.role == 'user' else 'Character'}: {msg.content}"
        for msg in messages
    ])

    grading_prompt = f"""Grade this training scenario completion.

**Scenario:** {scenario.title}
**Objective:** {scenario.objective}
**Grading Criteria:** {json.dumps(scenario.grading_criteria, indent=2)}

**Conversation:**
{conversation_text}

Provide a detailed grading in this exact JSON format:
{{
    "overall_score": <0-100>,
    "category_scores": {{
        "professionalism": <0-100>,
        "technical_accuracy": <0-100>,
        "communication": <0-100>,
        "problem_solving": <0-100>,
        "documentation": <0-100>
    }},
    "strengths": ["strength 1", "strength 2", ...],
    "areas_for_improvement": ["area 1", "area 2", ...],
    "key_moments": [
        {{"moment": "description", "feedback": "what was good/bad"}},
        ...
    ],
    "performance_tier": "<excellent|good|needs_improvement>",
    "next_steps": "Recommendation for next training"
}}
"""

    # Get grading from AI
    grading_messages = [
        {"role": "system", "content": "You are an expert training evaluator for roofing insurance reps. Provide detailed, constructive feedback."},
        {"role": "user", "content": grading_prompt}
    ]

    grading_response = await ai_provider_manager.generate(
        messages=grading_messages,
        ai_type="agnes",
        user_id=str(current_user.id)
    )

    # Parse grading (AI should return JSON)
    try:
        # Extract JSON from response (in case AI adds explanation text)
        content = grading_response["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        grading = json.loads(content.strip())
    except Exception as e:
        logger.error(f"Failed to parse grading JSON: {e}")
        # Fallback grading
        grading = {
            "overall_score": 75,
            "category_scores": {
                "professionalism": 75,
                "technical_accuracy": 75,
                "communication": 75,
                "problem_solving": 75,
                "documentation": 75
            },
            "strengths": ["Completed the scenario"],
            "areas_for_improvement": ["Continue practicing"],
            "key_moments": [],
            "performance_tier": "good",
            "next_steps": "Try a more challenging scenario"
        }

    # Save result
    result_record = ScenarioResult(
        user_id=current_user.id,
        scenario_id=scenario.id,
        session_id=session.id,
        score=grading["overall_score"],
        performance_tier=grading["performance_tier"],
        category_scores=grading["category_scores"],
        feedback=grading,
        duration_minutes=int((datetime.utcnow() - session.started_at).total_seconds() / 60)
    )
    db.add(result_record)

    # Update session
    session.completed = True
    session.completed_at = datetime.utcnow()
    session.final_score = grading["overall_score"]

    # Update user progress
    progress_result = await db.execute(
        select(UserTrainingProgress).where(
            UserTrainingProgress.user_id == current_user.id
        )
    )
    progress = progress_result.scalar_one_or_none()

    if not progress:
        progress = UserTrainingProgress(user_id=current_user.id)
        db.add(progress)
        await db.flush()

    # Update progress
    progress.total_scenarios_completed += 1

    # Update average score
    if progress.average_score:
        progress.average_score = (
            (progress.average_score * (progress.total_scenarios_completed - 1) + grading["overall_score"])
            / progress.total_scenarios_completed
        )
    else:
        progress.average_score = grading["overall_score"]

    # Update skill scores
    if not progress.skill_scores:
        progress.skill_scores = {}

    for skill, score in grading["category_scores"].items():
        if skill in progress.skill_scores:
            # Average with existing
            progress.skill_scores[skill] = (progress.skill_scores[skill] + score) / 2
        else:
            progress.skill_scores[skill] = score

    # Update completed scenarios list
    if not progress.completed_scenarios:
        progress.completed_scenarios = []

    if scenario.scenario_id not in progress.completed_scenarios:
        progress.completed_scenarios.append(scenario.scenario_id)

    # Check for badge awards (simplified - full logic would be in badge_system.py)
    badges_earned = []

    # Example: First scenario completion badge
    if progress.total_scenarios_completed == 1:
        badge_result = await db.execute(
            select(TrainingBadge).where(TrainingBadge.badge_id == "first_scenario")
        )
        badge = badge_result.scalar_one_or_none()

        if badge:
            user_badge = UserBadge(
                user_id=current_user.id,
                badge_id=badge.id
            )
            db.add(user_badge)
            badges_earned.append({
                "badge_id": badge.badge_id,
                "name": badge.name,
                "description": badge.description
            })

    # Update leaderboard
    today = date.today()
    leaderboard_result = await db.execute(
        select(Leaderboard).where(
            and_(
                Leaderboard.user_id == current_user.id,
                Leaderboard.period_start == today
            )
        )
    )
    leaderboard = leaderboard_result.scalar_one_or_none()

    if not leaderboard:
        leaderboard = Leaderboard(
            user_id=current_user.id,
            period_type="daily",
            period_start=today,
            period_end=today
        )
        db.add(leaderboard)
        await db.flush()

    leaderboard.total_score += grading["overall_score"]
    leaderboard.scenarios_completed += 1
    leaderboard.average_score = leaderboard.total_score / leaderboard.scenarios_completed

    await db.commit()

    logger.info(f"User {current_user.email} completed scenario {scenario.scenario_id} with score {grading['overall_score']}")

    return CompleteScenarioResponse(
        final_score=grading["overall_score"],
        performance_tier=grading["performance_tier"],
        feedback=grading,
        badges_earned=badges_earned,
        next_recommendation=grading.get("next_steps")
    )

@router.get("/progress", response_model=ProgressResponse)
async def get_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's training progress and achievements"""

    # Get progress
    result = await db.execute(
        select(UserTrainingProgress).where(
            UserTrainingProgress.user_id == current_user.id
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        return ProgressResponse(
            total_scenarios=0,
            completed_scenarios=0,
            average_score=0.0,
            skill_scores={},
            current_streak=0,
            badges=[],
            recent_completions=[]
        )

    # Get badges
    badges_result = await db.execute(
        select(UserBadge, TrainingBadge)
        .join(TrainingBadge, UserBadge.badge_id == TrainingBadge.id)
        .where(UserBadge.user_id == current_user.id)
        .order_by(desc(UserBadge.earned_at))
    )
    badges = [
        {
            "badge_id": badge.badge_id,
            "name": badge.name,
            "description": badge.description,
            "category": badge.category,
            "earned_at": user_badge.earned_at.isoformat()
        }
        for user_badge, badge in badges_result.all()
    ]

    # Get recent completions
    recent_result = await db.execute(
        select(ScenarioResult, TrainingScenario)
        .join(TrainingScenario, ScenarioResult.scenario_id == TrainingScenario.id)
        .where(ScenarioResult.user_id == current_user.id)
        .order_by(desc(ScenarioResult.completed_at))
        .limit(10)
    )
    recent = [
        {
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "score": result.score,
            "performance_tier": result.performance_tier,
            "completed_at": result.completed_at.isoformat()
        }
        for result, scenario in recent_result.all()
    ]

    # Get total scenarios available
    total_result = await db.execute(select(func.count(TrainingScenario.id)))
    total_scenarios = total_result.scalar()

    return ProgressResponse(
        total_scenarios=total_scenarios,
        completed_scenarios=progress.total_scenarios_completed,
        average_score=float(progress.average_score) if progress.average_score else 0.0,
        skill_scores=progress.skill_scores or {},
        current_streak=progress.current_streak,
        badges=badges,
        recent_completions=recent
    )

@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    period: str = "daily",  # daily, weekly, monthly, all_time
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get leaderboard for specified period"""

    # Get leaderboard entries
    query = select(Leaderboard, User).join(User, Leaderboard.user_id == User.id)

    if period != "all_time":
        query = query.where(Leaderboard.period_type == period)

    query = query.order_by(desc(Leaderboard.total_score)).limit(limit)

    result = await db.execute(query)
    entries_data = result.all()

    # Build leaderboard
    entries = []
    user_rank = None

    for idx, (leaderboard, user) in enumerate(entries_data, 1):
        entries.append(LeaderboardEntry(
            rank=idx,
            user_name=user.full_name,
            score=float(leaderboard.total_score),
            scenarios_completed=leaderboard.scenarios_completed,
            badges_count=leaderboard.badges_earned
        ))

        if user.id == current_user.id:
            user_rank = idx

    return LeaderboardResponse(
        period=period,
        entries=entries,
        user_rank=user_rank
    )

@router.get("/daily-challenge", response_model=DailyChallengeResponse)
async def get_daily_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get today's daily challenge"""

    today = date.today()

    # Find today's challenge
    result = await db.execute(
        select(DailyChallenge, TrainingScenario)
        .join(TrainingScenario, DailyChallenge.scenario_id == TrainingScenario.id)
        .where(DailyChallenge.challenge_date == today)
    )
    challenge_data = result.first()

    if not challenge_data:
        raise HTTPException(status_code=404, detail="No daily challenge available")

    challenge, scenario = challenge_data

    # Check if user completed it
    completion_result = await db.execute(
        select(ChallengeCompletion).where(
            and_(
                ChallengeCompletion.challenge_id == challenge.id,
                ChallengeCompletion.user_id == current_user.id
            )
        )
    )
    completion = completion_result.scalar_one_or_none()

    return DailyChallengeResponse(
        challenge_id=str(challenge.id),
        scenario={
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "category": scenario.category,
            "difficulty": scenario.difficulty,
            "description": scenario.situation
        },
        bonus_points=challenge.bonus_points,
        expires_at=datetime.combine(today, datetime.max.time()),
        is_completed=completion is not None
    )

@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all scenario categories with counts"""

    result = await db.execute(
        select(
            TrainingScenario.category,
            func.count(TrainingScenario.id).label('count')
        )
        .group_by(TrainingScenario.category)
    )

    categories = [
        {"category": row.category, "count": row.count}
        for row in result.all()
    ]

    return {"categories": categories}
