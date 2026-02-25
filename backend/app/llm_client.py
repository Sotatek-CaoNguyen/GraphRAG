"""OpenRouter API client for generating natural language responses."""
import os
import json
import httpx
import time
from typing import List, Dict, Any, Optional, Tuple

SISKEL_EBERT_SYSTEM_PROMPT = f"""You are a research assistant that can answer questions about movies.
You are given a question and a list of movies.
You need to answer the question based on the movies.
You need to use the movies to answer the question.
You need to use the movies to answer the question.
"""

class OpenRouterClient:
    """Client for interacting with OpenRouter's OpenAI-compatible API."""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1"
        self.model_name = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct-v0.2")
        self._health_cache_ttl_seconds = 60.0
        self._health_cache_checked_at: float = 0.0
        self._health_cache_ok: bool = False

        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # OpenRouter recommends setting these optional headers for attribution/observability.
        # They are safe to omit; kept here as a best practice.
        headers.setdefault("HTTP-Referer", "http://localhost")
        headers.setdefault("X-Title", "CineGraph")

        self.client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers=headers
        )

    def _parse_usage(self, result: Dict[str, Any], response: Optional[httpx.Response] = None) -> Dict[str, int]:
        """Extract token usage from OpenAI-compatible responses; fallback to 0 if unavailable."""
        usage = result.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)

        # Some gateways may return usage in a header as JSON.
        if (prompt_tokens == 0 and completion_tokens == 0) and response is not None:
            header_usage = response.headers.get("x-openrouter-usage")
            if header_usage:
                try:
                    header_usage_obj = json.loads(header_usage)
                    prompt_tokens = int(header_usage_obj.get("prompt_tokens") or 0)
                    completion_tokens = int(header_usage_obj.get("completion_tokens") or 0)
                except Exception:
                    pass

        return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

    def _estimate_token_count(self, text: str) -> int:
        """
        Rough token estimation when provider does not return usage.
        Heuristic: ~4 characters per token (works reasonably for Latin scripts).
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _log_openrouter_error(self, prefix: str, exc: Exception):
        if isinstance(exc, httpx.HTTPStatusError):
            body = exc.response.text
            if len(body) > 800:
                body = body[:800] + "...(truncated)"
            print(f"{prefix}: HTTP {exc.response.status_code} - {body}")
            return
        print(f"{prefix}: {exc}")

    def generate_response(self, question: str, graphrag_results: List[Dict[str, Any]]) -> Tuple[str, Dict[str, int], float]:
        """
        Generate a natural language response.
        
        Args:
            question: The user's question
            graphrag_results: response from GraphRAG query
            
        Returns:
            Tuple of (response_text, token_usage_dict, elapsed_time)
        """
        start_time = time.time()
        
        if not self.api_key:
            return self._generate_fallback_response(question, graphrag_results), {"prompt_tokens": 0, "completion_tokens": 0}, 0.0

        if not graphrag_results:
            response_text = self._generate_no_results_response(question)
            elapsed_time = time.time() - start_time
            return response_text, {"prompt_tokens": 0, "completion_tokens": 0}, elapsed_time
        
        grounding_text = self._format_grounding_data(graphrag_results)
        
        user_prompt = f"""User Question: {question}

Based on our movie database, here are the relevant films:

{grounding_text}

Please provide a text summary of the movies that are relevant to the user's question.
"""
        
        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": SISKEL_EBERT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.4,
                    "max_tokens": 500,
                    "stop": ["\n\n\n"]
                }
            )
            response.raise_for_status()
            result = response.json()
            elapsed_time = time.time() - start_time

            token_usage = self._parse_usage(result, response)
            
            response_text = result["choices"][0]["message"]["content"].strip()
            if token_usage.get("prompt_tokens", 0) == 0 and token_usage.get("completion_tokens", 0) == 0:
                token_usage = {
                    "prompt_tokens": self._estimate_token_count(SISKEL_EBERT_SYSTEM_PROMPT + "\n" + user_prompt),
                    "completion_tokens": self._estimate_token_count(response_text),
                }
            return response_text, token_usage, elapsed_time
        except Exception as e:
            self._log_openrouter_error("Error calling OpenRouter", e)
            elapsed_time = time.time() - start_time
            response_text = self._generate_fallback_response(question, graphrag_results)
            return response_text, {"prompt_tokens": 0, "completion_tokens": 0}, elapsed_time

    def _format_grounding_data(self, grounding_data: List[Dict[str, Any]]) -> str:
        """Format grounding data into a JSON string."""
        limited_data = grounding_data[:100]
        return json.dumps(limited_data, indent=2)

    def _generate_no_results_response(self, question: str) -> str:
        """Generate a response when no movies are found."""
        return f"""We couldn't find any movies matching "{question}". Try rephrasing your question."""

    def _generate_fallback_response(self, question: str, movies: List[Dict[str, Any]]) -> str:
        """Generate a fallback response if LLM call fails."""
        if not movies:
            return self._generate_no_results_response(question)
        
        response_parts = [f"We found {len(movies)} movie(s) for your query:\n\n"]
        for idx, movie in enumerate(movies[:5], 1):
            title = movie.get("title", "Unknown")
            year = movie.get("year", "?")
            response_parts.append(f"{idx}. {title} ({year})")
        
        return "\n".join(response_parts)

    def analyze_query(self, question: str) -> Tuple[Dict[str, Any], Dict[str, int], float]:
        """
        Analyze a user's question to determine query type and extract key terms.
        """
        start_time = time.time()

        if not self.api_key:
             return {"type": "keywords", "keywords": question.split()}, {"prompt_tokens": 0, "completion_tokens": 0}, 0.0

        analysis_prompt = f"""Analyze the following movie-related question and extract key information.

Question: "{question}"

Determine the query type and extract key terms. Supported types are "actor_genre", "director_actor", and "keywords".

Respond with a JSON object in this exact format:
{{
    "query_type": "one of the supported types",
    "director": "director name or null",
    "actor": "actor name or null",
    "genre": "genre name or null",
    "keywords": ["list", "of", "keywords"] or null
}}
"""

        def _post_analyze(include_response_format: bool) -> httpx.Response:
            payload: Dict[str, Any] = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that analyzes movie queries. Always respond with valid JSON only."
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            }
            if include_response_format:
                payload["response_format"] = {"type": "json_object"}
            return self.client.post(f"{self.api_url}/chat/completions", json=payload)

        try:
            response = _post_analyze(include_response_format=True)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Some models/providers do not support `response_format`; retry without it.
                if e.response.status_code in (400, 404, 422):
                    response = _post_analyze(include_response_format=False)
                    response.raise_for_status()
                else:
                    raise

            result = response.json()
            elapsed_time = time.time() - start_time

            token_usage = self._parse_usage(result, response)
            
            content = result["choices"][0]["message"]["content"].strip()
            analysis = json.loads(content)
            if token_usage.get("prompt_tokens", 0) == 0 and token_usage.get("completion_tokens", 0) == 0:
                token_usage = {
                    "prompt_tokens": self._estimate_token_count(analysis_prompt),
                    "completion_tokens": self._estimate_token_count(content),
                }
            
            query_type = analysis.get("query_type", "keywords")
            if query_type not in ["actor_genre", "keywords", "director_actor"]:
                query_type = "keywords"

            result_dict = {"type": query_type}
            if analysis.get("actor"): result_dict["actor"] = analysis["actor"]
            if analysis.get("director"): result_dict["director"] = analysis["director"]
            if analysis.get("genre"): result_dict["genre"] = analysis["genre"]
            if analysis.get("keywords"): result_dict["keywords"] = analysis["keywords"]
            
            if query_type == "keywords" and not result_dict.get("keywords"):
                result_dict["keywords"] = question.split()
            
            return result_dict, token_usage, elapsed_time
            
        except Exception as e:
            self._log_openrouter_error("Error analyzing query with OpenRouter", e)
            elapsed_time = time.time() - start_time
            return {"type": "keywords", "keywords": question.split()}, {"prompt_tokens": 0, "completion_tokens": 0}, elapsed_time

    def health_check(self) -> bool:
        """Check OpenRouter reachability and API key validity (cached)."""
        if not self.api_key:
            return False

        now = time.time()
        if (now - self._health_cache_checked_at) < self._health_cache_ttl_seconds:
            return self._health_cache_ok

        ok = False
        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "Return OK."},
                        {"role": "user", "content": "OK"}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1
                }
            )
            response.raise_for_status()
            ok = True
        except Exception as e:
            self._log_openrouter_error("OpenRouter health check failed", e)
            ok = False

        self._health_cache_checked_at = now
        self._health_cache_ok = ok
        return ok

# Global client instance
llm_client = OpenRouterClient()

