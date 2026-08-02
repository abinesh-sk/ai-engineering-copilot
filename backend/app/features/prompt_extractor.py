"""
Feature Extraction: Day 11 -- prompt/context metrics.

Pure function, no side effects, no DB access. Reads only the llm_call span's
raw_data. Never invents numbers Groq didn't actually report.

Design doc (Section 17.3) calls for "context tokens" specifically. Groq's
usage response only tokenizes the entire assembled prompt as one figure --
it does not separate "context" tokens from "question" tokens, and re-
tokenizing the context substring ourselves with a different tokenizer than
Llama actually uses would produce a plausible-looking but wrong number.

So this extractor reports:
  - prompt_tokens / completion_tokens: real numbers from Groq's usage response
  - prompt_length_chars: character length of the full assembled prompt
  - context_length_chars: character length of just the retrieved-context
    portion (everything before the "Customer question:" marker)

context_length_chars is a character-count proxy, not a token count.
Logged as a deviation from the doc's literal wording.
"""

QUESTION_MARKER = "\n\nCustomer question:"


def extract_prompt_metrics(raw_data: dict) -> dict:
    prompt = raw_data.get("prompt")
    prompt_tokens = raw_data.get("prompt_tokens")
    completion_tokens = raw_data.get("completion_tokens")

    if prompt is None:
        prompt_length_chars = None
        context_length_chars = None
    else:
        prompt_length_chars = len(prompt)
        split_index = prompt.find(QUESTION_MARKER)
        context_length_chars = split_index if split_index != -1 else None

    return {
        "prompt_length_chars": prompt_length_chars,
        "context_length_chars": context_length_chars,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }