"""
LLM-powered analysis using Groq API (llama-3.1-8b-instant — free tier).
Returns a structured JSON describing the problem variant, constraints, etc.
"""
from __future__ import annotations

import json
from typing import Literal

from app.core.config import settings

UploadKind = Literal["dataset", "algorithm", "metric"]

_SYSTEM_PROMPT = """You are an expert in combinatorial optimization and vehicle routing problems (VRP, PDPTW, TSP, CVRP, etc.).

Your task is to analyze uploaded file content and determine whether it is related to combinatorial optimization / vehicle routing.

IMPORTANT RULES:
1. If the file content is clearly NOT related to vehicle routing or combinatorial optimization (e.g. it is source code for a compiler, web app, general algorithm, or unrelated problem), set problem_variant to "Unknown", description to "File không liên quan đến bài toán tối ưu hóa tổ hợp hoặc định tuyến xe", and leave all list fields EMPTY.
2. Only identify a specific problem variant if you are confident the content is about vehicle routing / logistics / combinatorial optimization.
3. Respond ONLY with a valid JSON object — no markdown, no explanation outside JSON.
4. CRITICAL: problem_variant MUST be exactly one of these three values: "PDPTW", "2E-VRP", or "Unknown".
   - Use "PDPTW" for: Pickup and Delivery with Time Windows, PDPTW, PDP, any pickup-delivery variant.
   - Use "2E-VRP" for: Two-Echelon VRP, 2E-VRP, 2EVRP, multi-echelon routing, satellite-based routing, city logistics with depots and satellites, any two-echelon or multi-echelon variant.
   - Use "Unknown" for anything else (CVRP, TSP, VRPTW without pickup-delivery, unrecognized, or unrelated).
   Do NOT invent other variant names.

The JSON must have exactly these fields:
{
  "problem_variant": "PDPTW" | "2E-VRP" | "Unknown",
  "description": "1-3 sentence plain-language description",
  "hard_constraints": ["list", "of", "hard", "constraints"],
  "soft_constraints": ["list", "of", "soft", "objectives"],
  "dataset_format": "format name if dataset, e.g. Sartori & Buriol, Li & Lim, Solomon, Ropke & Cordeau, or N/A",
  "reference_papers": ["Author Year - Title (if recognizable, else empty list)"],
  "flow_steps": [
    {
      "phase": "Step name (max 6 words)",
      "description": "1-2 sentences describing what this phase does",
      "loop": false,
      "components": [
        {"name": "Component name", "desc": "What this component does (1 sentence)"}
      ]
    }
  ]
}

Rules for flow_steps:
- For algorithms: list the main execution phases in order (e.g. initialization, main loop, acceptance, output). Last step should have "loop": true if it cycles back.
- For datasets or metrics: set flow_steps to an empty array [].
- components can be empty [] if the phase has no sub-components.

Never add extra fields. hard_constraints and soft_constraints must be lists (can be empty if Unknown).
Respond with JSON only, no markdown fences."""

_PROMPTS: dict[UploadKind, str] = {
    "dataset": (
        "The following is the content of an uploaded file. "
        "Determine if it is a benchmark dataset for a vehicle routing or combinatorial optimization problem. "
        "If it is not (e.g. it is source code, a report, or unrelated data), return problem_variant='Unknown'.\n\n"
        "FILE CONTENT:\n{content}"
    ),
    "algorithm": (
        "The following is source code of an uploaded algorithm. "
        "Determine if it implements a solver for a vehicle routing or combinatorial optimization problem. "
        "If it is not (e.g. it is a compiler, web app, or unrelated program), return problem_variant='Unknown'.\n\n"
        "FILE CONTENT:\n{content}"
    ),
    "metric": (
        "The following is source code of an uploaded metric/evaluation plugin. "
        "Determine if it evaluates solutions for a vehicle routing or combinatorial optimization problem. "
        "If it is not, return problem_variant='Unknown'.\n\n"
        "FILE CONTENT:\n{content}"
    ),
}


def analyze(content_map: dict[str, str], kind: UploadKind) -> dict:
    """
    Call Groq to analyze uploaded content.

    content_map: { relative_filename: text_content }
    kind: "dataset" | "algorithm" | "metric"

    Returns parsed analysis dict.
    Raises RuntimeError on API failure.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    from groq import Groq  # type: ignore

    client = Groq(api_key=settings.GROQ_API_KEY)

    # Build combined content string
    if len(content_map) == 1:
        combined = next(iter(content_map.values()))
    else:
        parts = [f"=== {fname} ===\n{text}" for fname, text in content_map.items()]
        combined = "\n\n".join(parts)

    # Truncate to ~6k chars (~1500 tokens)
    if len(combined) > 6_000:
        combined = combined[:6_000] + "\n...[truncated]"

    user_prompt = _PROMPTS[kind].format(content=combined)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if model added them anyway
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}\nRaw: {raw[:500]}")

    # Ensure required fields exist with fallbacks
    result.setdefault("problem_variant", "Unknown")
    result.setdefault("description", "")
    result.setdefault("hard_constraints", [])
    result.setdefault("soft_constraints", [])
    result.setdefault("dataset_format", "N/A")
    result.setdefault("reference_papers", [])

    # Normalize problem_variant to supported values only
    _SUPPORTED = {"PDPTW", "2E-VRP", "Unknown"}
    pv = str(result.get("problem_variant", "")).strip()
    if pv not in _SUPPORTED:
        # Best-effort mapping: look for known keywords
        pv_upper = pv.upper().replace("-", "").replace(" ", "")
        if "2E" in pv_upper or "ECHELON" in pv_upper or "SATELLITE" in pv_upper:
            result["problem_variant"] = "2E-VRP"
        elif "PDPTW" in pv_upper or "PICKUP" in pv_upper or "DELIVERY" in pv_upper:
            result["problem_variant"] = "PDPTW"
        else:
            result["problem_variant"] = "Unknown"

    return result
