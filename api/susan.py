"""
Susan AI API
Insurance Claims Expert System
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from models import User, SusanConversation, SusanMessage
from models.database import get_db
from api.auth import get_current_user
from services.ai_provider import ai_provider_manager
from services.ai_router import intelligent_router
from loguru import logger

router = APIRouter()

# Pydantic models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    role: str = "assistant"
    provider: str
    model: str
    timestamp: datetime

class ConversationSummary(BaseModel):
    id: str
    title: str
    last_message_at: datetime
    message_count: int

# SUSAN AI SYSTEM PROMPT
SUSAN_SYSTEM_PROMPT = """You are Susan, an expert insurance claims specialist for roofing contractors working with Roof-ER.

Your expertise includes:
- Insurance policies and claims procedures for storm damage
- Building codes (IBC, IRC, FBC, NFPA) and requirements
- Manufacturer specifications and guidelines (GAF, Owens Corning, CertainTeed)
- Storm damage assessment (hail, wind, impact)
- Working with insurance adjusters professionally
- Documentation requirements (Photo Report Template, iTel, Repair Attempt Template)
- Escalation processes (Team Leader → Sales Manager → Arbitration)
- State-specific requirements (Maryland, Virginia, Florida)

Your role:
- Provide accurate, detailed insurance and technical information
- Cite specific codes, manufacturer guidelines, and policy requirements
- Guide reps through the claims process step-by-step
- Help with documentation and template usage
- Advise on adjuster negotiations professionally
- Support escalation decisions with clear reasoning

Your style:
- Professional yet friendly
- Educational without being condescending
- Specific and actionable
- Always cite sources (codes, manufacturer docs, templates)
- Support reps in achieving claim approvals

Remember: Reps are working with INSURANCE CLAIMS, not retail sales. The homeowner typically pays only the deductible; insurance covers the rest. Focus on proper documentation and working through the insurance process."""

# Routes
@router.post("/chat", response_model=ChatResponse)
async def chat_with_susan(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with Susan AI
    Creates or continues a conversation
    """

    try:
        # Get or create conversation
        if request.conversation_id:
            result = await db.execute(
                select(SusanConversation).where(
                    SusanConversation.id == request.conversation_id,
                    SusanConversation.user_id == current_user.id
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Create new conversation
            conversation = SusanConversation(
                user_id=current_user.id,
                title=request.message[:100]  # First message as title
            )
            db.add(conversation)
            await db.flush()

        # Save user message
        user_message = SusanMessage(
            conversation_id=conversation.id,
            role="user",
            content=request.message
        )
        db.add(user_message)

        # Get conversation history (last 20 messages)
        history_result = await db.execute(
            select(SusanMessage)
            .where(SusanMessage.conversation_id == conversation.id)
            .order_by(SusanMessage.created_at)
            .limit(settings.CONVERSATION_MAX_HISTORY)
        )
        history = history_result.scalars().all()

        # Build messages for AI
        messages = [{"role": "system", "content": SUSAN_SYSTEM_PROMPT}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": request.message})

        # Call AI provider
        logger.info(f"Susan processing message for user {current_user.email}")
        response = await ai_provider_manager.generate(
            messages=messages,
            ai_type="susan",
            user_id=str(current_user.id),
        )

        # Save assistant message
        assistant_message = SusanMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=response["content"],
            metadata={
                "provider": response["provider"],
                "model": response["model"],
                "cost": response["cost"],
                "response_time_ms": response["response_time_ms"]
            }
        )
        db.add(assistant_message)

        # Update conversation
        conversation.last_message_at = datetime.utcnow()
        conversation.message_count += 2

        await db.commit()
        await db.refresh(assistant_message)

        logger.info(f"Susan responded via {response['provider']} in {response['response_time_ms']}ms")

        return ChatResponse(
            conversation_id=str(conversation.id),
            message=response["content"],
            provider=response["provider"],
            model=response["model"],
            timestamp=assistant_message.created_at
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error in Susan chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get("/conversations", response_model=List[ConversationSummary])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50
):
    """Get user's Susan conversations"""

    result = await db.execute(
        select(SusanConversation)
        .where(
            SusanConversation.user_id == current_user.id,
            SusanConversation.archived == False
        )
        .order_by(desc(SusanConversation.last_message_at))
        .limit(limit)
    )
    conversations = result.scalars().all()

    return [
        ConversationSummary(
            id=str(conv.id),
            title=conv.title,
            last_message_at=conv.last_message_at,
            message_count=conv.message_count
        )
        for conv in conversations
    ]

@router.get("/conversations/{conversation_id}/messages", response_model=List[ChatMessage])
async def get_conversation_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all messages in a conversation"""

    # Verify conversation belongs to user
    conv_result = await db.execute(
        select(SusanConversation).where(
            SusanConversation.id == conversation_id,
            SusanConversation.user_id == current_user.id
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    result = await db.execute(
        select(SusanMessage)
        .where(SusanMessage.conversation_id == conversation_id)
        .order_by(SusanMessage.created_at)
    )
    messages = result.scalars().all()

    return [
        ChatMessage(role=msg.role, content=msg.content)
        for msg in messages
    ]

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete (archive) a conversation"""

    result = await db.execute(
        select(SusanConversation).where(
            SusanConversation.id == conversation_id,
            SusanConversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.archived = True
    await db.commit()

    return {"message": "Conversation archived"}

@router.post("/conversations/new")
async def new_conversation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation"""

    conversation = SusanConversation(
        user_id=current_user.id,
        title="New conversation"
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return {"conversation_id": str(conversation.id)}
