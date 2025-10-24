"""
RAG (Retrieval Augmented Generation) System
Vector search with pgvector for Susan's knowledge base
"""

from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime
from uuid import UUID

from models import KnowledgeBase, BuildingCode, Manufacturer, InsuranceCarrier
from rag.embeddings import embedding_generator
from loguru import logger
from config import settings


class RAGSystem:
    """
    Retrieval Augmented Generation system
    Searches knowledge base using vector similarity
    """

    def __init__(self):
        self.top_k = settings.RAG_TOP_K
        self.similarity_threshold = settings.RAG_SIMILARITY_THRESHOLD

    async def search_knowledge_base(
        self,
        db: AsyncSession,
        query: str,
        top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
        min_similarity: Optional[float] = None
    ) -> List[Dict]:
        """
        Search knowledge base using vector similarity

        Args:
            db: Database session
            query: Search query
            top_k: Number of results to return
            category_filter: Filter by category
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching knowledge base entries with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = await embedding_generator.generate_embedding(query)

            top_k = top_k or self.top_k
            min_similarity = min_similarity or self.similarity_threshold

            # Build SQL query with vector similarity
            # Using cosine distance operator <=>
            query_sql = text("""
                SELECT
                    id,
                    title,
                    content,
                    category,
                    source,
                    metadata,
                    1 - (embedding <=> :query_embedding) as similarity
                FROM knowledge_base
                WHERE
                    (:category IS NULL OR category = :category)
                    AND (1 - (embedding <=> :query_embedding)) >= :min_similarity
                ORDER BY embedding <=> :query_embedding
                LIMIT :top_k
            """)

            result = await db.execute(
                query_sql,
                {
                    "query_embedding": str(query_embedding),
                    "category": category_filter,
                    "min_similarity": min_similarity,
                    "top_k": top_k
                }
            )

            results = []
            for row in result.fetchall():
                results.append({
                    "id": str(row.id),
                    "title": row.title,
                    "content": row.content,
                    "category": row.category,
                    "source": row.source,
                    "metadata": row.metadata,
                    "similarity": float(row.similarity)
                })

            logger.info(f"RAG search found {len(results)} results for query: '{query[:50]}...'")

            return results

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}", exc_info=True)
            return []

    async def search_building_codes(
        self,
        db: AsyncSession,
        query: str,
        code_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Search building codes specifically
        Uses both vector similarity and keyword matching

        Args:
            db: Database session
            query: Search query
            code_type: Filter by code type (IBC, IRC, FBC, NFPA)

        Returns:
            List of matching building codes
        """
        try:
            # Try keyword matching first (exact code references)
            keyword_query = select(BuildingCode)

            if code_type:
                keyword_query = keyword_query.where(BuildingCode.code_type == code_type)

            # Search in code_number, title, or content
            search_term = f"%{query}%"
            keyword_query = keyword_query.where(
                (BuildingCode.code_number.ilike(search_term)) |
                (BuildingCode.title.ilike(search_term)) |
                (BuildingCode.content.ilike(search_term))
            ).limit(10)

            result = await db.execute(keyword_query)
            codes = result.scalars().all()

            results = [
                {
                    "id": str(code.id),
                    "code_type": code.code_type,
                    "code_number": code.code_number,
                    "title": code.title,
                    "content": code.content,
                    "section": code.section,
                    "year": code.year,
                    "match_type": "keyword"
                }
                for code in codes
            ]

            logger.info(f"Found {len(results)} building codes for query: '{query}'")

            return results

        except Exception as e:
            logger.error(f"Error searching building codes: {e}", exc_info=True)
            return []

    async def search_manufacturers(
        self,
        db: AsyncSession,
        query: str,
        manufacturer_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Search manufacturer specifications and guidelines

        Args:
            db: Database session
            query: Search query
            manufacturer_name: Filter by manufacturer (GAF, Owens Corning, etc.)

        Returns:
            List of matching manufacturer specs
        """
        try:
            query_obj = select(Manufacturer)

            if manufacturer_name:
                query_obj = query_obj.where(Manufacturer.name.ilike(f"%{manufacturer_name}%"))

            # Search in product_line, specs, or guidelines
            search_term = f"%{query}%"
            query_obj = query_obj.where(
                (Manufacturer.product_line.ilike(search_term)) |
                (Manufacturer.specifications.astext.ilike(search_term)) |
                (Manufacturer.installation_guidelines.astext.ilike(search_term))
            ).limit(10)

            result = await db.execute(query_obj)
            manufacturers = result.scalars().all()

            results = [
                {
                    "id": str(mfr.id),
                    "name": mfr.name,
                    "product_line": mfr.product_line,
                    "specifications": mfr.specifications,
                    "installation_guidelines": mfr.installation_guidelines,
                    "warranty_info": mfr.warranty_info
                }
                for mfr in manufacturers
            ]

            logger.info(f"Found {len(results)} manufacturer specs for query: '{query}'")

            return results

        except Exception as e:
            logger.error(f"Error searching manufacturers: {e}", exc_info=True)
            return []

    async def search_insurance_carriers(
        self,
        db: AsyncSession,
        carrier_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Search insurance carrier information

        Args:
            db: Database session
            carrier_name: Carrier name to search

        Returns:
            List of matching insurance carriers
        """
        try:
            query = select(InsuranceCarrier)

            if carrier_name:
                query = query.where(InsuranceCarrier.name.ilike(f"%{carrier_name}%"))

            result = await db.execute(query.limit(20))
            carriers = result.scalars().all()

            results = [
                {
                    "id": str(carrier.id),
                    "name": carrier.name,
                    "contact_info": carrier.contact_info,
                    "claims_process": carrier.claims_process,
                    "common_requirements": carrier.common_requirements,
                    "notes": carrier.notes
                }
                for carrier in carriers
            ]

            logger.info(f"Found {len(results)} insurance carriers")

            return results

        except Exception as e:
            logger.error(f"Error searching insurance carriers: {e}", exc_info=True)
            return []

    async def add_knowledge_entry(
        self,
        db: AsyncSession,
        title: str,
        content: str,
        category: str,
        source: str,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> UUID:
        """
        Add new entry to knowledge base
        Automatically generates and stores embedding

        Args:
            db: Database session
            title: Entry title
            content: Entry content
            category: Category (codes, manufacturers, insurance, procedures)
            source: Source reference
            metadata: Additional metadata
            tags: Tags for filtering

        Returns:
            UUID of created entry
        """
        try:
            # Generate embedding
            embedded = await embedding_generator.embed_knowledge_base_entry(
                title=title,
                content=content,
                metadata=metadata
            )

            # Create knowledge base entry
            entry = KnowledgeBase(
                title=title,
                content=content,
                category=category,
                source=source,
                embedding=embedded['embedding'],
                metadata=metadata or {},
                tags=tags or []
            )

            db.add(entry)
            await db.flush()

            logger.info(f"Added knowledge base entry: {title}")

            return entry.id

        except Exception as e:
            logger.error(f"Error adding knowledge entry: {e}", exc_info=True)
            raise

    async def build_context_for_query(
        self,
        db: AsyncSession,
        query: str,
        include_codes: bool = True,
        include_manufacturers: bool = True,
        include_insurance: bool = False
    ) -> Dict:
        """
        Build comprehensive context for a query
        Searches multiple sources and combines results

        Args:
            db: Database session
            query: User query
            include_codes: Include building codes
            include_manufacturers: Include manufacturer specs
            include_insurance: Include insurance carrier info

        Returns:
            Dict with context from multiple sources
        """
        try:
            context = {
                "query": query,
                "knowledge_base": [],
                "building_codes": [],
                "manufacturers": [],
                "insurance_carriers": [],
                "total_sources": 0
            }

            # Search general knowledge base
            kb_results = await self.search_knowledge_base(db, query, top_k=5)
            context["knowledge_base"] = kb_results
            context["total_sources"] += len(kb_results)

            # Search building codes if requested
            if include_codes:
                codes = await self.search_building_codes(db, query)
                context["building_codes"] = codes
                context["total_sources"] += len(codes)

            # Search manufacturers if requested
            if include_manufacturers:
                manufacturers = await self.search_manufacturers(db, query)
                context["manufacturers"] = manufacturers
                context["total_sources"] += len(manufacturers)

            # Search insurance carriers if requested
            if include_insurance:
                carriers = await self.search_insurance_carriers(db)
                context["insurance_carriers"] = carriers[:3]  # Limit to top 3
                context["total_sources"] += len(context["insurance_carriers"])

            logger.info(f"Built context with {context['total_sources']} total sources")

            return context

        except Exception as e:
            logger.error(f"Error building context: {e}", exc_info=True)
            return {"query": query, "knowledge_base": [], "total_sources": 0}

    def format_context_for_prompt(self, context: Dict) -> str:
        """
        Format context into a string for AI prompt
        Creates a structured context with citations

        Args:
            context: Context dict from build_context_for_query

        Returns:
            Formatted context string
        """
        try:
            prompt_parts = ["=== RELEVANT KNOWLEDGE BASE ===\n"]

            # Add general knowledge
            if context.get("knowledge_base"):
                prompt_parts.append("## Knowledge Base Entries:\n")
                for i, entry in enumerate(context["knowledge_base"][:3], 1):
                    prompt_parts.append(f"\n**Source {i}:** {entry['title']} (Similarity: {entry['similarity']:.2f})")
                    prompt_parts.append(f"Category: {entry['category']}")
                    prompt_parts.append(f"Content: {entry['content'][:500]}...")
                    prompt_parts.append(f"Reference: {entry['source']}\n")

            # Add building codes
            if context.get("building_codes"):
                prompt_parts.append("\n## Building Codes:\n")
                for code in context["building_codes"][:3]:
                    prompt_parts.append(f"\n**{code['code_type']} {code['code_number']}:** {code['title']}")
                    prompt_parts.append(f"Content: {code['content'][:300]}...")
                    prompt_parts.append(f"Section: {code.get('section', 'N/A')}\n")

            # Add manufacturer specs
            if context.get("manufacturers"):
                prompt_parts.append("\n## Manufacturer Specifications:\n")
                for mfr in context["manufacturers"][:2]:
                    prompt_parts.append(f"\n**{mfr['name']} - {mfr['product_line']}**")
                    if mfr.get('specifications'):
                        prompt_parts.append(f"Specs: {str(mfr['specifications'])[:200]}...\n")

            # Add insurance carrier info
            if context.get("insurance_carriers"):
                prompt_parts.append("\n## Insurance Carriers:\n")
                for carrier in context["insurance_carriers"][:2]:
                    prompt_parts.append(f"\n**{carrier['name']}**")
                    if carrier.get('common_requirements'):
                        prompt_parts.append(f"Requirements: {str(carrier['common_requirements'])[:200]}...\n")

            prompt_parts.append("\n=== END KNOWLEDGE BASE ===\n")
            prompt_parts.append(f"\nTotal sources: {context['total_sources']}")
            prompt_parts.append("\nUse this information to answer the user's question accurately. Always cite sources.")

            return "\n".join(prompt_parts)

        except Exception as e:
            logger.error(f"Error formatting context: {e}", exc_info=True)
            return ""


# Global instance
rag_system = RAGSystem()
