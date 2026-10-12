"""LLM calls over the OpenAI-compatible chat API (OpenRouter by default).

One vision-capable model reads each document: the PDF's text layer plus images
of any scanned pages go in, schema-validated JSON comes out. The model only
extracts; verifier.py decides. Point LLM_BASE_URL at http://localhost:11434/v1
to run the same calls on a local Ollama model instead.
"""
import base64
import json
import time
from typing import Any, Dict, List

import httpx

from .config import settings
from .models import Extraction

PROMPT = """You extract fields from one health-insurance claim document. Rules:
- Use null when a value is not in the document. Never invent numbers, names or dates.
- Copy itemized charge descriptions and amounts exactly as printed; amounts are plain numbers.
- Dates as YYYY-MM-DD when unambiguous (Indian documents are day-first), otherwise copy them as printed.
- Only invoices have itemized_charges and total_amount; for every other type use [] and null.
- Policy documents: fill policy_number, validity dates, coverage_limit, deductible, exclusions,
  required_documents (document names only) and policy_clauses (verbatim clause text). Their
  admission/discharge/invoice dates and invoice_number are null.
- Scanned pages are attached as images; read them as carefully as the text.
- confidence: 0.9 when everything is clearly legible, below 0.5 if parts are illegible or cut off.

FILE: {filename}
TEXT LAYER:
{text}"""


def _strict(schema: Dict[str, Any]) -> Dict[str, Any]:
    """OpenAI-style strict schemas need additionalProperties=false and every key required."""
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    return schema


SCHEMA = _strict(Extraction.model_json_schema())


class LLMError(RuntimeError):
    pass


def _chat(messages: List[dict], **extra) -> str:
    if not configured():
        raise LLMError("OPENROUTER_API_KEY is not set in backend/.env")
    body = {"model": settings.llm_model, "messages": messages, "temperature": 0,
            # Only route to providers that don't collect prompt data (health records).
            "provider": {"data_collection": "deny", "require_parameters": True}, **extra}
    if settings.llm_reasoning:  # reasoning models spend output tokens thinking; keep it short
        body["reasoning"] = {"effort": settings.llm_reasoning, "exclude": True}
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "X-Title": "Kaagaz"}
    for attempt in range(3):
        try:
            r = httpx.post(f"{settings.llm_base_url.rstrip('/')}/chat/completions", json=body,
                           headers=headers, timeout=settings.llm_timeout_s)
        except httpx.TransportError as e:
            if attempt == 2:
                raise LLMError(f"LLM service unreachable ({e})") from e
        else:
            if r.status_code == 200:
                data = r.json()
                if data.get("error"):
                    raise LLMError(str(data["error"].get("message", data["error"])))
                choice = data["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise LLMError("The model ran out of output tokens; try again or use a model with less reasoning.")
                return choice["message"]["content"] or ""
            if r.status_code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                try:
                    msg = r.json()["error"]["message"]
                except Exception:
                    msg = r.text[:300]
                raise LLMError(f"LLM request failed ({r.status_code}): {msg}")
        time.sleep(3 * (attempt + 1))
    raise LLMError("LLM request failed")


def extract(text: str, images: List[bytes], filename: str) -> Dict[str, Any]:
    """Document text + scanned-page JPEGs -> dict matching Extraction. Raises LLMError."""
    content: List[dict] = [{"type": "text", "text": PROMPT.format(filename=filename, text=text[:60000] or "(none)")}]
    content += [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(i).decode()}}
                for i in images]
    raw = _chat([{"role": "user", "content": content}], max_tokens=12000,
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "extraction", "strict": True, "schema": SCHEMA}})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model returned invalid JSON for {filename}") from e
    if not isinstance(data, dict):
        raise LLMError(f"Model returned non-object JSON for {filename}")
    return data


def explain_clause(clause: str) -> str:
    return _chat([{"role": "user", "content":
                   "Explain in 2-4 plain sentences what this health-insurance policy clause means for a "
                   f"claim reviewer. Explain only what the clause says; do not add terms.\nCLAUSE: {clause[:2000]}"}],
                 max_tokens=2000).strip()


def configured() -> bool:
    return bool(settings.openrouter_api_key) or "openrouter.ai" not in settings.llm_base_url
