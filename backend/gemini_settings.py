import json
import os
import warnings

# Override with GEMINI_MODEL in .env if your API key supports a different model.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Default false so demo works without Gemini quota. Set USE_GEMINI=true when key has quota.
_use_gemini_env = os.getenv("USE_GEMINI", "false").lower()
GEMINI_QUOTA_EXHAUSTED = False


def is_gemini_enabled() -> bool:
    """Whether to call the Gemini API (key present, not disabled, quota not exhausted)."""
    if _use_gemini_env in ("0", "false", "no", "off"):
        return False
    if GEMINI_QUOTA_EXHAUSTED:
        return False
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def mark_gemini_quota_exhausted() -> None:
    """Stop further Gemini calls this process after a 429/quota error."""
    global GEMINI_QUOTA_EXHAUSTED
    GEMINI_QUOTA_EXHAUSTED = True


def is_quota_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate" in msg


def handle_gemini_error(exc: BaseException, context: str) -> None:
    if is_quota_error(exc):
        mark_gemini_quota_exhausted()
        print(f"{context}: Gemini quota exceeded — using fallbacks. Set USE_GEMINI=false in .env to silence.")
    else:
        print(f"{context}: {exc}")


def _generate_content(prompt: str, temperature: float = 0.2, json_mode: bool = True) -> str | None:
    """Lazy-load deprecated SDK only when needed; suppress FutureWarning on import."""
    if not is_gemini_enabled():
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(GEMINI_MODEL)
        config_kwargs = {"temperature": temperature}
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        config = genai.types.GenerationConfig(**config_kwargs)
        response = model.generate_content(prompt, generation_config=config)
        return (response.text or "").strip()
    except Exception as e:
        handle_gemini_error(e, "Gemini API")
        return None


def generate_json(prompt: str, temperature: float = 0.2) -> dict | None:
    """Call Gemini and parse JSON response. Returns None on failure/disabled."""
    text = _generate_content(prompt, temperature=temperature, json_mode=True)
    if not text:
        return None
    try:
        cleaned = text
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        handle_gemini_error(e, "Gemini JSON parse")
        return None


def generate_text(prompt: str, temperature: float = 0.3) -> str | None:
    """Call Gemini for plain text. Returns None on failure/disabled."""
    return _generate_content(prompt, temperature=temperature, json_mode=False)


# Back-compat: callers that passed a "client" can ignore it; use helpers above instead.
def get_gemini_client():
    """Deprecated shim — returns a sentinel if Gemini is enabled, else None."""
    return object() if is_gemini_enabled() else None
