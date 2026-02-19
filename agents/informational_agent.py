"""
Informational Agent — RAG specialist for automotive product knowledge.

Model  : Claude Sonnet 4.5  (complex reasoning for multi-source synthesis)
Role   : Query Bedrock Knowledge Bases (vehicle manuals, technical docs, past cases),
         and return a cited answer about the vehicle's features or functionality.
Tools  : retrieve_kb  (custom — wraps bedrock-agent-runtime retrieve, handles S3 URIs)
Output : JSON string with answer, sources, and confidence.

Environment variables required:
    KNOWLEDGE_BASE_ID   — Bedrock KB ID (also accepts STRANDS_KNOWLEDGE_BASE_ID as fallback)
    AWS_REGION          — AWS region (defaults to us-east-1)

Knowledge Base content (PoV phase):
    KB-PublicDocs: Vehicle owner manuals and product documentation
                   (currently: 2022 BMW 5 Series user guide)

Optional (for multi-KB routing in future phases):
    KB_VEHICLE_MANUALS_ID       — owner manuals and feature guides
    KB_TECHNICAL_BULLETINS_ID   — service bulletins and recall notices
    KB_PAST_CASES_ID            — resolved support cases (Jira ETL)
"""

import json
import os

import boto3
from strands import Agent, tool

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

INFO_PROMPT = """\
You are an automotive product knowledge specialist for a car manufacturer's customer \
support team. You have access to vehicle owner manuals, feature guides, technical \
documentation, and past resolved support cases.

Your responsibilities:
1. Search the knowledge base using the retrieve_kb tool to find information relevant to
   the customer's question about their vehicle or a vehicle they are considering.
2. Synthesise a clear, accurate answer a human support agent can relay to the customer.
3. Always cite your sources — include the document URI and relevant excerpt.
4. Assess your own confidence (0.0 to 1.0) based on how directly the retrieved
   content answers the question.

Topics you can answer:
- How vehicle features and driver assistance systems work (ACC, lane-keep, parking assist, etc.)
- Dashboard warning lights and instrument cluster indicators
- Vehicle specifications (engine, fuel consumption, towing capacity, dimensions)
- Infotainment, connectivity, and technology features
- Scheduled maintenance intervals and owner care instructions
- Trim levels, packages, and optional equipment differences
- Safety systems and ratings

Output format — respond with ONLY valid JSON, no markdown fences:
{
  "answer": "<complete, customer-friendly response the human agent can send or adapt>",
  "sources": [
    {
      "uri": "<document URI from knowledge base>",
      "text": "<verbatim excerpt that supports the answer>",
      "score": <float 0-1>
    }
  ],
  "confidence": <float 0-1>,
  "notes": "<optional: caveats, model-year limitations, or suggestions for the agent>"
}

Rules:
- When the customer mentions a specific warning light code, feature name, or part number,
  include those exact terms in your search query for accurate lexical matching.
- Retrieve up to 10 results, then synthesise — do not paste raw chunks verbatim.
- If the knowledge base does not contain sufficient information (e.g. a model year not
  yet ingested), set confidence below 0.7 and explain the gap in notes.
- NEVER fabricate specifications, safety ratings, or feature descriptions.
- NEVER recommend specific repair actions — refer the customer to a certified dealer.
"""

# ---------------------------------------------------------------------------
# Custom KB retrieval tool — handles S3-backed Knowledge Bases correctly
# ---------------------------------------------------------------------------


@tool
def retrieve_kb(query: str, max_results: int = 10, min_score: float = 0.4) -> str:
    """
    Search the vehicle knowledge base using semantic retrieval.

    Args:
        query:       The search query — use exact feature names, warning codes, or
                     part numbers from the customer's message for accurate matching.
        max_results: Maximum number of chunks to retrieve (default 10, max 25).
        min_score:   Minimum relevance score 0.0–1.0 to filter low-quality matches
                     (default 0.4).

    Returns:
        JSON string with a list of results: [{uri, text, score}, ...].
        Returns an empty list if no relevant content is found.
    """
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID") or os.environ.get("STRANDS_KNOWLEDGE_BASE_ID")
    print(f"[retrieve_kb] called: query={query!r} kb_id={kb_id!r}", flush=True)
    if not kb_id:
        print("[retrieve_kb] ERROR: no KB ID in environment", flush=True)
        return json.dumps({"error": "KNOWLEDGE_BASE_ID environment variable not set", "results": []})

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-agent-runtime", region_name=region)

    try:
        response = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": min(max_results, 25),
                }
            },
        )
        print(f"[retrieve_kb] got {len(response.get('retrievalResults', []))} raw results", flush=True)
    except Exception as exc:
        print(f"[retrieve_kb] ERROR during retrieve: {exc}", flush=True)
        return json.dumps({"error": str(exc), "results": []})

    results = []
    for chunk in response.get("retrievalResults", []):
        score = chunk.get("score", 0.0)
        if score < min_score:
            continue

        text = chunk.get("content", {}).get("text", "")

        # Extract URI — handle both S3 and CUSTOM data source location types
        location = chunk.get("location", {})
        uri = (
            location.get("s3Location", {}).get("uri")
            or location.get("customDocumentLocation", {}).get("id")
            or "unknown"
        )

        results.append({"uri": uri, "text": text, "score": round(score, 4)})

    return json.dumps({"results": results})


# ---------------------------------------------------------------------------
# Agent-as-Tool
# ---------------------------------------------------------------------------


@tool
def informational_agent(query: str, context: str) -> str:
    """
    Answer vehicle-related questions using Knowledge Base retrieval.

    Use this for INFORMATIONAL requests: questions about vehicle features,
    warning lights, specifications, driver assistance systems, infotainment,
    maintenance schedules, trim differences, or safety systems.

    Args:
        query:   The customer's question (as stated — do not rephrase or simplify).
        context: Customer ID, vehicle VIN/model/year, and conversation history.
                 Include any specific feature names or warning codes mentioned.

    Returns:
        JSON string with keys: answer, sources (list of uri/text/score),
        confidence (0-1), notes.
    """
    prompt = (
        f"Customer and vehicle context:\n{context}\n\n"
        f"Customer question:\n{query}\n\n"
        "Search the vehicle knowledge base for relevant information and return your "
        "answer as JSON per the format in your system prompt."
    )

    agent = Agent(
        model=SONNET,
        system_prompt=INFO_PROMPT,
        tools=[retrieve_kb],
        callback_handler=None,
        trace_attributes={"gen_ai.agent.name": "informational"},
    )

    response = agent(prompt)
    return str(response)
