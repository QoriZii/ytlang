"""Translate transcript lines to a target language via Grok (xai_sdk).

Each call receives a batch of merged sentence-level segments and returns
an equal-length list of translations.
"""
from __future__ import annotations

import json
from typing import List

from ytlang import config
from ytlang.pipeline.utils import make_client
from ytlang.languages import DEFAULT_SOURCE_LANG, DEFAULT_NATIVE_LANG

BATCH_SIZE = 20

def _translate_batch(client, texts: List[str], translate_prompt: str) -> List[str]:
    from xai_sdk.chat import system, user

    chat = client.chat.create(model=config.XAI_MODEL)
    chat.append(system(translate_prompt))
    chat.append(user(json.dumps({"texts": texts}, ensure_ascii=False)))

    response = chat.sample()
    data = json.loads(response.content)
    result = data.get("translations", [])

    # Length guard: pad with original English if model returned fewer items
    if len(result) < len(texts):
        result.extend("" for _ in range(len(texts) - len(result)))
    return result[:len(texts)]


def translate(texts: List[str], source_lang: str = DEFAULT_SOURCE_LANG, native_lang: str = DEFAULT_NATIVE_LANG) -> List[str]:
    """Translate a list of source-language strings to the native language using Grok.

    Batches input into groups of BATCH_SIZE and sends all batches in parallel.
    Falls back to empty strings for any batch that fails.
    """
    if not texts:
        return []

    if not config.XAI_API_KEY:
        raise ValueError("XAI_API_KEY is not set. Export it: export XAI_API_KEY=xai-...")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ytlang.prompts import load_prompts

    prompts = load_prompts(source_lang, native_lang)
    translate_prompt = prompts["translate"]

    batches = [texts[i: i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
    results_map: dict = {}

    def run_batch(idx: int, batch: List[str]) -> tuple:
        try:
            return idx, _translate_batch(make_client(), batch, translate_prompt)
        except Exception as e:
            print(f"[translate] Warning: batch {idx + 1} failed ({e}); using empty strings")
            return idx, [""] * len(batch)

    with ThreadPoolExecutor(max_workers=min(len(batches), 3)) as executor:
        futures = {executor.submit(run_batch, i, b): i for i, b in enumerate(batches)}
        for future in as_completed(futures):
            idx, result = future.result()
            results_map[idx] = result

    results: List[str] = []
    for i in range(len(batches)):
        results.extend(results_map[i])
    return results
