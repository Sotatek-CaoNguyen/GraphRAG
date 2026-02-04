# CineGraph - Movie GraphRAG Application

CineGraph is an AI-powered movie query application that uses Neo4j GraphRAG to index and query movie entities and relationships. Users can ask questions about movies, actors, directors, writers, and genres through a Next.js web interface, receiving natural language responses.


## Features

- GraphRAG pipeline using Neo4j relationships.
- Baseline keyword RAG for comparison testing.
- Compare mode returns side-by-side answers and metrics.
- Next.js chat UI with GraphRAG/Baseline/Compare toggle.

## Architecture

The application consists of 4 core components orchestrated via Docker Compose:

1. Neo4j - Graph database storing movie entities and relationships.
2. Python Backend API - FastAPI service handling GraphRAG, baseline retrieval, CSV import, and LLM calls.
3. Next.js Frontend - Chat UI for user interactions.
4. OpenRouter API - LLM inference provider.

## Prerequisites

- Docker and Docker Compose
- An API key from https://openrouter.ai/

## Project Structure

```
.
|-- docker-compose.yml
|-- .env
|-- README.md
|-- backend/
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- movies.csv
|   |-- app/
|       |-- main.py
|       |-- database.py
|       |-- csv_importer.py
|       |-- graphrag.py
|       |-- baseline_rag.py
|       |-- llm_client.py
|-- frontend/
|   |-- Dockerfile
|   |-- package.json
|   |-- src/
|       |-- app/
|       |   |-- api/
|       |   |   |-- chat/
|       |   |   |-- baseline/
|       |   |   |-- compare/
|       |   |-- components/
|           |-- ChatInterface.tsx
```

## Graph Schema

### Nodes
- Movie: imdb_title_id, original_title, year, duration, description, avg_vote, votes
- Person: name (actors, directors, writers)
- Genre: name
- ProductionCompany: name

### Relationships
- ACTED_IN (Person -> Movie)
- DIRECTED (Person -> Movie)
- WROTE (Person -> Movie)
- HAS_GENRE (Movie -> Genre)
- PRODUCED_BY (Movie -> ProductionCompany)

## Setup Instructions

1. Set up OpenRouter API Key:
   Create a file named `.env` in the root of the project directory and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY="your_openrouter_api_key_here"
   ```
   The `docker-compose.yml` file is configured to read this file.

2. Place the CSV file:
   Ensure `backend/movies.csv` exists.

3. Start the services:
   ```bash
   docker compose up -d --build
   ```

4. Wait for services to initialize:
   - Neo4j will start on port 7474 (HTTP) and 7687 (Bolt).
   - The backend will import CSV data if the graph is empty.
   - The frontend will be available on port 3000.

5. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Neo4j Browser: http://localhost:7474 (use credentials `neo4j`/`cinegraph123`)

## UI Modes

The chat interface includes three modes, selectable in the header toggle:

- GraphRAG: graph-based retrieval only.
- Baseline: keyword retrieval only (title/description matching).
- Compare: shows baseline vs GraphRAG answers with timing/tokens side-by-side.

## API Endpoints

### POST /api/chat
GraphRAG pipeline.

Request:
```json
{
  "question": "Which Crime movies are Joe Pesci in?"
}
```

Response (truncated):
```json
{
  "answer": "# Commentary\n..."
}
```

### POST /api/baseline
Baseline keyword retrieval (title/description matching) + LLM response.

Request:
```json
{
  "question": "Which films directed by Christopher Nolan was Christian Bale in?"
}
```

Response (truncated):
```json
{
  "answer": "# Commentary\n..."
}
```

### POST /api/compare
Returns baseline and GraphRAG answers with metrics for side-by-side comparison.

Request:
```json
{
  "question": "What movies are about Frodo?"
}
```

Response (truncated):
```json
{
  "baseline": {
    "answer": "# Commentary\n...",
    "results_count": 12,
    "metrics": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "total_tokens": 0,
      "analysis_time": 0.0,
      "retrieval_time": 0.15,
      "llm_time": 0.0,
      "tokens_per_second": 0.0
    }
  },
  "graphrag": {
    "answer": "# Commentary\n...",
    "results_count": 5,
    "metrics": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "total_tokens": 0,
      "analysis_time": 0.2,
      "retrieval_time": 0.12,
      "llm_time": 0.0,
      "tokens_per_second": 0.0
    }
  }
}
```

### GET /api/health
Check the health status of all services.

Response:
```json
{
  "status": "healthy",
  "neo4j_connected": true,
  "openrouter_available": true,
  "graph_has_data": true
}
```

## Configuration

### Environment Variables

Backend:
- NEO4J_URI: Neo4j connection URI (default: `neo4j://neo4j:7687`)
- NEO4J_USER: Neo4j username (default: `neo4j`)
- NEO4J_PASSWORD: Neo4j password (default: `cinegraph123`)
- OPENROUTER_API_KEY: API key for OpenRouter (read from `.env`).

Frontend:
- BACKEND_URL: Backend API URL (default: `http://backend:8000`)

## Troubleshooting

1. Neo4j connection errors: wait for Neo4j to fully initialize. Check logs with `docker compose logs neo4j`.
2. CSV import not working: verify `backend/movies.csv` exists and has the correct format.
3. No LLM response: ensure `OPENROUTER_API_KEY` is valid and active.

## Technical Stack

- Backend: Python 3.11+, FastAPI, neo4j-driver, pandas, httpx
- Frontend: Next.js 14+, TypeScript, React
- Database: Neo4j 5.15
- LLM: OpenRouter API
- Orchestration: Docker Compose
