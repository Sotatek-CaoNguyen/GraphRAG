"""Baseline keyword retrieval for comparison against GraphRAG."""
import re
import time
from typing import List, Dict, Any, Tuple

from .database import db

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "to", "was", "were", "with", "which", "who", "whom", "what", "where",
    "when", "why", "how"
}


def extract_keywords(question: str) -> List[str]:
    """Extract simple keywords without LLM analysis."""
    tokens = re.findall(r"[A-Za-z0-9']+", question.lower())
    keywords = [token for token in tokens if token not in STOPWORDS and len(token) > 2]
    return keywords or tokens or [question]


def query_movies_by_keywords(keyword_list: List[str], limit: int = 50) -> List[Dict[str, Any]]:
    """Find movies by matching keywords in title or description."""
    escaped_keywords = [re.escape(keyword) for keyword in keyword_list if keyword]
    if not escaped_keywords:
        return []

    pattern = "(?i).*(" + "|".join(escaped_keywords) + ").*"
    query = """
        MATCH (m:Movie)
        WHERE (m.description IS NOT NULL AND m.description =~ $pattern)
           OR (m.original_title IS NOT NULL AND m.original_title =~ $pattern)
        RETURN m.original_title as title,
               m.year as year,
               m.description as description,
               m.avg_vote as rating,
               m.imdb_title_id as imdb_id
        ORDER BY m.avg_vote DESC
        LIMIT $limit
    """

    return db.execute_query(query, {"pattern": pattern, "limit": limit})


def execute_baseline_rag_query(question: str) -> Tuple[List[Dict[str, Any]], float, List[str]]:
    """Execute baseline retrieval and return results with timing and keywords."""
    keywords = extract_keywords(question)
    query_start_time = time.time()
    results = query_movies_by_keywords(keywords)
    query_time = time.time() - query_start_time
    return results, query_time, keywords
