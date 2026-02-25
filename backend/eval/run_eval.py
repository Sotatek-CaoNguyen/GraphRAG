import argparse
import json
import os
import statistics
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx


def load_env():
    """
    Load environment variables from a local .env file if present.
    This keeps evaluation runnable even when keys are only provided via docker-compose/.env.
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def call_eval_compare(client: httpx.Client, base_url: str, question: str) -> Tuple[Dict[str, Any], float]:
    start = time.perf_counter()
    r = client.post(f"{base_url}/api/eval/compare", json={"question": question})
    r.raise_for_status()
    elapsed = time.perf_counter() - start
    return r.json(), elapsed


def summarize_latencies(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {}
    lat_sorted = sorted(latencies)
    return {
        "count": float(len(lat_sorted)),
        "mean": statistics.mean(lat_sorted),
        "p50": lat_sorted[len(lat_sorted) // 2],
        "p95": lat_sorted[int(len(lat_sorted) * 0.95) - 1],
        "max": max(lat_sorted),
    }


def try_ragas_eval(
    questions: List[str],
    answers: List[str],
    contexts: List[List[str]],
    references: Optional[List[str]] = None,
):
    """
    Optional RAGAS evaluation.

    This function is best-effort because RAGAS configuration depends on your environment:
    - LLM/embeddings provider
    - API keys
    - RAGAS version
    """
    try:
        from datasets import Dataset  # type: ignore
        from ragas import evaluate  # type: ignore
        # Use v1 metrics (Metric objects) compatible with `ragas.evaluate`.
        from ragas.metrics._faithfulness import faithfulness  # type: ignore
        from ragas.metrics._context_precision import context_precision  # type: ignore
        from ragas.metrics._answer_relevance import answer_relevancy  # type: ignore
        from ragas.metrics._context_recall import context_recall  # type: ignore
        from openai import OpenAI  # type: ignore
        from openai import AuthenticationError  # type: ignore
        from ragas.llms import llm_factory  # type: ignore
        from ragas.embeddings import _embedding_factory  # type: ignore
    except Exception as e:
        print("RAGAS not available in this Python environment.")
        print("Install deps with: pip install -r backend/requirements-eval.txt")
        if "anthropic" in str(e).lower():
            print("Note: RAGAS may import optional providers; install missing module with: pip install anthropic")
        print(f"Import error: {e}")
        return None

    def _redact_key(key: str) -> str:
        key = (key or "").strip()
        if len(key) <= 10:
            return "***"
        return f"{key[:6]}...{key[-4:]}"

    openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENROUTER_BASE_URL")
    if not openai_base_url and (os.getenv("OPENROUTER_API_KEY") or "").strip():
        openai_base_url = "https://openrouter.ai/api/v1"
    llm_model = os.getenv("OPENAI_MODEL") or os.getenv("OPENROUTER_MODEL") or os.getenv("RAGAS_LLM_MODEL") or "gpt-4o-mini"
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL") or os.getenv("RAGAS_EMBEDDING_MODEL") or "text-embedding-3-small"

    if not openai_api_key:
        print("RAGAS requires OPENAI_API_KEY (or OPENROUTER_API_KEY).")
        print("Example (PowerShell):")
        print('  $env:OPENAI_API_KEY = \"<your_openrouter_api_key>\"')
        print('  $env:OPENAI_BASE_URL = \"https://openrouter.ai/api/v1\"')
        print('  $env:OPENAI_MODEL = \"google/gemini-3-flash-preview\"')
        return None

    openai_client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
    llm = llm_factory(llm_model, provider="openai", client=openai_client)

    embeddings = None
    try:
        embeddings = _embedding_factory(
            provider="openai",
            model=embedding_model,
            client=openai_client,
        )
    except Exception as e:
        print("Warning: failed to initialize embeddings for RAGAS (AnswerRelevancy will be skipped).")
        print(f"Embeddings init error: {e}")

    # Quick auth sanity check to reduce confusing downstream errors.
    # This makes a tiny request to the LLM provider (costs a few tokens).
    try:
        openai_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=3,
        )
    except AuthenticationError as e:
        print("RAGAS LLM authentication failed.")
        print(f"- base_url: {openai_base_url}")
        print(f"- model: {llm_model}")
        print(f"- api_key: {_redact_key(openai_api_key)}")
        print("Fix (OpenRouter, PowerShell):")
        print("  $env:OPENAI_API_KEY = $env:OPENROUTER_API_KEY")
        print('  $env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"')
        print(f'  $env:OPENAI_MODEL = "{llm_model}"')
        print(f"Auth error: {e}")
        return None
    except Exception as e:
        print("Warning: RAGAS LLM connectivity check failed; continuing anyway.")
        print(f"Check error: {e}")

    data: Dict[str, Any] = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
    }
    if references is not None:
        # RAGAS v0.4 expects `reference` for reference/ground-truth answers.
        data["reference"] = references

    dataset = Dataset.from_dict(data)

    # With no reference answers, we can still compute:
    # - faithfulness (answer grounded in retrieved contexts)
    # - answer_relevancy (question vs answer) if embeddings are available
    selected_metrics = [faithfulness]
    if embeddings is not None:
        selected_metrics.append(answer_relevancy)

    # Context-based metrics (precision/recall) require reference answers.
    if references is not None:
        selected_metrics.append(context_precision)
        selected_metrics.append(context_recall)

    result = evaluate(dataset, metrics=selected_metrics, llm=llm, embeddings=embeddings)
    return result


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Run evaluation batch for CineGraph (Baseline vs GraphRAG).")
    parser.add_argument("--base-url", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--input", required=True, help="Path to eval questions JSONL.")
    parser.add_argument("--output", default="eval_outputs.jsonl", help="Where to write per-question outputs.")
    parser.add_argument("--summary", default="eval_summary.json", help="Where to write summary JSON.")
    parser.add_argument("--ragas", action="store_true", help="Run RAGAS evaluation (requires extra deps + provider config).")
    parser.add_argument("--limit", type=int, default=0, help="Only run the first N questions (0 = all).")
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    client = httpx.Client(timeout=120.0)

    outputs: List[Dict[str, Any]] = []
    total_latencies: List[float] = []

    try:
        from tqdm import tqdm  # type: ignore

        iterator = tqdm(rows, desc="Eval", unit="q")
    except Exception:
        iterator = rows

    for row in iterator:
        question = row.get("question")
        if not question:
            continue

        payload, elapsed = call_eval_compare(client, args.base_url, question)
        total_latencies.append(elapsed)

        outputs.append({
            "id": row.get("id"),
            "type": row.get("type"),
            "question": question,
            "ground_truth": row.get("ground_truth"),
            "elapsed_total": elapsed,
            "baseline": payload["baseline"],
            "graphrag": payload["graphrag"],
        })

    write_jsonl(args.output, outputs)

    summary: Dict[str, Any] = {
        "base_url": args.base_url,
        "input": args.input,
        "output": args.output,
        "latency_total": summarize_latencies(total_latencies),
        "count": len(outputs),
    }

    if args.ragas and outputs:
        questions = [o["question"] for o in outputs]

        baseline_answers = [o["baseline"]["response_text"] for o in outputs]
        baseline_contexts = [o["baseline"]["contexts"] for o in outputs]

        graphrag_answers = [o["graphrag"]["response_text"] for o in outputs]
        graphrag_contexts = [o["graphrag"]["contexts"] for o in outputs]

        references = [o.get("ground_truth") for o in outputs]
        if all(isinstance(r, str) and r.strip() for r in references):
            refs: Optional[List[str]] = [str(r) for r in references]  # type: ignore
        else:
            refs = None

        summary["ragas"] = {}
        summary["ragas"]["baseline"] = str(try_ragas_eval(questions, baseline_answers, baseline_contexts, refs))
        summary["ragas"]["graphrag"] = str(try_ragas_eval(questions, graphrag_answers, graphrag_contexts, refs))

    with open(args.summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Wrote outputs: {args.output}")
    print(f"Wrote summary: {args.summary}")


if __name__ == "__main__":
    main()
