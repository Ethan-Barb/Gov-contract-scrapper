"""Groq LLM summarizer."""
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def summarize_8k(text: str, items: list[str], api_key: str, model: str) -> str:
    if not text or len(text.strip()) < 50:
        return f"Filed 8-K with Items: {', '.join(items)}"

    prompt = (
        "You summarize SEC 8-K filings. Output ONE plain sentence, max 30 words. "
        "State what specifically happened and why it matters. "
        "No preamble, no quotes, no markdown - just the sentence."
    )
    user_msg = f"8-K Items reported: {', '.join(items)}\n\nFiling excerpt:\n{text[:3500]}"
    return _chat(prompt, user_msg, api_key, model, max_tokens=100)


def summarize_contract(description: str, api_key: str, model: str) -> str:
    if not description or len(description.strip()) < 20:
        return "No description available."
    prompt = (
        "You summarize US government contract awards in EXACTLY ONE sentence "
        "of at most 25 words. Be specific about what work is being performed. "
        "No preamble, no quotes, no markdown - just the sentence."
    )
    return _chat(prompt, description[:4000], api_key, model, max_tokens=80)


def _chat(system: str, user: str, api_key: str, model: str, max_tokens: int) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = httpx.post(GROQ_URL, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(Summary unavailable: {type(e).__name__})"
