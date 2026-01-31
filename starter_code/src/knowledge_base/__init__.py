"""
Security Knowledge Base for RAG-enhanced code review.

This module provides retrieval-augmented generation capabilities
using OWASP, CWE, and Python security documentation.
"""

from .rag_engine import (
    RAGEngine,
    get_rag_engine,
    search_security_docs
)

__all__ = [
    'RAGEngine',
    'get_rag_engine', 
    'search_security_docs'
]
