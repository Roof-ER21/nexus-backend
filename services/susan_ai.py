"""
Susan AI Service
Main orchestration layer for Susan's insurance expertise
Integrates RAG, email generation, document processing, weather verification
"""

from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime

from services.ai_provider import ai_provider_manager
from rag.rag_system import rag_system
from email.generator import email_generator
from documents.processor import document_processor
from documents.ocr import ocr_processor
from weather.noaa_api import noaa_weather_api
from loguru import logger


class SusanAIService:
    """
    Susan AI - Insurance Claims Expert
    Orchestrates all Susan-specific services
    """

    def __init__(self):
        self.system_prompt = """You are Susan, an expert insurance claims specialist for roofing contractors working with Roof-ER.

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

CRITICAL: Reps are working with INSURANCE CLAIMS, not retail sales. The homeowner typically pays only the deductible; insurance covers the rest. Focus on proper documentation and working through the insurance process."""

    async def enhanced_chat(
        self,
        db: AsyncSession,
        message: str,
        conversation_history: List[Dict],
        user_id: UUID,
        enable_rag: bool = True,
        enable_code_search: bool = True
    ) -> Dict:
        """
        Enhanced chat with RAG and knowledge base integration

        Args:
            db: Database session
            message: User message
            conversation_history: Previous messages
            user_id: User ID
            enable_rag: Use RAG for knowledge retrieval
            enable_code_search: Search building codes

        Returns:
            Dict with response and sources
        """
        try:
            sources = []
            context_text = ""

            # Build context using RAG if enabled
            if enable_rag:
                # Determine what to search based on message content
                include_codes = any(word in message.lower() for word in [
                    'code', 'ibc', 'irc', 'fbc', 'nfpa', 'requirement', 'standard'
                ])

                include_manufacturers = any(word in message.lower() for word in [
                    'gaf', 'owens', 'corning', 'certainteed', 'manufacturer', 'spec', 'guideline'
                ])

                include_insurance = any(word in message.lower() for word in [
                    'carrier', 'policy', 'coverage', 'insurance company'
                ])

                # Build comprehensive context
                context = await rag_system.build_context_for_query(
                    db=db,
                    query=message,
                    include_codes=include_codes and enable_code_search,
                    include_manufacturers=include_manufacturers,
                    include_insurance=include_insurance
                )

                # Format context for prompt
                if context['total_sources'] > 0:
                    context_text = rag_system.format_context_for_prompt(context)
                    sources = self._extract_sources_from_context(context)

            # Build messages for AI
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Add context if available
            if context_text:
                messages.append({
                    "role": "system",
                    "content": f"\n\n{context_text}\n\nUse this knowledge base to provide accurate, cited answers."
                })

            # Add conversation history
            for msg in conversation_history[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })

            # Add current message
            messages.append({
                "role": "user",
                "content": message
            })

            # Get AI response
            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="susan",
                user_id=str(user_id)
            )

            # Detect if user needs help with specific tasks
            suggestions = self._detect_task_suggestions(message, response['content'])

            logger.info(f"Susan enhanced chat completed with {len(sources)} sources")

            return {
                "content": response['content'],
                "sources": sources,
                "suggestions": suggestions,
                "provider": response['provider'],
                "model": response['model'],
                "cost": response['cost'],
                "context_used": len(sources) > 0
            }

        except Exception as e:
            logger.error(f"Error in enhanced chat: {e}", exc_info=True)
            raise

    def _extract_sources_from_context(self, context: Dict) -> List[Dict]:
        """Extract source citations from context"""
        sources = []

        # Knowledge base sources
        for entry in context.get('knowledge_base', [])[:3]:
            sources.append({
                "type": "knowledge_base",
                "title": entry['title'],
                "source": entry['source'],
                "similarity": entry['similarity']
            })

        # Building codes
        for code in context.get('building_codes', [])[:3]:
            sources.append({
                "type": "building_code",
                "code": f"{code['code_type']} {code['code_number']}",
                "title": code['title']
            })

        # Manufacturers
        for mfr in context.get('manufacturers', [])[:2]:
            sources.append({
                "type": "manufacturer",
                "manufacturer": mfr['name'],
                "product": mfr['product_line']
            })

        return sources

    def _detect_task_suggestions(self, user_message: str, ai_response: str) -> List[Dict]:
        """Detect if Susan should suggest specific tools/features"""
        suggestions = []
        message_lower = user_message.lower()

        # Email generation suggestion
        if any(word in message_lower for word in ['email', 'write', 'letter', 'correspondence', 'adjuster']):
            suggestions.append({
                "type": "email_generation",
                "title": "Generate Professional Email",
                "description": "I can help you generate a professional email to the adjuster with proper citations and formatting.",
                "action": "generate_email"
            })

        # Document analysis suggestion
        if any(word in message_lower for word in ['estimate', 'document', 'pdf', 'file', 'report']):
            suggestions.append({
                "type": "document_analysis",
                "title": "Analyze Document",
                "description": "Upload the document and I can extract key information, analyze estimates, and identify important details.",
                "action": "analyze_document"
            })

        # Weather verification suggestion
        if any(word in message_lower for word in ['storm', 'weather', 'hail', 'wind', 'date of loss']):
            suggestions.append({
                "type": "weather_verification",
                "title": "Verify Weather Event",
                "description": "I can verify the storm event using NOAA data to support your claim documentation.",
                "action": "verify_weather"
            })

        # Code citation suggestion
        if any(word in message_lower for word in ['code', 'requirement', 'standard', 'specification']):
            suggestions.append({
                "type": "code_citation",
                "title": "Get Code Citations",
                "description": "I can provide specific code citations with section numbers and requirements.",
                "action": "get_codes"
            })

        return suggestions[:3]  # Limit to 3 suggestions

    async def generate_claim_email(
        self,
        db: AsyncSession,
        user_id: UUID,
        template_name: str,
        claim_details: Dict
    ) -> Dict:
        """
        Generate professional claim email
        Wrapper around email generator with Susan's expertise

        Args:
            db: Database session
            user_id: User ID
            template_name: Email template name
            claim_details: Claim information

        Returns:
            Generated email dict
        """
        try:
            # Enrich claim details with Susan's insights
            enriched_details = await self._enrich_claim_details(db, claim_details)

            # Generate email
            email = await email_generator.generate_from_template(
                db=db,
                template_name=template_name,
                variables=enriched_details,
                user_id=user_id,
                customize_with_ai=True
            )

            logger.info(f"Generated claim email for user {user_id}")

            return email

        except Exception as e:
            logger.error(f"Error generating claim email: {e}")
            raise

    async def _enrich_claim_details(self, db: AsyncSession, details: Dict) -> Dict:
        """Add additional context to claim details using RAG"""
        try:
            enriched = details.copy()

            # Add relevant building codes if not present
            if not details.get('building_codes'):
                codes = await rag_system.search_building_codes(
                    db=db,
                    query=details.get('damage_type', 'roofing damage')
                )
                enriched['building_codes'] = codes[:3]

            # Add manufacturer requirements if product mentioned
            if details.get('manufacturer'):
                manufacturers = await rag_system.search_manufacturers(
                    db=db,
                    query=details.get('product_line', ''),
                    manufacturer_name=details['manufacturer']
                )
                enriched['manufacturer_requirements'] = manufacturers[:2]

            return enriched

        except Exception as e:
            logger.error(f"Error enriching claim details: {e}")
            return details

    async def analyze_uploaded_document(
        self,
        db: AsyncSession,
        file: bytes,
        filename: str,
        user_id: UUID,
        document_type: Optional[str] = None
    ) -> Dict:
        """
        Analyze uploaded document with Susan's expertise

        Args:
            db: Database session
            file: File bytes
            filename: Filename
            user_id: User ID
            document_type: Type hint

        Returns:
            Analysis results
        """
        try:
            import io

            # Process document
            file_obj = io.BytesIO(file)
            processed = await document_processor.process_document(
                db=db,
                file=file_obj,
                filename=filename,
                user_id=user_id,
                document_type=document_type
            )

            # If it's an estimate, do deeper analysis
            if document_type == 'estimate' or 'estimate' in filename.lower():
                estimate_analysis = await document_processor.analyze_estimate(
                    text=processed['text'],
                    structured_data=processed.get('structured_data')
                )
                processed['estimate_analysis'] = estimate_analysis

            # Get Susan's insights
            insights = await self._get_document_insights(
                db=db,
                text=processed['text'],
                document_type=document_type or 'unknown',
                user_id=user_id
            )

            processed['susan_insights'] = insights

            logger.info(f"Analyzed document {filename} for user {user_id}")

            return processed

        except Exception as e:
            logger.error(f"Error analyzing document: {e}")
            raise

    async def _get_document_insights(
        self,
        db: AsyncSession,
        text: str,
        document_type: str,
        user_id: UUID
    ) -> Dict:
        """Get Susan's AI insights on document"""
        try:
            prompt = f"""Analyze this {document_type} document and provide key insights for an insurance claim.

Document text:
{text[:2000]}...

Provide:
1. Key information identified (claims, dates, amounts, parties)
2. Potential issues or red flags
3. Missing information that should be included
4. Recommendations for strengthening the claim
5. Relevant codes or guidelines that apply

Be specific and actionable."""

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="susan",
                user_id=str(user_id)
            )

            return {
                "analysis": response['content'],
                "provider": response['provider']
            }

        except Exception as e:
            logger.error(f"Error getting document insights: {e}")
            return {"analysis": "Unable to analyze document at this time."}

    async def verify_storm_for_claim(
        self,
        db: AsyncSession,
        user_id: UUID,
        location: Dict,
        date: datetime,
        event_type: Optional[str] = None
    ) -> Dict:
        """
        Verify storm event and generate report for claim

        Args:
            db: Database session
            user_id: User ID
            location: Location dict
            date: Date of alleged event
            event_type: Type of event

        Returns:
            Verification report
        """
        try:
            # Verify with NOAA
            report = await noaa_weather_api.generate_weather_report(
                location=location,
                date=date,
                event_type=event_type
            )

            # Save if verified
            if report.get('verification', {}).get('verified'):
                best_match = report['verification'].get('best_match', {})
                await noaa_weather_api.save_weather_event(
                    db=db,
                    user_id=user_id,
                    event_data=best_match
                )

            # Get Susan's interpretation
            interpretation = await self._interpret_weather_verification(
                report=report,
                user_id=user_id
            )

            report['susan_interpretation'] = interpretation

            logger.info(f"Verified storm event for user {user_id}")

            return report

        except Exception as e:
            logger.error(f"Error verifying storm: {e}")
            raise

    async def _interpret_weather_verification(
        self,
        report: Dict,
        user_id: UUID
    ) -> str:
        """Get Susan's interpretation of weather verification"""
        try:
            prompt = f"""As Susan, interpret this weather verification report for the rep.

Report: {str(report)}

Provide:
1. Clear explanation of what was found
2. Strength of the verification (strong, moderate, weak)
3. How to use this in the claim
4. What additional documentation might help
5. Talking points for the adjuster

Be clear and actionable."""

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="susan",
                user_id=str(user_id)
            )

            return response['content']

        except Exception as e:
            logger.error(f"Error interpreting weather verification: {e}")
            return "Weather verification completed. Review the report for details."


# Global instance
susan_ai_service = SusanAIService()
