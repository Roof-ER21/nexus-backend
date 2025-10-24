"""
Email Generation System
AI-powered professional email generation for insurance claims
"""

from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from uuid import UUID

from models import EmailTemplate, GeneratedEmail, User
from email.templates import email_template_engine
from services.ai_provider import ai_provider_manager
from loguru import logger


class EmailGenerator:
    """
    Generate professional emails for insurance claims
    Combines templates with AI for customization
    """

    async def generate_from_template(
        self,
        db: AsyncSession,
        template_name: str,
        variables: Dict,
        user_id: UUID,
        customize_with_ai: bool = True
    ) -> Dict:
        """
        Generate email from template with optional AI customization

        Args:
            db: Database session
            template_name: Name of template to use
            variables: Variables to substitute
            user_id: User generating the email
            customize_with_ai: Use AI to enhance/customize

        Returns:
            Dict with subject, body, and metadata
        """
        try:
            # Get template
            template_result = await db.execute(
                select(EmailTemplate).where(
                    EmailTemplate.template_name == template_name
                )
            )
            template = template_result.scalar_one_or_none()

            if not template:
                # Use default template
                default_templates = email_template_engine.get_default_templates()
                if template_name not in default_templates:
                    raise ValueError(f"Template not found: {template_name}")

                template_content = default_templates[template_name]
            else:
                template_content = template.template_content

            # Render template with variables
            rendered = email_template_engine.render_template(
                template_string=template_content,
                variables=variables
            )

            # Split subject and body
            lines = rendered.split('\n', 1)
            subject = lines[0].replace('Subject:', '').strip()
            body = lines[1].strip() if len(lines) > 1 else ""

            # Optionally customize with AI
            if customize_with_ai:
                customized = await self._customize_with_ai(
                    subject=subject,
                    body=body,
                    context=variables,
                    user_id=user_id
                )
                subject = customized['subject']
                body = customized['body']

            # Save generated email
            generated = GeneratedEmail(
                user_id=user_id,
                template_name=template_name,
                subject=subject,
                body=body,
                variables=variables,
                recipient=variables.get('adjuster_email') or variables.get('recipient_email'),
                status="draft"
            )

            db.add(generated)
            await db.flush()

            logger.info(f"Generated email from template '{template_name}' for user {user_id}")

            return {
                "email_id": str(generated.id),
                "subject": subject,
                "body": body,
                "variables": variables,
                "template_name": template_name
            }

        except Exception as e:
            logger.error(f"Error generating email: {e}", exc_info=True)
            raise

    async def _customize_with_ai(
        self,
        subject: str,
        body: str,
        context: Dict,
        user_id: UUID
    ) -> Dict:
        """
        Use AI to customize and improve email
        Maintains professional tone and adds context-specific details

        Args:
            subject: Email subject
            body: Email body
            context: Context variables
            user_id: User ID for tracking

        Returns:
            Dict with improved subject and body
        """
        try:
            prompt = f"""You are an expert at writing professional insurance claim correspondence.

Review and improve this email while maintaining its core message and professional tone.

**Current Email:**
Subject: {subject}

{body}

**Context:**
{str(context)}

**Instructions:**
1. Maintain the professional, respectful tone
2. Keep all factual information and citations
3. Improve clarity and flow if needed
4. Add any relevant details from context
5. Ensure proper formatting
6. Keep it concise but complete

Return ONLY the improved email in this exact format:
SUBJECT: [improved subject line]

BODY:
[improved body]
"""

            messages = [
                {"role": "system", "content": "You are a professional insurance correspondence specialist."},
                {"role": "user", "content": prompt}
            ]

            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="susan",
                user_id=str(user_id)
            )

            # Parse response
            content = response['content']

            # Extract subject
            if 'SUBJECT:' in content:
                subject_part = content.split('SUBJECT:')[1].split('BODY:')[0].strip()
            else:
                subject_part = subject

            # Extract body
            if 'BODY:' in content:
                body_part = content.split('BODY:')[1].strip()
            else:
                body_part = body

            logger.info("AI customization applied to email")

            return {
                "subject": subject_part,
                "body": body_part
            }

        except Exception as e:
            logger.error(f"Error customizing email with AI: {e}")
            # Return original on error
            return {"subject": subject, "body": body}

    async def generate_custom_email(
        self,
        db: AsyncSession,
        user_id: UUID,
        purpose: str,
        key_points: List[str],
        recipient_info: Dict,
        claim_info: Optional[Dict] = None,
        tone: str = "professional"
    ) -> Dict:
        """
        Generate completely custom email using AI
        No template - built from scratch based on requirements

        Args:
            db: Database session
            user_id: User generating email
            purpose: Purpose of email (e.g., "request supplemental", "respond to denial")
            key_points: Key points to include
            recipient_info: Info about recipient (name, role, etc.)
            claim_info: Claim details
            tone: Desired tone (professional, formal, friendly-professional)

        Returns:
            Dict with generated email
        """
        try:
            # Get user info
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one()

            # Build prompt
            prompt = f"""Generate a professional insurance claim email with the following requirements:

**Purpose:** {purpose}

**Key Points to Include:**
{chr(10).join(f'- {point}' for point in key_points)}

**Recipient Information:**
{str(recipient_info)}

**Claim Information:**
{str(claim_info) if claim_info else 'N/A'}

**Tone:** {tone}

**Sender Information:**
- Name: {user.full_name}
- Company: Roof-ER
- Role: Roofing Insurance Specialist

**Requirements:**
1. Professional and respectful tone
2. Clear and concise
3. Include all key points naturally
4. Proper email formatting
5. Appropriate subject line
6. Professional closing

Generate the complete email with subject line and body.

Format:
SUBJECT: [subject line]

BODY:
[complete email body]
"""

            messages = [
                {
                    "role": "system",
                    "content": "You are an expert insurance correspondence specialist. Write professional, clear, and effective emails for roofing insurance claims."
                },
                {"role": "user", "content": prompt}
            ]

            response = await ai_provider_manager.generate(
                messages=messages,
                ai_type="susan",
                user_id=str(user_id)
            )

            # Parse response
            content = response['content']

            # Extract subject
            subject = "Insurance Claim Correspondence"
            if 'SUBJECT:' in content:
                subject = content.split('SUBJECT:')[1].split('BODY:')[0].strip()

            # Extract body
            body = content
            if 'BODY:' in content:
                body = content.split('BODY:')[1].strip()

            # Save generated email
            generated = GeneratedEmail(
                user_id=user_id,
                template_name="custom_ai_generated",
                subject=subject,
                body=body,
                variables={
                    "purpose": purpose,
                    "key_points": key_points,
                    "recipient_info": recipient_info,
                    "claim_info": claim_info
                },
                recipient=recipient_info.get('email'),
                status="draft",
                metadata={
                    "generation_method": "ai_custom",
                    "provider": response['provider'],
                    "model": response['model']
                }
            )

            db.add(generated)
            await db.flush()

            logger.info(f"Generated custom AI email for user {user_id}")

            return {
                "email_id": str(generated.id),
                "subject": subject,
                "body": body,
                "metadata": {
                    "purpose": purpose,
                    "provider": response['provider']
                }
            }

        except Exception as e:
            logger.error(f"Error generating custom email: {e}", exc_info=True)
            raise

    async def get_generated_email(
        self,
        db: AsyncSession,
        email_id: UUID,
        user_id: UUID
    ) -> Optional[Dict]:
        """
        Retrieve a generated email

        Args:
            db: Database session
            email_id: Email ID
            user_id: User ID (for permission check)

        Returns:
            Email dict or None
        """
        try:
            result = await db.execute(
                select(GeneratedEmail).where(
                    GeneratedEmail.id == email_id,
                    GeneratedEmail.user_id == user_id
                )
            )
            email = result.scalar_one_or_none()

            if not email:
                return None

            return {
                "id": str(email.id),
                "subject": email.subject,
                "body": email.body,
                "template_name": email.template_name,
                "recipient": email.recipient,
                "status": email.status,
                "variables": email.variables,
                "created_at": email.created_at.isoformat(),
                "sent_at": email.sent_at.isoformat() if email.sent_at else None
            }

        except Exception as e:
            logger.error(f"Error retrieving generated email: {e}")
            return None

    async def mark_email_sent(
        self,
        db: AsyncSession,
        email_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Mark email as sent

        Args:
            db: Database session
            email_id: Email ID
            user_id: User ID (for permission check)

        Returns:
            Success boolean
        """
        try:
            result = await db.execute(
                select(GeneratedEmail).where(
                    GeneratedEmail.id == email_id,
                    GeneratedEmail.user_id == user_id
                )
            )
            email = result.scalar_one_or_none()

            if not email:
                return False

            email.status = "sent"
            email.sent_at = datetime.utcnow()

            await db.commit()

            logger.info(f"Marked email {email_id} as sent")

            return True

        except Exception as e:
            logger.error(f"Error marking email as sent: {e}")
            return False


# Global instance
email_generator = EmailGenerator()
