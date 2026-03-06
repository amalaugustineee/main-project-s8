"""
llm_local.py — Shared local LLM helper using Ollama.

Replaces Google Gemini cloud API.
Requires:  pip install ollama
           Ollama server running at http://localhost:11434  (ollama serve)
           Model pulled: ollama pull llama3.2
"""

import json
import re
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import ollama

# ---------- CONFIG ----------
OLLAMA_MODEL = "llama3.2"   # Change to "mistral" or "llama3" if you pulled a different model

logger = logging.getLogger(__name__)

# ---------- RETRY-WRAPPED GENERATION ----------
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
def _chat_with_retry(prompt: str, json_mode: bool = False) -> str:
    """Call Ollama and return raw text response."""
    try:
        kwargs = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        if json_mode:
            kwargs["format"] = "json"
            
        response = ollama.chat(**kwargs)
        return response["message"]["content"]
    except Exception as e:
        logger.warning(f"⚠️ Ollama call failed (will retry): {e}")
        raise


# ---------- PUBLIC INTERFACE ----------
def llm_generate(prompt: str, json_mode: bool = False):
    """
    Generate a response from the local Ollama LLM.

    Args:
        prompt (str): The full prompt to send.
        json_mode (bool): If True, strip markdown fences and parse JSON.
                          Returns a dict. If False, returns plain text string.

    Raises:
        RuntimeError: If Ollama server is not reachable.
        json.JSONDecodeError: If json_mode=True and the model returns bad JSON.
    """
    try:
        raw = _chat_with_retry(prompt, json_mode)
    except Exception as e:
        raise RuntimeError(
            f"❌ Local LLM (Ollama/{OLLAMA_MODEL}) failed after 3 attempts: {e}\n"
            f"   Make sure Ollama is running ('ollama serve') and model is pulled ('ollama pull {OLLAMA_MODEL}')."
        )

    if not json_mode:
        return raw

    # Strip markdown code fences that the model may wrap JSON in
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.MULTILINE).strip()

    # If the model returned extra prose before the JSON, try to extract just the JSON block
    # Look for the first { ... } or [ ... ] block
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if match:
        cleaned = match.group(1)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(f"❌ LLM returned invalid JSON. Raw output:\n{raw[:500]}")
        raise


# ---------- SIMPLE SELF-TEST ----------
if __name__ == "__main__":
    import sys
    print(f"Testing local LLM ({OLLAMA_MODEL})...")
    try:
        answer = llm_generate("Say 'hello' in 3 different languages. Keep it short.")
        print("✅ LLM responded:\n", answer)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
