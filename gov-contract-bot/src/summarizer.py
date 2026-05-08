"""One-sentence award summarizer using Groq's free-tier Llama 3.1."""
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You summarize US government contract awards in EXACTLY ONE sentence "
    "of at most 25 words. Be specific about what work is being performed. "
    "No preamble, no quotes, no markdown — just the sentence."
)


def summarize(description: str, api_key: str, model: str = "llama-3.1-8b-instant") -> str:
    if not description or len(description.strip()) < 20:
        return "No description available."

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description[:4000]},
        ],
        "max_tokens": 80,
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        resp = httpx.post(GROQ_URL, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(Summary unavailable: {type(e).__name__})"
