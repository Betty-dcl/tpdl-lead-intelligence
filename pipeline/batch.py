"""Step 5 — Batch API scoring: score many companies in one -50% batch.

The Anthropic Batch API is the SAME Claude models and the SAME API key as the
normal calls — you just submit a bundle of requests that Anthropic processes
within 24h at half price. Scoring a whole run is not time-critical, so batch is
the right mode for volume (cran 2+). A single company (cran 1) uses the normal
synchronous path in score.py — no need to batch one request.

Everything here is behind the money gate: dry-run raises EngineOffline.
"""
from __future__ import annotations

import logging
import time

from pipeline.config import PROMPTS_DIR, EngineConfig, require_live
from pipeline.score import _parse_interpretation, evidence_payload, score_signal
from pipeline.types import EvidenceBlock, ScoredSignal

logger = logging.getLogger(__name__)

SCORE_PROMPT = (PROMPTS_DIR / "score_opus.md").read_text(encoding="utf-8")

_POLL_SECONDS = 30
_MAX_WAIT_SECONDS = 24 * 3600


def score_blocks_batched(cfg: EngineConfig, blocks: list[EvidenceBlock],
                         poll_seconds: int = _POLL_SECONDS
                         ) -> dict[str, tuple[list[ScoredSignal], list[str], str]]:
    """Score every block via one Batch API job. Keyed by company_name.

    Falls back cleanly: the deterministic arithmetic (recency/corroboration)
    is still applied in code to each interpreted signal, exactly like the
    synchronous path — batch only changes HOW the Opus calls are sent.
    """
    require_live(cfg, cfg.anthropic_api_key, "Batch scoring (Opus 4.8)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    requests = [
        {
            "custom_id": _safe_id(i, b.company_name),
            "params": {
                "model": cfg.interpretation_model,
                "max_tokens": 4096,
                "system": SCORE_PROMPT,
                "messages": [{"role": "user", "content": evidence_payload(b)}],
            },
        }
        for i, b in enumerate(blocks)
    ]
    id_to_block = {r["custom_id"]: b for r, b in zip(requests, blocks)}

    batch = client.messages.batches.create(requests=requests)
    logger.info("[batch] submitted %d companies (id=%s) — polling every %ds",
                len(requests), batch.id, poll_seconds)

    waited = 0
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        if waited >= _MAX_WAIT_SECONDS:
            raise TimeoutError(f"Batch {batch.id} did not finish within 24h")
        time.sleep(poll_seconds)
        waited += poll_seconds

    results: dict[str, tuple[list[ScoredSignal], list[str], str]] = {}
    for entry in client.messages.batches.results(batch.id):
        block = id_to_block.get(entry.custom_id)
        if block is None:
            continue
        if entry.result.type != "succeeded":
            logger.warning("[batch] %s: %s", entry.custom_id, entry.result.type)
            results[block.company_name] = ([], [], "Batch scoring failed for this company.")
            continue
        text = "".join(b.text for b in entry.result.message.content if b.type == "text")
        signals, not_evidenced, summary = _parse_interpretation(text, block)
        scored = [score_signal(cfg, s) for s in signals]
        results[block.company_name] = (scored, not_evidenced, summary)
    logger.info("[batch] scored %d companies at -50%%", len(results))
    return results


def _safe_id(index: int, name: str) -> str:
    """custom_id must be a stable token; index keeps it unique + short."""
    import re
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:48]
    return f"c{index}-{slug}"
