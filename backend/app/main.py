"""FastAPI application entry point."""
import os
import asyncio
import json
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


class ComparisonResult(BaseModel):
    answer: str
    results_count: int


class CompareResponse(BaseModel):
    baseline: ComparisonResult
    graphrag: ComparisonResult


class EvalRequest(BaseModel):
    question: str


class EvalPipelineResult(BaseModel):
    response_text: str
    answer_markdown: str
    contexts: List[str]
    retrieved: List[Dict[str, Any]]


class EvalCompareResponse(BaseModel):
    question: str
    baseline: EvalPipelineResult
    graphrag: EvalPipelineResult


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


def build_markdown_answer(response_text: str, movies: List[Dict[str, Any]]) -> str:
    """Build a markdown response with commentary and filmography."""
    markdown_parts = []

    markdown_parts.append("# Commentary\n")
    markdown_parts.append(response_text)
    markdown_parts.append("\n\n")

    markdown_parts.append("# Matching Filmography\n")
    markdown_parts.append(format_movies_as_markdown_table(movies))

    return "\n".join(markdown_parts)


def build_contexts_from_records(records: List[Dict[str, Any]]) -> List[str]:
    """
    Convert retrieved records into a list of context strings for evaluation tools (e.g., RAGAS).
    """
    contexts: List[str] = []
    for record in records:
        try:
            contexts.append(json.dumps(record, ensure_ascii=False))
        except Exception:
            contexts.append(str(record))
    return contexts


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
        graphrag_results, _, _, _ = execute_graphrag_query(request.question)
        
        # Generate natural language response (returns response_text, token_usage, elapsed_time)
        response_text, _, _ = llm_client.generate_response(request.question, graphrag_results)
        answer = build_markdown_answer(response_text, graphrag_results)

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
        response_text, _, _ = llm_client.generate_response(
            request.question,
            baseline_results
        )
        _ = baseline_query_time  # kept for possible future instrumentation
        answer = build_markdown_answer(response_text, baseline_results)
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
        baseline_text, _, _ = llm_client.generate_response(
            request.question,
            baseline_results
        )
        _ = baseline_query_time  # kept for possible future instrumentation
        baseline_answer = build_markdown_answer(baseline_text, baseline_results)

        graphrag_results, _, _, _ = execute_graphrag_query(
            request.question
        )
        graphrag_text, _, _ = llm_client.generate_response(
            request.question,
            graphrag_results
        )
        graphrag_answer = build_markdown_answer(graphrag_text, graphrag_results)

        return CompareResponse(
            baseline=ComparisonResult(
                answer=baseline_answer,
                results_count=len(baseline_results)
            ),
            graphrag=ComparisonResult(
                answer=graphrag_answer,
                results_count=len(graphrag_results)
            )
        )
    except Exception as e:
        print(f"Error processing comparison request: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.post("/api/eval/baseline", response_model=EvalPipelineResult)
async def eval_baseline(request: EvalRequest):
    """Evaluation-friendly baseline endpoint returning contexts and retrieved items."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not db.driver:
        try:
            db.connect()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")

    baseline_results, _, _ = execute_baseline_rag_query(request.question)
    response_text, _, _ = llm_client.generate_response(request.question, baseline_results)
    answer_markdown = build_markdown_answer(response_text, baseline_results)
    return EvalPipelineResult(
        response_text=response_text,
        answer_markdown=answer_markdown,
        contexts=build_contexts_from_records(baseline_results),
        retrieved=baseline_results
    )


@app.post("/api/eval/graphrag", response_model=EvalPipelineResult)
async def eval_graphrag(request: EvalRequest):
    """Evaluation-friendly GraphRAG endpoint returning contexts and retrieved items."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not db.driver:
        try:
            db.connect()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")

    graphrag_results, _, _, _ = execute_graphrag_query(request.question)
    response_text, _, _ = llm_client.generate_response(request.question, graphrag_results)
    answer_markdown = build_markdown_answer(response_text, graphrag_results)
    return EvalPipelineResult(
        response_text=response_text,
        answer_markdown=answer_markdown,
        contexts=build_contexts_from_records(graphrag_results),
        retrieved=graphrag_results
    )


@app.post("/api/eval/compare", response_model=EvalCompareResponse)
async def eval_compare(request: EvalRequest):
    """Evaluation-friendly compare endpoint returning both pipelines with contexts."""
    baseline = await eval_baseline(request)
    graphrag = await eval_graphrag(request)
    return EvalCompareResponse(question=request.question, baseline=baseline, graphrag=graphrag)

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

