"""
Susan AI Models - Insurance Expert System
Conversations, messages, and knowledge base
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
from .database import Base

class SusanConversation(Base):
    """Susan conversation tracking"""
    __tablename__ = "susan_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_message_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    message_count = Column(Integer, default=0)
    archived = Column(Boolean, default=False)
    metadata = Column(JSONB)  # Store additional context

    # Relationships
    user = relationship("User", back_populates="susan_conversations")
    messages = relationship("SusanMessage", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SusanConversation {self.id} - {self.title}>"

class SusanMessage(Base):
    """Individual messages in Susan conversations"""
    __tablename__ = "susan_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("susan_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    metadata = Column(JSONB)  # RAG sources, function calls, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    conversation = relationship("SusanConversation", back_populates="messages")

    def __repr__(self):
        return f"<SusanMessage {self.role}: {self.content[:50]}...>"

class KnowledgeBase(Base):
    """RAG knowledge base with vector embeddings"""
    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embedding dimensions
    metadata = Column(JSONB)  # Source, tags, references
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    active = Column(Boolean, default=True)

    # Create index for vector similarity search
    __table_args__ = (
        Index(
            'idx_knowledge_embedding',
            embedding,
            postgresql_using='ivfflat',
            postgresql_with={'lists': 100},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )

    def __repr__(self):
        return f"<KnowledgeBase {self.category}: {self.title}>"

class BuildingCode(Base):
    """Building codes database"""
    __tablename__ = "building_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_type = Column(String(50), nullable=False, index=True)  # IBC, IRC, FBC, NFPA
    code_number = Column(String(50))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    requirements = Column(JSONB)
    jurisdiction = Column(String(100))  # State, county, city
    effective_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<BuildingCode {self.code_type}: {self.code_number}>"

class Manufacturer(Base):
    """Manufacturer specifications"""
    __tablename__ = "manufacturers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    product_lines = Column(JSONB)
    specifications = Column(JSONB)
    warranties = Column(JSONB)
    installation_guides = Column(JSONB)
    storm_damage_guidelines = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Manufacturer {self.name}>"

class InsuranceCarrier(Base):
    """Insurance carrier information"""
    __tablename__ = "insurance_carriers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    contact_info = Column(JSONB)
    policy_types = Column(JSONB)
    claim_procedures = Column(JSONB)
    common_coverages = Column(JSONB)
    adjuster_notes = Column(JSONB)  # Common adjuster behaviors
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<InsuranceCarrier {self.name}>"

class ProcessedDocument(Base):
    """Uploaded and processed documents"""
    __tablename__ = "processed_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    storage_path = Column(String(500))
    extracted_text = Column(Text)
    extracted_data = Column(JSONB)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ProcessedDocument {self.filename}>"

class EmailTemplate(Base):
    """Email templates for generation"""
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    subject = Column(String(255))
    body = Column(Text, nullable=False)
    variables = Column(JSONB)  # Required variables
    category = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<EmailTemplate {self.name}>"

class GeneratedEmail(Base):
    """Generated emails log"""
    __tablename__ = "generated_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id"))
    subject = Column(String(255))
    body = Column(Text)
    recipient_name = Column(String(255))
    context = Column(JSONB)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<GeneratedEmail {self.subject}>"

class WeatherEvent(Base):
    """Weather verification data"""
    __tablename__ = "weather_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location = Column(String(255), nullable=False, index=True)
    lat = Column(String(20))
    lng = Column(String(20))
    event_date = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(String(50))  # hail, wind, tornado, etc.
    wind_speed = Column(String(50))
    hail_size = Column(String(50))
    precipitation = Column(String(50))
    data_source = Column(String(100))
    raw_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<WeatherEvent {self.location} - {self.event_date}>"
