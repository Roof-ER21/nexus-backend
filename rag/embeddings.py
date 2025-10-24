"""
Vector Embeddings Generation
OpenAI text-embedding-3-small for RAG system
"""

from typing import List, Dict, Optional
import openai
from openai import AsyncOpenAI
import numpy as np
from loguru import logger

from config import settings

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class EmbeddingGenerator:
    """
    Generate vector embeddings for RAG system
    Uses OpenAI text-embedding-3-small (1536 dimensions)
    """

    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS
        self.max_tokens = 8191  # Max tokens for text-embedding-3-small

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Truncate if too long
            if len(text) > self.max_tokens * 4:  # Rough character estimate
                text = text[:self.max_tokens * 4]
                logger.warning(f"Text truncated to {self.max_tokens} tokens")

            response = await client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )

            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding of dimension {len(embedding)}")

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        try:
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                # Truncate long texts
                batch = [
                    text[:self.max_tokens * 4] if len(text) > self.max_tokens * 4 else text
                    for text in batch
                ]

                response = await client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float"
                )

                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.info(f"Generated {len(batch_embeddings)} embeddings (batch {i // batch_size + 1})")

            return all_embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}", exc_info=True)
            raise

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            return float(similarity)

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    async def embed_document_chunks(
        self,
        document_text: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[Dict]:
        """
        Split document into chunks and embed each chunk
        Useful for long documents that exceed token limits

        Args:
            document_text: Full document text
            chunk_size: Characters per chunk
            overlap: Character overlap between chunks

        Returns:
            List of dicts with 'text' and 'embedding'
        """
        try:
            # Split into chunks with overlap
            chunks = []
            start = 0

            while start < len(document_text):
                end = start + chunk_size
                chunk_text = document_text[start:end]

                # Try to break at sentence boundary
                if end < len(document_text):
                    # Find last period, question mark, or exclamation
                    last_period = chunk_text.rfind('.')
                    last_question = chunk_text.rfind('?')
                    last_exclaim = chunk_text.rfind('!')

                    boundary = max(last_period, last_question, last_exclaim)

                    if boundary > chunk_size // 2:  # Only if we're not cutting too short
                        chunk_text = chunk_text[:boundary + 1]
                        end = start + boundary + 1

                chunks.append({
                    'text': chunk_text.strip(),
                    'start_index': start,
                    'end_index': end
                })

                start = end - overlap

            logger.info(f"Split document into {len(chunks)} chunks")

            # Generate embeddings for all chunks
            chunk_texts = [chunk['text'] for chunk in chunks]
            embeddings = await self.generate_embeddings_batch(chunk_texts)

            # Add embeddings to chunks
            for i, chunk in enumerate(chunks):
                chunk['embedding'] = embeddings[i]

            return chunks

        except Exception as e:
            logger.error(f"Error embedding document chunks: {e}", exc_info=True)
            raise

    async def embed_knowledge_base_entry(
        self,
        title: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Embed a knowledge base entry
        Combines title and content for better semantic search

        Args:
            title: Entry title
            content: Entry content
            metadata: Optional metadata

        Returns:
            Dict with embedding and combined text
        """
        try:
            # Combine title and content
            combined_text = f"Title: {title}\n\nContent: {content}"

            # Generate embedding
            embedding = await self.generate_embedding(combined_text)

            return {
                'title': title,
                'content': content,
                'combined_text': combined_text,
                'embedding': embedding,
                'metadata': metadata or {}
            }

        except Exception as e:
            logger.error(f"Error embedding knowledge base entry: {e}", exc_info=True)
            raise


# Global instance
embedding_generator = EmbeddingGenerator()
