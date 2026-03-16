"""
llm_local.py — Shared local LLM helper using Ollama.

Two models are used:
  - llama3.2        : text generation (chatbot, diet plan, health summary)
  - qwen2.5vl       : image understanding (prescription & lab report reading)

Requires:  pip install ollama
           ollama serve
           ollama pull llama3.2
           ollama pull qwen2.5vl
"""

import io
import json
import re
import base64
import logging
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import ollama

# ---------- CONFIG ----------
OLLAMA_MODEL        = "qwen2.5vl"         # text-only model for chat / diet / summaries
OLLAMA_VISION_MODEL = "qwen2.5vl"  # vision model for prescription & lab report images

logger = logging.getLogger(__name__)


# ---------- HELPERS ----------
def _pil_to_base64(img: Image.Image) -> str:
    """Convert a PIL Image to a base64-encoded PNG string for Ollama vision API."""
    buf = io.BytesIO()
    # Save as PNG; convert mode if needed (RGBA or palette → RGB)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _clean_json(raw: str) -> dict:
    """Strip markdown fences and extract the first JSON object/array from raw text."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.MULTILINE).strip()
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if match:
        cleaned = match.group(1)
    return json.loads(cleaned)


# ---------- VISION CALL (prescription & lab report) ----------
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
def _vision_chat_with_retry(image_b64: str, prompt: str) -> str:
    """Send an image + prompt to vision model and return raw text."""
    try:
        response = ollama.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_b64]   # base64-encoded image
            }],
            format="json"               # request JSON output
        )
        return response["message"]["content"]
    except Exception as e:
        logger.warning(f"⚠️ Vision model call failed (will retry): {e}")
        raise


def vision_analyze(img: Image.Image, prompt: str) -> dict:
    """
    Send a PIL image and a prompt to vision model.
    Returns a parsed dict from the model's JSON response.

    Args:
        img    : PIL Image (any mode — auto-converted to RGB PNG)
        prompt : Instruction prompt for the vision model

    Raises:
        RuntimeError        : If vision model fails after 3 attempts
        json.JSONDecodeError: If the model returns malformed JSON
    """
    image_b64 = _pil_to_base64(img)
    try:
        raw = _vision_chat_with_retry(image_b64, prompt)
    except Exception as e:
        raise RuntimeError(
            f"❌ Vision LLM (Ollama/{OLLAMA_VISION_MODEL}) failed after 3 attempts: {e}\n"
            f"   Make sure Ollama is running and the model is pulled: "
            f"'ollama pull {OLLAMA_VISION_MODEL}'"
        )

    try:
        return _clean_json(raw)
    except json.JSONDecodeError:
        logger.error(f"❌ Vision model returned invalid JSON:\n{raw[:500]}")
        raise


# ---------- TEXT CALL (chat / diet / summary) ----------
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
def _chat_with_retry(prompt: str, json_mode: bool = False) -> str:
    """Call llama3.2 text model and return raw text response."""
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


def llm_generate(prompt: str, json_mode: bool = False):
    """
    Generate a response from the local Ollama text LLM (llama3.2).

    Args:
        prompt    : The full prompt to send.
        json_mode : If True, strip markdown fences and parse JSON.
                    Returns a dict. If False, returns plain text string.

    Raises:
        RuntimeError       : If Ollama server is not reachable.
        json.JSONDecodeError: If json_mode=True and the model returns bad JSON.
    """
    try:
        raw = _chat_with_retry(prompt, json_mode)
    except Exception as e:
        raise RuntimeError(
            f"❌ Local LLM (Ollama/{OLLAMA_MODEL}) failed after 3 attempts: {e}\n"
            f"   Make sure Ollama is running ('ollama serve') and model is pulled "
            f"('ollama pull {OLLAMA_MODEL}')."
        )

    if not json_mode:
        return raw

    try:
        return _clean_json(raw)
    except json.JSONDecodeError:
        logger.error(f"❌ LLM returned invalid JSON. Raw output:\n{raw[:500]}")
        raise


# ---------- SIMPLE SELF-TEST ----------
if __name__ == "__main__":
    import sys
    print(f"Testing text LLM ({OLLAMA_MODEL})...")
    try:
        answer = llm_generate("Say 'hello' in 3 different languages. Keep it short.")
        print("✅ Text LLM responded:\n", answer)
    except Exception as e:
        print(f"❌ Text LLM test failed: {e}")
        sys.exit(1)

    print(f"\nVision model: {OLLAMA_VISION_MODEL}")
    print(f"(Pull with: ollama pull {OLLAMA_VISION_MODEL})")
