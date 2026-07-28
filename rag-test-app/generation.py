import os
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = """You are a customer support assistant. Answer the customer's
question using ONLY the policy excerpts provided below. If the excerpts don't
fully answer the question, say what you're unsure about rather than guessing.
Be concise — 2-3 sentences."""

def build_prompt(query: str, retrieved_chunks: list) -> str:
    context = "\n\n".join(
        f"[Excerpt from {c['source_file']}]\n{c['content']}"
        for c in retrieved_chunks
    )
    return f"""Policy excerpts:
{context}

Customer question: {query}"""

def generate(query: str, retrieved_chunks: list):
    user_prompt = build_prompt(query, retrieved_chunks)
    start = time.time()
    response = _client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    latency_ms = (time.time() - start) * 1000
    answer = response.choices[0].message.content
    usage = response.usage  # prompt_tokens, completion_tokens, total_tokens

    return {
        "answer": answer,
        "prompt": user_prompt,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "latency_ms": latency_ms,
    }


if __name__ == "__main__":
    from retrieval import retrieve

    query = "Can I return Product X? It is within the 30-day return period."
    chunks, retrieval_latency_ms = retrieve(query)
    result = generate(query, chunks)

    print(f"Answer:\n{result['answer']}\n")
    print(f"Prompt tokens: {result['prompt_tokens']}, Completion tokens: {result['completion_tokens']}")