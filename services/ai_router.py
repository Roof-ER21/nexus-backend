"""
Intelligent AI Router
Decides whether to route queries to Susan (Insurance Expert) or Agnes (Training Partner)
Based on intent analysis, keywords, and context
"""

import re
from typing import Tuple, Dict, Optional
from loguru import logger

class IntelligentRouter:
    """
    Routes user queries to the appropriate AI system
    Susan: Insurance expertise, technical questions, real-world assistance
    Agnes: Training, roleplay, practice scenarios, learning
    """

    # Training-related keywords (route to Agnes)
    TRAINING_KEYWORDS = {
        'practice': 1.0,
        'roleplay': 1.0,
        'training': 1.0,
        'scenario': 0.9,
        'teach me': 0.9,
        'learn': 0.8,
        'how to handle': 0.9,
        'what should i say': 0.9,
        'how do i respond': 0.9,
        'objection': 0.7,
        'script': 0.7,
        'agnes': 1.0,
        'train': 0.8,
        'rehearse': 0.9,
        'prepare for': 0.8,
    }

    # Insurance/Technical keywords (route to Susan)
    SUSAN_KEYWORDS = {
        'building code': 1.0,
        'manufacturer': 0.9,
        'insurance': 0.9,
        'claim': 0.9,
        'adjuster': 0.9,
        'policy': 0.8,
        'coverage': 0.8,
        'GAF': 1.0,
        'Owens Corning': 1.0,
        'CertainTeed': 1.0,
        'IBC': 1.0,
        'IRC': 1.0,
        'NFPA': 1.0,
        'wind': 0.6,
        'hail': 0.6,
        'storm': 0.6,
        'damage': 0.7,
        'susan': 1.0,
        'flashing': 0.8,
        'underlayment': 0.8,
        'shingles': 0.7,
        'roof': 0.6,
        'photo report': 0.9,
        'iTel': 0.9,
        'template': 0.7,
        'documentation': 0.7,
        'estimate': 0.7,
        'complaint': 0.8,
        'arbitration': 0.8,
    }

    # Question patterns that indicate need for expertise (Susan)
    TECHNICAL_QUESTION_PATTERNS = [
        r'what (is|are) the (code|requirement|guideline)',
        r'how (do|does) (insurance|claim|policy)',
        r'(can|should|must) (i|we|they)',
        r'what (does|is) (GAF|Owens Corning|IBC|IRC)',
        r'(wind speed|hail size|storm)',
    ]

    # Question patterns that indicate training need (Agnes)
    TRAINING_QUESTION_PATTERNS = [
        r'how (do i|should i) (handle|respond|deal with)',
        r'what (should|would|could) i say',
        r'(practice|roleplay|train|rehearse)',
        r'(help me|teach me|show me) (how to|to)',
    ]

    def route(
        self,
        message: str,
        context: Optional[Dict] = None
    ) -> Tuple[str, str, float]:
        """
        Route message to appropriate AI system

        Args:
            message: User's message
            context: Additional context (active_scenario, conversation_history, etc.)

        Returns:
            Tuple of (ai_name, reason, confidence)
            - ai_name: 'susan' or 'agnes'
            - reason: Explanation of routing decision
            - confidence: 0.0-1.0 confidence score
        """

        context = context or {}
        message_lower = message.lower()

        # 1. Explicit mentions (highest priority)
        if 'susan' in message_lower and 'agnes' not in message_lower:
            return ('susan', 'Explicit mention of Susan', 1.0)

        if 'agnes' in message_lower and 'susan' not in message_lower:
            return ('agnes', 'Explicit mention of Agnes', 1.0)

        # 2. Active training scenario (high priority)
        if context.get('active_training_scenario'):
            return ('agnes', 'Active training scenario in progress', 1.0)

        # 3. Conversation context
        if context.get('last_ai') == 'agnes':
            agnes_streak = context.get('agnes_message_count', 0)
            if agnes_streak >= 3:
                # User is in deep training session, keep with Agnes
                return ('agnes', f'Training session continuity ({agnes_streak} messages)', 0.9)

        if context.get('last_ai') == 'susan':
            susan_streak = context.get('susan_message_count', 0)
            if susan_streak >= 3:
                # User is consulting Susan on technical matters
                return ('susan', f'Technical consultation continuity ({susan_streak} messages)', 0.9)

        # 4. Calculate intent scores from keywords
        training_score = self._calculate_keyword_score(message_lower, self.TRAINING_KEYWORDS)
        technical_score = self._calculate_keyword_score(message_lower, self.SUSAN_KEYWORDS)

        # 5. Pattern matching
        training_pattern_match = self._check_patterns(message_lower, self.TRAINING_QUESTION_PATTERNS)
        technical_pattern_match = self._check_patterns(message_lower, self.TECHNICAL_QUESTION_PATTERNS)

        if training_pattern_match:
            training_score += 0.5
        if technical_pattern_match:
            technical_score += 0.5

        # 6. Context-based adjustments
        if context.get('recent_scenario_completion'):
            # User just finished a scenario, might want feedback (Agnes)
            training_score += 0.3

        if context.get('recent_claim_discussion'):
            # User was discussing actual claim (Susan)
            technical_score += 0.3

        # 7. Make decision
        logger.debug(f"Routing scores - Training: {training_score:.2f}, Technical: {technical_score:.2f}")

        if training_score > technical_score:
            confidence = min(training_score / (training_score + technical_score + 0.1), 1.0)
            return ('agnes', f'Training intent detected (score: {training_score:.2f})', confidence)
        elif technical_score > training_score:
            confidence = min(technical_score / (training_score + technical_score + 0.1), 1.0)
            return ('susan', f'Technical/insurance intent detected (score: {technical_score:.2f})', confidence)
        else:
            # Tie or both low - default to Susan for general assistance
            return ('susan', 'Default routing (no strong signal)', 0.5)

    def _calculate_keyword_score(self, message: str, keywords: Dict[str, float]) -> float:
        """Calculate score based on keyword matches"""
        score = 0.0
        for keyword, weight in keywords.items():
            if keyword in message:
                score += weight
        return score

    def _check_patterns(self, message: str, patterns: list) -> bool:
        """Check if message matches any regex patterns"""
        for pattern in patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False

    def suggest_handoff(
        self,
        current_ai: str,
        message: str,
        conversation_length: int
    ) -> Optional[Dict]:
        """
        Suggest if conversation should be handed off to the other AI

        Args:
            current_ai: Current AI handling the conversation
            message: Latest user message
            conversation_length: Number of messages in conversation

        Returns:
            Dict with handoff suggestion or None
        """

        # Don't suggest handoff too early
        if conversation_length < 3:
            return None

        optimal_ai, reason, confidence = self.route(message)

        # If optimal AI is different and confidence is high
        if optimal_ai != current_ai and confidence >= 0.8:
            return {
                "suggested_ai": optimal_ai,
                "reason": reason,
                "confidence": confidence,
                "message": self._generate_handoff_message(current_ai, optimal_ai)
            }

        return None

    def _generate_handoff_message(self, from_ai: str, to_ai: str) -> str:
        """Generate friendly handoff message"""
        if from_ai == "susan" and to_ai == "agnes":
            return "It sounds like you'd like to practice this! Let me connect you with Agnes for some roleplay training. She's great at this!"

        if from_ai == "agnes" and to_ai == "susan":
            return "Great practice! For the actual technical details and insurance specifics, let me hand you over to Susan. She's the expert on real-world claims!"

        return f"Let me connect you with {to_ai.title()} for this."

# Global router instance
intelligent_router = IntelligentRouter()
