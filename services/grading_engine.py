"""
Grading Engine
AI-powered evaluation of training scenario performance
"""

from typing import Dict, List, Optional
from uuid import UUID
import json

from services.ai_provider import ai_provider_manager
from loguru import logger


class GradingEngine:
    """
    Evaluate training scenario performance
    Uses AI to provide detailed, constructive feedback
    """

    def __init__(self):
        self.grading_categories = [
            "professionalism",
            "technical_accuracy",
            "communication",
            "problem_solving",
            "documentation"
        ]

        self.performance_tiers = {
            "excellent": {"min": 90, "description": "Outstanding performance"},
            "good": {"min": 75, "description": "Strong performance with minor areas for improvement"},
            "needs_improvement": {"min": 0, "description": "Significant room for growth"}
        }

    async def grade_scenario_completion(
        self,
        scenario: Dict,
        conversation: List[Dict],
        user_id: UUID
    ) -> Dict:
        """
        Grade a completed training scenario

        Args:
            scenario: Scenario dict with grading criteria
            conversation: List of messages (role, content)
            user_id: User ID for tracking

        Returns:
            Grading result dict
        """
        try:
            # Build grading prompt
            prompt = self._build_grading_prompt(scenario, conversation)

            # Get AI grading
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert training evaluator for roofing insurance representatives. Provide detailed, constructive, and fair assessments."
                },
                {"role": "user", "content": prompt}
            ]

            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="agnes",
                user_id=str(user_id)
            )

            # Parse grading result
            grading = self._parse_grading_response(response['content'])

            # Validate and enhance grading
            grading = self._validate_and_enhance_grading(grading, scenario, conversation)

            logger.info(f"Graded scenario {scenario['scenario_id']} for user {user_id}: {grading['overall_score']}")

            return grading

        except Exception as e:
            logger.error(f"Error grading scenario: {e}", exc_info=True)
            # Return fallback grading
            return self._fallback_grading(scenario)

    def _build_grading_prompt(self, scenario: Dict, conversation: List[Dict]) -> str:
        """Build detailed grading prompt"""

        # Format conversation
        conversation_text = "\n\n".join([
            f"{'REP' if msg['role'] == 'user' else 'SCENARIO'}: {msg['content']}"
            for msg in conversation
        ])

        prompt = f"""Grade this training scenario completion for a roofing insurance representative.

**SCENARIO INFORMATION:**
- **Title:** {scenario['title']}
- **Category:** {scenario['category']}
- **Difficulty:** {scenario['difficulty']}
- **Objective:** {scenario['objective']}

**SITUATION:**
{scenario['situation']}

**KEY CHALLENGES:**
{', '.join(scenario.get('key_challenges', []))}

**LEARNING OBJECTIVES:**
{', '.join(scenario.get('learning_objectives', []))}

**GRADING CRITERIA:**
{json.dumps(scenario.get('grading_criteria', {}), indent=2)}

**FULL CONVERSATION:**
{conversation_text}

---

**GRADING INSTRUCTIONS:**

Evaluate the rep's performance across these categories:
1. **Professionalism (0-100):** Tone, empathy, respect, courtesy
2. **Technical Accuracy (0-100):** Correct use of codes, guidelines, procedures, terminology
3. **Communication (0-100):** Clarity, active listening, explanation quality
4. **Problem Solving (0-100):** Handling objections, finding solutions, creative thinking
5. **Documentation (0-100):** Proper template usage, thoroughness, attention to detail

For each category, provide:
- Score (0-100)
- Specific examples from the conversation (quote what they said)
- What they did well
- What they could improve

Then provide:
- **Overall Score:** Weighted average (all categories equal weight)
- **Performance Tier:** "excellent" (90+), "good" (75-89), or "needs_improvement" (<75)
- **Key Strengths:** Top 3 things they did well
- **Areas for Improvement:** Top 3 things to work on
- **Key Moments:** 2-3 specific moments (good or bad) with feedback
- **Next Steps:** Specific recommendation for their next training

**IMPORTANT:**
- Be fair but honest
- Use specific examples from the conversation
- Be constructive - focus on growth
- Consider the difficulty level (be more lenient for beginner scenarios)
- Remember this is INSURANCE CLAIMS, not retail sales

**OUTPUT FORMAT (JSON):**
```json
{{
  "overall_score": <0-100>,
  "category_scores": {{
    "professionalism": <0-100>,
    "technical_accuracy": <0-100>,
    "communication": <0-100>,
    "problem_solving": <0-100>,
    "documentation": <0-100>
  }},
  "performance_tier": "<excellent|good|needs_improvement>",
  "strengths": [
    "Specific strength 1 with example",
    "Specific strength 2 with example",
    "Specific strength 3 with example"
  ],
  "areas_for_improvement": [
    "Specific area 1 with actionable advice",
    "Specific area 2 with actionable advice",
    "Specific area 3 with actionable advice"
  ],
  "key_moments": [
    {{
      "moment": "Quote or description of what happened",
      "feedback": "Why this was good/bad and what to learn"
    }}
  ],
  "next_steps": "Specific recommendation for next training scenario or skill to focus on"
}}
```

Provide ONLY the JSON output, no additional text.
"""

        return prompt

    def _parse_grading_response(self, response: str) -> Dict:
        """Parse AI grading response"""
        try:
            # Extract JSON from response
            content = response.strip()

            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            # Parse JSON
            grading = json.loads(content.strip())

            return grading

        except Exception as e:
            logger.error(f"Error parsing grading response: {e}")
            logger.debug(f"Response content: {response[:500]}")
            raise

    def _validate_and_enhance_grading(
        self,
        grading: Dict,
        scenario: Dict,
        conversation: List[Dict]
    ) -> Dict:
        """Validate grading structure and add enhancements"""
        try:
            # Ensure all required fields exist
            if "overall_score" not in grading:
                # Calculate from category scores if possible
                if "category_scores" in grading:
                    scores = grading["category_scores"].values()
                    grading["overall_score"] = sum(scores) / len(scores)
                else:
                    grading["overall_score"] = 75  # Default

            # Clamp overall score
            grading["overall_score"] = max(0, min(100, grading["overall_score"]))

            # Ensure category scores exist
            if "category_scores" not in grading:
                grading["category_scores"] = {cat: 75 for cat in self.grading_categories}

            # Clamp category scores
            for category in self.grading_categories:
                if category in grading["category_scores"]:
                    grading["category_scores"][category] = max(
                        0, min(100, grading["category_scores"][category])
                    )
                else:
                    grading["category_scores"][category] = 75

            # Determine performance tier if not set
            if "performance_tier" not in grading:
                score = grading["overall_score"]
                if score >= 90:
                    grading["performance_tier"] = "excellent"
                elif score >= 75:
                    grading["performance_tier"] = "good"
                else:
                    grading["performance_tier"] = "needs_improvement"

            # Ensure strengths and improvements exist
            if "strengths" not in grading or not grading["strengths"]:
                grading["strengths"] = ["Completed the scenario"]

            if "areas_for_improvement" not in grading or not grading["areas_for_improvement"]:
                grading["areas_for_improvement"] = ["Continue practicing to improve confidence"]

            # Ensure key moments exist
            if "key_moments" not in grading or not grading["key_moments"]:
                grading["key_moments"] = [
                    {
                        "moment": "Overall scenario completion",
                        "feedback": "Reviewed full conversation performance"
                    }
                ]

            # Add metadata
            grading["metadata"] = {
                "scenario_id": scenario["scenario_id"],
                "scenario_difficulty": scenario["difficulty"],
                "conversation_length": len(conversation),
                "graded_at": "auto"
            }

            return grading

        except Exception as e:
            logger.error(f"Error validating grading: {e}")
            return grading

    def _fallback_grading(self, scenario: Dict) -> Dict:
        """Fallback grading if AI grading fails"""
        return {
            "overall_score": 75,
            "category_scores": {
                "professionalism": 75,
                "technical_accuracy": 75,
                "communication": 75,
                "problem_solving": 75,
                "documentation": 75
            },
            "performance_tier": "good",
            "strengths": [
                "Completed the scenario",
                "Engaged with the training material",
                "Demonstrated willingness to learn"
            ],
            "areas_for_improvement": [
                "Continue practicing to build confidence",
                "Focus on specific technical details",
                "Work on communication clarity"
            ],
            "key_moments": [
                {
                    "moment": "Scenario completion",
                    "feedback": "Successfully completed the training scenario"
                }
            ],
            "next_steps": "Continue with similar difficulty scenarios to build confidence",
            "metadata": {
                "scenario_id": scenario.get("scenario_id"),
                "grading_method": "fallback",
                "note": "AI grading unavailable, default scores provided"
            }
        }

    def calculate_skill_improvements(
        self,
        current_scores: Dict[str, float],
        new_scores: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate skill improvement deltas

        Args:
            current_scores: Current skill scores
            new_scores: New scores from this scenario

        Returns:
            Dict of improvements by skill
        """
        improvements = {}

        for skill in self.grading_categories:
            current = current_scores.get(skill, 0)
            new = new_scores.get(skill, 0)
            improvements[skill] = new - current

        return improvements

    def get_performance_insights(self, grading: Dict) -> Dict:
        """
        Generate insights from grading results

        Args:
            grading: Grading result dict

        Returns:
            Insights dict
        """
        try:
            category_scores = grading.get("category_scores", {})

            # Find strongest and weakest areas
            if category_scores:
                strongest = max(category_scores, key=category_scores.get)
                weakest = min(category_scores, key=category_scores.get)
            else:
                strongest = "N/A"
                weakest = "N/A"

            # Calculate score distribution
            scores = list(category_scores.values())
            score_variance = max(scores) - min(scores) if scores else 0

            insights = {
                "strongest_skill": strongest,
                "strongest_score": category_scores.get(strongest, 0),
                "weakest_skill": weakest,
                "weakest_score": category_scores.get(weakest, 0),
                "score_variance": score_variance,
                "consistency": "high" if score_variance < 10 else "medium" if score_variance < 20 else "low",
                "overall_trend": self._determine_trend(grading.get("overall_score", 0))
            }

            return insights

        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return {}

    def _determine_trend(self, score: float) -> str:
        """Determine performance trend"""
        if score >= 90:
            return "excellent"
        elif score >= 80:
            return "strong"
        elif score >= 70:
            return "improving"
        else:
            return "developing"


# Global instance
grading_engine = GradingEngine()
