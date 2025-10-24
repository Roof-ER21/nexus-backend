"""
Email Template System
Jinja2 templates for professional insurance emails
"""

from jinja2 import Environment, BaseLoader, TemplateNotFound
from typing import Dict, Optional
from loguru import logger


class EmailTemplateEngine:
    """
    Render email templates with variable substitution
    Uses Jinja2 for flexible templating
    """

    def __init__(self):
        self.env = Environment(loader=BaseLoader())

    def render_template(
        self,
        template_string: str,
        variables: Dict
    ) -> str:
        """
        Render a template with variables

        Args:
            template_string: Jinja2 template string
            variables: Dict of variables to substitute

        Returns:
            Rendered template string
        """
        try:
            template = self.env.from_string(template_string)
            rendered = template.render(**variables)

            logger.debug(f"Rendered template with {len(variables)} variables")

            return rendered

        except Exception as e:
            logger.error(f"Error rendering template: {e}", exc_info=True)
            raise

    def get_default_templates(self) -> Dict[str, str]:
        """
        Get dictionary of default email templates

        Returns:
            Dict mapping template names to template strings
        """
        return {
            "adjuster_initial_contact": """
Subject: Insurance Claim Documentation - {{ homeowner_name }} at {{ property_address }}

Dear {{ adjuster_name }},

I am writing on behalf of {{ homeowner_name }} regarding the insurance claim for storm damage at {{ property_address }}.

**Claim Details:**
- Claim Number: {{ claim_number }}
- Date of Loss: {{ loss_date }}
- Property Address: {{ property_address }}
- Policyholder: {{ homeowner_name }}

**Damage Summary:**
{{ damage_summary }}

I have completed a thorough inspection and documented all damage following industry standards. Attached you will find:
{% for document in attached_documents %}
- {{ document }}
{% endfor %}

**Next Steps:**
{{ next_steps }}

I am available to meet at your earliest convenience to review the damage together. Please let me know your availability for a joint inspection.

Thank you for your time and attention to this matter.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip(),

            "code_citation_support": """
Subject: Building Code Requirements - {{ claim_number }}

Dear {{ adjuster_name }},

Following our conversation regarding the claim at {{ property_address }}, I wanted to provide specific building code references that support the scope of work.

**Applicable Building Codes:**
{% for code in building_codes %}
- **{{ code.code_type }} {{ code.code_number }}:** {{ code.description }}
{% endfor %}

**Manufacturer Requirements:**
{% for req in manufacturer_requirements %}
- **{{ req.manufacturer }}:** {{ req.requirement }}
{% endfor %}

These requirements mandate {{ required_scope }}, which is reflected in our estimate.

I have attached detailed documentation including:
{% for document in attached_documents %}
- {{ document }}
{% endfor %}

Please let me know if you need any additional information or clarification regarding these code requirements.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip(),

            "repair_attempt_notification": """
Subject: Repair Attempt Documentation - {{ claim_number }}

Dear {{ adjuster_name }},

Per our discussion, I am providing documentation of the repair attempt at {{ property_address }}.

**Repair Attempt Summary:**
- Date of Attempt: {{ attempt_date }}
- Work Attempted: {{ work_attempted }}
- Outcome: {{ outcome }}
- Reason for Failure: {{ failure_reason }}

**Documented Evidence:**
{% for item in evidence_items %}
- {{ item }}
{% endfor %}

This repair attempt demonstrates that {{ conclusion }}.

Per the Roof-ER Repair Attempt Template, we have thoroughly documented:
1. Initial damage assessment
2. Repair methodology attempted
3. Materials used
4. Photographic evidence of failure
5. Expert opinion on viability

Based on this documentation, we recommend proceeding with {{ recommended_action }}.

I have completed the formal Repair Attempt Template and attached it for your review.

Please let me know if you require any additional information.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip(),

            "escalation_request": """
Subject: Request for Escalation - Claim {{ claim_number }}

Dear {{ adjuster_name }},

I am writing to formally request escalation of the claim for {{ homeowner_name }} at {{ property_address }}.

**Claim Information:**
- Claim Number: {{ claim_number }}
- Date of Loss: {{ loss_date }}
- Current Status: {{ current_status }}

**Reason for Escalation:**
{{ escalation_reason }}

**Supporting Documentation:**
{% for document in supporting_documents %}
- {{ document }}
{% endfor %}

**Unresolved Issues:**
{% for issue in unresolved_issues %}
{{ loop.index }}. {{ issue }}
{% endfor %}

Despite multiple attempts to resolve these issues, we have been unable to reach an agreement that adequately addresses the documented damage and applicable code requirements.

**Requested Resolution:**
{{ requested_resolution }}

I respectfully request that this claim be reviewed by your supervisor or the appropriate level of management. I am available to provide any additional information or documentation that may be helpful.

I appreciate your assistance in this matter and look forward to a prompt resolution.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}

cc: {{ cc_recipients }}
            """.strip(),

            "supplemental_request": """
Subject: Supplemental Damage Documentation - {{ claim_number }}

Dear {{ adjuster_name }},

During the course of work at {{ property_address }}, we have discovered additional damage that was not visible during the initial inspection.

**Original Claim Scope:**
{{ original_scope }}

**Newly Discovered Damage:**
{% for item in new_damage_items %}
- **{{ item.component }}:** {{ item.description }}
  - Cause: {{ item.cause }}
  - Repair Required: {{ item.repair }}
  - Cost: ${{ item.cost }}
{% endfor %}

**Total Supplemental Amount:** ${{ supplemental_total }}

**Documentation Provided:**
{% for document in attached_documents %}
- {{ document }}
{% endfor %}

This supplemental damage is directly related to the original loss event on {{ loss_date }} and was not visible until {{ discovery_circumstances }}.

I am available to meet and review this additional damage at your convenience.

Thank you for your prompt attention to this matter.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip(),

            "photo_report_transmittal": """
Subject: Photo Report - {{ property_address }}

Dear {{ adjuster_name }},

Please find attached the comprehensive photo report for the property at {{ property_address }}.

**Report Details:**
- Claim Number: {{ claim_number }}
- Inspection Date: {{ inspection_date }}
- Total Photos: {{ photo_count }}
- Inspector: {{ inspector_name }}

**Photo Report Contents:**
{% for section in report_sections %}
- {{ section.name }} ({{ section.photo_count }} photos)
{% endfor %}

The report follows the Roof-ER Photo Report Template and includes:
1. Property overview and context
2. Detailed damage documentation
3. Close-up shots of affected areas
4. Reference measurements and markers
5. Surrounding property conditions

All photos are timestamped, geotagged, and include detailed descriptions.

Please review and let me know if you need any additional photographs or clarification.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip(),

            "weather_verification": """
Subject: Weather Event Verification - {{ claim_number }}

Dear {{ adjuster_name }},

I am providing official weather data verification for the loss event at {{ property_address }}.

**Claim Information:**
- Claim Number: {{ claim_number }}
- Reported Date of Loss: {{ loss_date }}
- Property Location: {{ property_address }}

**Weather Event Verification:**
- **Event Type:** {{ event_type }}
- **Event Date:** {{ event_date }}
- **Location:** {{ event_location }}
- **Severity:** {{ severity_details }}

**Official Sources:**
{% for source in weather_sources %}
- **{{ source.name }}:** {{ source.details }}
  - Source: {{ source.reference }}
{% endfor %}

**Damage Correlation:**
{{ damage_correlation }}

The documented damage at this property is consistent with {{ event_type }} events of this magnitude occurring on {{ event_date }}.

Attached please find:
{% for document in attached_documents %}
- {{ document }}
{% endfor %}

This verification supports the causal relationship between the weather event and the documented damage.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip(),

            "itel_submission": """
Subject: iTel Documentation - {{ claim_number }}

Dear {{ adjuster_name }},

I am submitting completed iTel (Insurance Technology Electronic Link) documentation for {{ property_address }}.

**iTel Submission Details:**
- Claim Number: {{ claim_number }}
- Submission Date: {{ submission_date }}
- Property: {{ property_address }}
- Policyholder: {{ homeowner_name }}

**Documentation Included:**
{% for item in documentation_items %}
{{ loop.index }}. {{ item.name }}
   - Status: {{ item.status }}
   - Details: {{ item.details }}
{% endfor %}

**Estimate Summary:**
- Total Claim Amount: ${{ total_amount }}
- Depreciation: ${{ depreciation }}
- Deductible: ${{ deductible }}
- Net Payment: ${{ net_payment }}

All documentation has been uploaded to the iTel system and is available for your review.

**System Reference:**
- iTel Reference Number: {{ itel_reference }}
- Upload Date/Time: {{ upload_timestamp }}

Please confirm receipt and let me know if any additional information is required.

Best regards,
{{ rep_name }}
{{ company_name }}
{{ rep_phone }}
{{ rep_email }}
            """.strip()
        }

    def create_custom_template(
        self,
        name: str,
        subject: str,
        body: str
    ) -> str:
        """
        Create a custom email template

        Args:
            name: Template name
            subject: Email subject line (can include variables)
            body: Email body (can include Jinja2 syntax)

        Returns:
            Complete template string
        """
        template = f"Subject: {subject}\n\n{body}"
        logger.info(f"Created custom template: {name}")
        return template


# Global instance
email_template_engine = EmailTemplateEngine()
