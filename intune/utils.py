import httpx
import json
from django.conf import settings


def get_query_embedding(query):
    open_ai_api_key = settings.OPENAI_API_KEY
    open_ai_url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_ai_api_key}",
    }
    json_data = {
        "input": query,
        "model": "text-embedding-ada-002",
        "encoding_format": "float",
    }
    response = httpx.post(open_ai_url, headers=headers, json=json_data)
    if not response.status_code == 200:
        print(f"Failed to get embedding")
        return

    return response.json()["data"][0]["embedding"]


def get_llm_response(prompt):
    open_ai_api_key = settings.OPENAI_API_KEY
    open_ai_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_ai_api_key}",
    }
    json_data = {
        "model": "gpt-5-nano",
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 20000,
    }

    response = httpx.post(open_ai_url, headers=headers, json=json_data, timeout=60.0)
    if not response.status_code == 200:
        print("Response Details:", response.text)
        print(f"Failed to get LLM response")
        return None
    return response.json()["choices"][0]["message"]["content"]


def get_chat_title_from_llm(conversation_summary):
    """
    Generate a concise (<= 10 words) chat title from a conversation summary
    using the OpenAI Chat Completions endpoint. Returns the title string
    or None on error.
    """
    if not conversation_summary:
        return None

    prompt = f"""Generate a concise and descriptive title for the following chat conversation summary.
    The title should be no longer than 10 words and should capture the main topic of the conversation.
    Respond with only the title, without any additional text or formatting.

    Conversation Summary:
    {conversation_summary}

    Output Format: <summary>"""

    open_ai_api_key = settings.OPENAI_API_KEY
    open_ai_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_ai_api_key}",
    }

    json_data = {
        "model": "gpt-5-nano",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that outputs a single concise title.",
            },
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 1000,
    }

    try:
        response = httpx.post(
            open_ai_url, headers=headers, json=json_data, timeout=30.0
        )
    except httpx.RequestError as exc:
        # network/connection error
        print(f"Request failed: {exc}")
        return None

    if response.status_code != 200:
        print("Response Details:", response.text)
        print("Failed to get chat title from LLM")
        return None

    try:
        data = response.json()
        # robustly find choice text
        choice = data["choices"][0]
        # both chat/completions and some responses might place text in different keys:
        content = choice.get("message", {}).get("content") or choice.get("text")
        if not content:
            print("No content in LLM response:", data)
            return None
        title = content.strip()
        # Optionally enforce the <= 10 words constraint here by trimming:
        words = title.split()
        if len(words) > 10:
            title = " ".join(words[:10])
        return title
    except (KeyError, IndexError, ValueError) as exc:
        print("Error parsing LLM response:", exc)
        print("Response body:", response.text)
        return None
