"""FastAPI application entry point."""
import os
import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .database import db
from .csv_importer import import_movies_csv
from .graphrag import execute_graphrag_query
from .baseline_rag import execute_baseline_rag_query
from .llm_client import llm_client


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    openrouter_available: bool
    graph_has_data: bool


class ComparisonMetrics(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    analysis_time: float
    retrieval_time: float
    llm_time: float
    tokens_per_second: float


class ComparisonResult(BaseModel):
    answer: str
    results_count: int
    metrics: ComparisonMetrics


class CompareResponse(BaseModel):
    baseline: ComparisonResult
    graphrag: ComparisonResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    async def initialize_backend():
        print("Starting CineGraph backend...")

        connect_ok = False
        try:
            await asyncio.to_thread(db.connect)
            connect_ok = True
            print("Neo4j connected successfully")
        except Exception as e:
            print(f"Warning: Could not connect to Neo4j: {e}")
            print("Will retry on first request...")

        if connect_ok:
            try:
                has_data = await asyncio.to_thread(db.has_data)
                if not has_data:
                    print("Graph is empty. Importing movies from CSV...")
                    csv_path = os.getenv("CSV_PATH", "/app/movies.csv")
                    if os.path.exists(csv_path):
                        await asyncio.to_thread(import_movies_csv, csv_path)
                    else:
                        print(f"CSV file not found at {csv_path}. Skipping import.")
                else:
                    print("Graph already contains data. Skipping CSV import.")
            except Exception as e:
                print(f"Error during CSV import check: {e}")
        else:
            print("Skipping CSV import because Neo4j is unavailable at startup.")

        if llm_client.health_check():
            print("OpenRouter service is available")
        else:
            print("Warning: OpenRouter service is not available. Responses may be limited.")

    init_task = asyncio.create_task(initialize_backend())
    try:
        yield
    finally:
        init_task.cancel()
        with suppress(asyncio.CancelledError):
            await init_task
        print("Shutting down CineGraph backend...")
        db.close()


app = FastAPI(
    title="CineGraph API",
    description="GraphRAG API for movie queries",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    neo4j_connected = False
    graph_has_data = False
    
    try:
        if not db.driver:
            db.connect()
        neo4j_connected = True
        graph_has_data = db.has_data()
    except Exception as e:
        print(f"Neo4j health check failed: {e}")
    
    openrouter_available = llm_client.health_check()
    
    status = "healthy" if (neo4j_connected and openrouter_available) else "degraded"
    
    return HealthResponse(
        status=status,
        neo4j_connected=neo4j_connected,
        openrouter_available=openrouter_available,
        graph_has_data=graph_has_data
    )


def format_movies_as_markdown_table(movies: List[Dict[str, Any]]) -> str:
    """Format movie results as a markdown table dynamically based on dictionary keys."""
    if not movies:
        return "No movies found."
    
    # Get the keys from the first dictionary (all dictionaries have the same structure)
    keys = list(movies[0].keys())
    
    if not keys:
        return "No data available."
    
    # Create table header row
    header_row = "| " + " | ".join(key.capitalize() for key in keys) + " |\n"
    
    # Create separator row
    separator_row = "| " + " | ".join("---" for _ in keys) + " |\n"
    
    # Build the markdown table
    markdown = header_row + separator_row
    
    # Add data rows
    for movie in movies:
        row_values = []
        for key in keys:
            value = movie.get(key, "")
            # Convert value to string if it's not already
            if not isinstance(value, str):
                value = str(value)
            # Truncate long values
            if len(value) > 100:
                value = value[:97] + "..."
            # Escape pipe characters in markdown
            value = value.replace("|", "\\|")
            row_values.append(value)
        
        markdown += "| " + " | ".join(row_values) + " |\n"
    
    return markdown


def format_analysis_table(
    prompt_tokens: int,
    completion_tokens: int,
    analysis_time: float,
    retrieval_time: float,
    llm_completion_time: float,
    tokens_per_second: float,
    analysis_label: str = "Query analysis",
    retrieval_label: str = "Retrieval"
) -> str:
    """Format analysis metrics as a markdown table."""
    markdown = "| Metric | Value |\n"
    markdown += "|--------|-------|\n"
    markdown += f"| Prompt tokens | {prompt_tokens} |\n"
    markdown += f"| Completion tokens | {completion_tokens} |\n"
    markdown += f"| Time taken for {analysis_label} (seconds) | {analysis_time:.2f} |\n"
    markdown += f"| Time taken for {retrieval_label} (seconds) | {retrieval_time:.2f} |\n"
    markdown += f"| Time taken for final LLM completion (seconds) | {llm_completion_time:.2f} |\n"
    markdown += f"| Tokens/second (final completion) | {tokens_per_second:.1f} |\n"
    return markdown


def build_markdown_answer(response_text: str, movies: List[Dict[str, Any]], analysis_table: str) -> str:
    """Build a markdown response with commentary, filmography, and metrics."""
    markdown_parts = []

    markdown_parts.append("# Commentary\n")
    markdown_parts.append(response_text)
    markdown_parts.append("\n\n")

    markdown_parts.append("# Matching Filmography\n")
    markdown_parts.append(format_movies_as_markdown_table(movies))
    markdown_parts.append("\n")

    markdown_parts.append("# Performance Stats\n")
    markdown_parts.append(analysis_table)

    return "\n".join(markdown_parts)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat queries using GraphRAG."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    # Ensure database connection
    if not db.driver:
        try:
            db.connect()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    
    try:
        # Execute GraphRAG query (returns movie_results, analysis_token_usage, analysis_time, query_time)
        graphrag_results, analysis_token_usage, analysis_time, query_time = execute_graphrag_query(request.question)
        
        # Generate natural language response (returns response_text, token_usage, elapsed_time)
        response_text, llm_token_usage, llm_time = llm_client.generate_response(request.question, graphrag_results)
        
        # Combine all token usage (from term extraction + final LLM completion)
        total_prompt_tokens = analysis_token_usage.get("prompt_tokens", 0) + llm_token_usage.get("prompt_tokens", 0)
        total_completion_tokens = analysis_token_usage.get("completion_tokens", 0) + llm_token_usage.get("completion_tokens", 0)
        
        # Calculate tokens/second for final LLM completion
        final_completion_tokens = llm_token_usage.get("completion_tokens", 0)
        tokens_per_second = final_completion_tokens / llm_time if llm_time > 0 else 0.0
        
        analysis_table = format_analysis_table(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            analysis_time=analysis_time,
            retrieval_time=query_time,
            llm_completion_time=llm_time,
            tokens_per_second=tokens_per_second,
            analysis_label="Term extraction",
            retrieval_label="GraphRAG query"
        )

        answer = build_markdown_answer(response_text, graphrag_results, analysis_table)

        return ChatResponse(answer=answer)
    except Exception as e:
        print(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.post("/api/baseline", response_model=ChatResponse)
async def baseline_chat(request: ChatRequest):
    """Handle chat queries using baseline keyword retrieval."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not db.driver:
        try:
            db.connect()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")

    try:
        baseline_results, baseline_query_time, _ = execute_baseline_rag_query(request.question)
        response_text, llm_token_usage, llm_time = llm_client.generate_response(
            request.question,
            baseline_results
        )

        total_prompt_tokens = llm_token_usage.get("prompt_tokens", 0)
        total_completion_tokens = llm_token_usage.get("completion_tokens", 0)
        tokens_per_second = (
            total_completion_tokens / llm_time if llm_time > 0 else 0.0
        )

        analysis_table = format_analysis_table(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            analysis_time=0.0,
            retrieval_time=baseline_query_time,
            llm_completion_time=llm_time,
            tokens_per_second=tokens_per_second,
            analysis_label="Baseline analysis",
            retrieval_label="Baseline retrieval"
        )

        answer = build_markdown_answer(response_text, baseline_results, analysis_table)
        return ChatResponse(answer=answer)
    except Exception as e:
        print(f"Error processing baseline request: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.post("/api/compare", response_model=CompareResponse)
async def compare(request: ChatRequest):
    """Compare baseline keyword retrieval with GraphRAG."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not db.driver:
        try:
            db.connect()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")

    try:
        baseline_results, baseline_query_time, _ = execute_baseline_rag_query(request.question)
        baseline_text, baseline_token_usage, baseline_llm_time = llm_client.generate_response(
            request.question,
            baseline_results
        )
        baseline_prompt_tokens = baseline_token_usage.get("prompt_tokens", 0)
        baseline_completion_tokens = baseline_token_usage.get("completion_tokens", 0)
        baseline_total_tokens = baseline_prompt_tokens + baseline_completion_tokens
        baseline_tokens_per_second = (
            baseline_completion_tokens / baseline_llm_time if baseline_llm_time > 0 else 0.0
        )
        baseline_table = format_analysis_table(
            prompt_tokens=baseline_prompt_tokens,
            completion_tokens=baseline_completion_tokens,
            analysis_time=0.0,
            retrieval_time=baseline_query_time,
            llm_completion_time=baseline_llm_time,
            tokens_per_second=baseline_tokens_per_second,
            analysis_label="Baseline analysis",
            retrieval_label="Baseline retrieval"
        )
        baseline_answer = build_markdown_answer(baseline_text, baseline_results, baseline_table)

        graphrag_results, analysis_token_usage, analysis_time, query_time = execute_graphrag_query(
            request.question
        )
        graphrag_text, llm_token_usage, llm_time = llm_client.generate_response(
            request.question,
            graphrag_results
        )
        graphrag_prompt_tokens = analysis_token_usage.get("prompt_tokens", 0) + llm_token_usage.get(
            "prompt_tokens", 0
        )
        graphrag_completion_tokens = analysis_token_usage.get(
            "completion_tokens", 0
        ) + llm_token_usage.get("completion_tokens", 0)
        graphrag_total_tokens = graphrag_prompt_tokens + graphrag_completion_tokens
        graphrag_tokens_per_second = (
            llm_token_usage.get("completion_tokens", 0) / llm_time if llm_time > 0 else 0.0
        )
        graphrag_table = format_analysis_table(
            prompt_tokens=graphrag_prompt_tokens,
            completion_tokens=graphrag_completion_tokens,
            analysis_time=analysis_time,
            retrieval_time=query_time,
            llm_completion_time=llm_time,
            tokens_per_second=graphrag_tokens_per_second,
            analysis_label="Term extraction",
            retrieval_label="GraphRAG query"
        )
        graphrag_answer = build_markdown_answer(graphrag_text, graphrag_results, graphrag_table)

        return CompareResponse(
            baseline=ComparisonResult(
                answer=baseline_answer,
                results_count=len(baseline_results),
                metrics=ComparisonMetrics(
                    prompt_tokens=baseline_prompt_tokens,
                    completion_tokens=baseline_completion_tokens,
                    total_tokens=baseline_total_tokens,
                    analysis_time=0.0,
                    retrieval_time=baseline_query_time,
                    llm_time=baseline_llm_time,
                    tokens_per_second=baseline_tokens_per_second
                )
            ),
            graphrag=ComparisonResult(
                answer=graphrag_answer,
                results_count=len(graphrag_results),
                metrics=ComparisonMetrics(
                    prompt_tokens=graphrag_prompt_tokens,
                    completion_tokens=graphrag_completion_tokens,
                    total_tokens=graphrag_total_tokens,
                    analysis_time=analysis_time,
                    retrieval_time=query_time,
                    llm_time=llm_time,
                    tokens_per_second=graphrag_tokens_per_second
                )
            )
        )
    except Exception as e:
        print(f"Error processing comparison request: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "CineGraph API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "chat": "/api/chat",
            "baseline": "/api/baseline",
            "compare": "/api/compare"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

