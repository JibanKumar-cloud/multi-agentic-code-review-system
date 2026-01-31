"""
RAG Engine for Security Knowledge Base.

Provides vector-based semantic search over security documentation
to enhance code review accuracy with authoritative references.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib
import json

logger = logging.getLogger(__name__)

# Knowledge base directory
DOCS_DIR = Path(__file__).parent / "docs"


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for security knowledge.
    
    Uses ChromaDB for vector search when available, falls back to
    keyword search otherwise.
    """
    
    def __init__(self):
        self._collection = None
        self._client = None
        self._use_chroma = False
        self._documents_cache: Dict[str, str] = {}
        self._initialize()
        
    def _initialize(self):
        """Initialize the vector store."""
        try:
            import chromadb
            
            # Use in-memory for simplicity (can switch to persistent)
            self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                name="security_docs",
                metadata={"hnsw:space": "cosine"}
            )
            self._use_chroma = True
            logger.info("RAG Engine initialized with ChromaDB")
            
            # Index documents if collection is empty
            if self._collection.count() == 0:
                self._index_documents()
                
        except ImportError:
            logger.info("ChromaDB not available, using keyword search")
            self._use_chroma = False
            self._load_documents_cache()
            
    def _load_documents_cache(self):
        """Load all documents into memory for keyword search."""
        for doc_path in DOCS_DIR.rglob("*.md"):
            try:
                content = doc_path.read_text(encoding='utf-8')
                rel_path = str(doc_path.relative_to(DOCS_DIR))
                self._documents_cache[rel_path] = content
            except Exception as e:
                logger.error(f"Error loading {doc_path}: {e}")
                
        logger.info(f"Loaded {len(self._documents_cache)} documents into cache")
                
    def _index_documents(self):
        """Index all markdown documents into ChromaDB."""
        documents = []
        metadatas = []
        ids = []
        
        for doc_path in DOCS_DIR.rglob("*.md"):
            try:
                content = doc_path.read_text(encoding='utf-8')
                rel_path = str(doc_path.relative_to(DOCS_DIR))
                category = rel_path.split('/')[0] if '/' in rel_path else 'general'
                
                # Split into chunks for better retrieval
                chunks = self._chunk_document(content)
                
                for i, chunk in enumerate(chunks):
                    doc_id = hashlib.md5(f"{rel_path}_{i}".encode()).hexdigest()
                    documents.append(chunk['text'])
                    metadatas.append({
                        "source": rel_path,
                        "category": category,
                        "section": chunk.get('section', ''),
                        "chunk_index": i
                    })
                    ids.append(doc_id)
                    
            except Exception as e:
                logger.error(f"Error indexing {doc_path}: {e}")
                
        if documents:
            self._collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Indexed {len(documents)} document chunks")
            
    def _chunk_document(self, content: str, max_chunk_size: int = 1500) -> List[Dict]:
        """
        Split document into semantic chunks based on headers.
        
        Args:
            content: Full document text
            max_chunk_size: Maximum characters per chunk
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        current_section = "Overview"
        current_text = []
        
        for line in content.split('\n'):
            # Detect section headers
            if line.startswith('## '):
                # Save current chunk
                if current_text:
                    text = '\n'.join(current_text)
                    if len(text) > 50:  # Skip tiny chunks
                        chunks.append({
                            'section': current_section,
                            'text': text
                        })
                current_section = line[3:].strip()
                current_text = [line]
            else:
                current_text.append(line)
                
                # Split if chunk gets too large
                if len('\n'.join(current_text)) > max_chunk_size:
                    chunks.append({
                        'section': current_section,
                        'text': '\n'.join(current_text)
                    })
                    current_text = []
                    
        # Don't forget last chunk
        if current_text:
            text = '\n'.join(current_text)
            if len(text) > 50:
                chunks.append({
                    'section': current_section,
                    'text': text
                })
                
        return chunks if chunks else [{'section': 'full', 'text': content}]
        
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant security documentation.
        
        Args:
            query: Search query (e.g., "SQL injection f-string python")
            category: Filter by category (owasp, cwe, python, fixes)
            n_results: Number of results to return
            
        Returns:
            List of relevant document chunks with metadata
        """
        if self._use_chroma:
            return self._vector_search(query, category, n_results)
        else:
            return self._keyword_search(query, category, n_results)
            
    def _vector_search(
        self,
        query: str,
        category: Optional[str],
        n_results: int
    ) -> List[Dict[str, Any]]:
        """Semantic search using ChromaDB embeddings."""
        where_filter = {"category": category} if category else None
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            output = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    
                    output.append({
                        "content": doc,
                        "source": metadata.get("source", "unknown"),
                        "category": metadata.get("category", "general"),
                        "section": metadata.get("section", ""),
                        "relevance_score": round(1 - (distance / 2), 3)  # Normalize
                    })
                    
            return output
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return self._keyword_search(query, category, n_results)
            
    def _keyword_search(
        self,
        query: str,
        category: Optional[str],
        n_results: int
    ) -> List[Dict[str, Any]]:
        """Fallback keyword-based search with TF-IDF-like scoring."""
        query_terms = query.lower().split()
        results = []
        
        for rel_path, content in self._documents_cache.items():
            # Filter by category
            doc_category = rel_path.split('/')[0] if '/' in rel_path else 'general'
            if category and doc_category != category:
                continue
                
            content_lower = content.lower()
            
            # Score based on term frequency and position
            score = 0
            for term in query_terms:
                count = content_lower.count(term)
                if count > 0:
                    # Boost if term appears in first 500 chars (likely title/overview)
                    position_boost = 2 if term in content_lower[:500] else 1
                    score += count * position_boost
                    
            if score > 0:
                # Extract most relevant section
                relevant_section = self._extract_relevant_section(content, query_terms)
                
                results.append({
                    "content": relevant_section,
                    "source": rel_path,
                    "category": doc_category,
                    "section": "",
                    "relevance_score": min(score / (len(query_terms) * 10), 1.0)
                })
                
        # Sort by score descending
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:n_results]
        
    def _extract_relevant_section(
        self,
        content: str,
        query_terms: List[str],
        max_length: int = 1500
    ) -> str:
        """Extract the most relevant section from a document."""
        content_lower = content.lower()
        
        # Find the best starting position
        best_pos = 0
        best_score = 0
        
        for i in range(0, len(content) - 200, 100):
            window = content_lower[i:i+500]
            score = sum(window.count(term) for term in query_terms)
            if score > best_score:
                best_score = score
                best_pos = i
                
        # Extract section around best position
        start = max(0, best_pos - 100)
        end = min(len(content), start + max_length)
        
        # Try to start at a line boundary
        while start > 0 and content[start] != '\n':
            start -= 1
            
        return content[start:end].strip()


# Global instance
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get or create the global RAG engine instance."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine


def search_security_docs(
    query: str,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search security documentation - TOOL FUNCTION.
    
    This is called by the agent tool system.
    
    Args:
        query: What to search for (e.g., "SQL injection python f-string fix")
        category: Optional filter - one of: owasp, cwe, python, fixes
        
    Returns:
        Dictionary with search results containing:
        - references: List of relevant document excerpts
        - count: Number of results found
    """
    engine = get_rag_engine()
    results = engine.search(query, category, n_results=3)
    
    return {
        "query": query,
        "category": category,
        "references": [
            {
                "source": r["source"],
                "category": r["category"],
                "content": r["content"][:1200],  # Limit for token efficiency
                "relevance": r["relevance_score"]
            }
            for r in results
        ],
        "count": len(results)
    }
