"""
AI Provider Manager
Multi-provider system with automatic failover (Groq → Together → OpenRouter)
Cost tracking and performance monitoring
"""

import os
import time
import asyncio
from typing import List, Dict, Optional, Tuple
from loguru import logger
from groq import Groq
from together import Together
from openai import OpenAI

from config import settings
from models import AIRequest
from models.database import AsyncSessionLocal

class AIProviderManager:
    """
    Manages multiple AI providers with intelligent failover
    Tracks costs, performance, and automatically switches on failures
    """

    def __init__(self):
        self.providers = [
            {
                "name": "groq",
                "client": Groq(api_key=settings.GROQ_API_KEY),
                "models": {
                    "susan": settings.GROQ_MODEL_SUSAN,
                    "agnes": settings.GROQ_MODEL_AGNES,
                },
                "cost_per_1k_tokens": 0.00059,  # $0.59 per 1M tokens
                "priority": 1,
                "max_tokens": 8192,
                "supports_streaming": True,
            },
            {
                "name": "together",
                "client": Together(api_key=settings.TOGETHER_API_KEY),
                "models": {
                    "susan": settings.TOGETHER_MODEL_SUSAN,
                    "agnes": settings.TOGETHER_MODEL_AGNES,
                },
                "cost_per_1k_tokens": 0.0009,  # $0.90 per 1M tokens
                "priority": 2,
                "max_tokens": 8192,
                "supports_streaming": True,
            },
            {
                "name": "openrouter",
                "client": OpenAI(
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1"
                ),
                "models": {
                    "susan": settings.OPENROUTER_MODEL,
                    "agnes": settings.OPENROUTER_MODEL,
                },
                "cost_per_1k_tokens": 0.001,  # $1.00 per 1M tokens (varies by model)
                "priority": 3,
                "max_tokens": 4096,
                "supports_streaming": True,
            }
        ]

        # Performance tracking
        self.provider_stats = {p["name"]: {"successes": 0, "failures": 0, "total_cost": 0.0} for p in self.providers}

        logger.info(f"✅ AI Provider Manager initialized with {len(self.providers)} providers")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        ai_type: str,  # 'susan' or 'agnes'
        user_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict:
        """
        Generate AI response with automatic failover

        Args:
            messages: List of chat messages [{"role": "user", "content": "..."}]
            ai_type: 'susan' or 'agnes'
            user_id: User ID for logging
            temperature: Temperature override (default from settings)
            max_tokens: Max tokens override (default from settings)
            stream: Enable streaming response

        Returns:
            Dict with 'content', 'provider', 'model', 'usage', 'cost'
        """
        temperature = temperature or settings.AI_TEMPERATURE
        max_tokens = max_tokens or settings.AI_MAX_TOKENS

        errors = []

        # Try providers in priority order
        for provider in sorted(self.providers, key=lambda x: x["priority"]):
            try:
                start_time = time.time()

                # Get model for this AI type
                model = provider["models"].get(ai_type)
                if not model:
                    logger.warning(f"No model configured for {ai_type} on {provider['name']}")
                    continue

                logger.debug(f"Attempting {provider['name']} with model {model}")

                # Make API call
                response_data = await self._call_provider(
                    provider=provider,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=min(max_tokens, provider["max_tokens"]),
                    stream=stream,
                )

                elapsed_ms = int((time.time() - start_time) * 1000)

                # Calculate cost
                total_tokens = response_data["usage"]["total_tokens"]
                cost = self._calculate_cost(total_tokens, provider["cost_per_1k_tokens"])

                # Update stats
                self.provider_stats[provider["name"]]["successes"] += 1
                self.provider_stats[provider["name"]]["total_cost"] += cost

                # Log request
                await self._log_request(
                    user_id=user_id,
                    ai_type=ai_type,
                    provider=provider["name"],
                    model=model,
                    usage=response_data["usage"],
                    cost=cost,
                    response_time_ms=elapsed_ms,
                    success=True,
                )

                logger.info(f"✅ {provider['name']} succeeded in {elapsed_ms}ms (cost: ${cost:.6f})")

                return {
                    "content": response_data["content"],
                    "provider": provider["name"],
                    "model": model,
                    "usage": response_data["usage"],
                    "cost": cost,
                    "response_time_ms": elapsed_ms,
                }

            except Exception as e:
                error_msg = str(e)
                errors.append({
                    "provider": provider["name"],
                    "error": error_msg
                })

                # Update stats
                self.provider_stats[provider["name"]]["failures"] += 1

                # Log failed request
                await self._log_request(
                    user_id=user_id,
                    ai_type=ai_type,
                    provider=provider["name"],
                    model=provider["models"].get(ai_type, "unknown"),
                    success=False,
                    error_message=error_msg,
                )

                logger.warning(f"❌ {provider['name']} failed: {error_msg}")

                # Continue to next provider
                continue

        # All providers failed
        error_summary = "; ".join([f"{e['provider']}: {e['error']}" for e in errors])
        logger.error(f"🚨 ALL AI PROVIDERS FAILED: {error_summary}")
        raise Exception(f"All AI providers failed: {error_summary}")

    async def _call_provider(
        self,
        provider: Dict,
        model: str,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        stream: bool = False,
    ) -> Dict:
        """
        Call specific provider's API

        Returns:
            Dict with 'content' and 'usage' keys
        """

        if provider["name"] == "groq":
            response = await asyncio.to_thread(
                provider["client"].chat.completions.create,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

        elif provider["name"] == "together":
            response = await asyncio.to_thread(
                provider["client"].chat.completions.create,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

        elif provider["name"] == "openrouter":
            response = await asyncio.to_thread(
                provider["client"].chat.completions.create,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                extra_headers={
                    "HTTP-Referer": settings.FRONTEND_URL,
                    "X-Title": "NEXUS",
                }
            )

        else:
            raise ValueError(f"Unknown provider: {provider['name']}")

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        }

    def _calculate_cost(self, total_tokens: int, cost_per_1k: float) -> float:
        """Calculate cost for token usage"""
        return (total_tokens / 1000) * cost_per_1k

    async def _log_request(
        self,
        user_id: Optional[str],
        ai_type: str,
        provider: str,
        model: str,
        usage: Optional[Dict] = None,
        cost: Optional[float] = None,
        response_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Log AI request to database"""
        try:
            async with AsyncSessionLocal() as session:
                log_entry = AIRequest(
                    user_id=user_id,
                    ai_type=ai_type,
                    provider=provider,
                    model=model,
                    prompt_tokens=usage.get("prompt_tokens") if usage else None,
                    completion_tokens=usage.get("completion_tokens") if usage else None,
                    total_tokens=usage.get("total_tokens") if usage else None,
                    cost_usd=cost,
                    response_time_ms=response_time_ms,
                    success=success,
                    error_message=error_message,
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log AI request: {e}")

    def get_stats(self) -> Dict:
        """Get provider performance statistics"""
        return {
            "providers": self.provider_stats,
            "total_successes": sum(p["successes"] for p in self.provider_stats.values()),
            "total_failures": sum(p["failures"] for p in self.provider_stats.values()),
            "total_cost": sum(p["total_cost"] for p in self.provider_stats.values()),
        }

# Global instance
ai_provider_manager = AIProviderManager()
