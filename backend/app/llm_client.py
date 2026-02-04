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
        self.model_name = "mistralai/mistral-7b-instruct-v0.2"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        self.client = httpx.Client(timeout=60.0, headers=headers)

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
        
        groudning_text = self._format_grounding_data(graphrag_results)
        
        user_prompt = f"""User Question: {question}

Based on our movie database, here are the relevant films:

{groudning_text}

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
            
            usage = result.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)
            }
            
            response_text = result["choices"][0]["message"]["content"].strip()
            return response_text, token_usage, elapsed_time
        except Exception as e:
            print(f"Error calling OpenRouter: {e}")
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

        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that analyzes movie queries. Always respond with valid JSON only."},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 300,
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            result = response.json()
            elapsed_time = time.time() - start_time
            
            usage = result.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)
            }
            
            content = result["choices"][0]["message"]["content"].strip()
            analysis = json.loads(content)
            
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
            print(f"Error analyzing query with OpenRouter: {e}")
            elapsed_time = time.time() - start_time
            return {"type": "keywords", "keywords": question.split()}, {"prompt_tokens": 0, "completion_tokens": 0}, elapsed_time

    def health_check(self) -> bool:
        """Check if the OpenRouter API key is available."""
        return bool(self.api_key)

# Global client instance
llm_client = OpenRouterClient()

