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


def _client(cfg: EngineConfig):
    require_live(cfg, cfg.anthropic_api_key, "Batch scoring (Opus 4.8)")
    import anthropic
    return anthropic.Anthropic(api_key=cfg.anthropic_api_key)


def _id_map(blocks: list[EvidenceBlock]) -> dict[str, EvidenceBlock]:
    """custom_id → block. Deterministic (index + name slug), so a separate
    `fetch` process rebuilds the SAME mapping from the persisted blocks."""
    return {_safe_id(i, b.company_name): b for i, b in enumerate(blocks)}


def _requests(cfg: EngineConfig, blocks: list[EvidenceBlock]) -> list[dict]:
    return [
        {
            "custom_id": _safe_id(i, b.company_name),
            "params": {
                "model": cfg.interpretation_model,
                "max_tokens": 8192,   # match score.py: 4096 truncated rich interpretations
                "system": SCORE_PROMPT,
                "messages": [{"role": "user", "content": evidence_payload(b)}],
            },
        }
        for i, b in enumerate(blocks)
    ]


def submit_blocks(cfg: EngineConfig, blocks: list[EvidenceBlock]) -> str:
    """Submit the scoring batch and return its id WITHOUT waiting.

    This is the 'submit' half of the submit→fetch-later flow: the machine can
    be shut down after this returns; the results are collected by a separate
    `fetch` run once Anthropic has finished (within 24h)."""
    client = _client(cfg)
    batch = client.messages.batches.create(requests=_requests(cfg, blocks))
    logger.info("[batch] submitted %d companies (id=%s) — fetch later", len(blocks), batch.id)
    return batch.id


def batch_status(cfg: EngineConfig, batch_id: str) -> str:
    """Anthropic processing_status: 'in_progress' | 'ended' | 'canceling' …"""
    return _client(cfg).messages.batches.retrieve(batch_id).processing_status


def collect_results(cfg: EngineConfig, batch_id: str, id_to_block: dict[str, EvidenceBlock]
                    ) -> dict[str, tuple[list[ScoredSignal], list[str], str]]:
    """Parse a finished batch into scored results, keyed by company_name.

    Deterministic arithmetic (recency/corroboration) is applied in code here,
    exactly like the synchronous path — batch only changes HOW Opus was called.
    """
    client = _client(cfg)
    results: dict[str, tuple[list[ScoredSignal], list[str], str]] = {}
    for entry in client.messages.batches.results(batch_id):
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
    logger.info("[batch] collected %d companies at -50%%", len(results))
    return results


def score_blocks_batched(cfg: EngineConfig, blocks: list[EvidenceBlock],
                         poll_seconds: int = _POLL_SECONDS
                         ) -> dict[str, tuple[list[ScoredSignal], list[str], str]]:
    """Blocking mode: submit, poll up to 24h, then collect. Keyed by company_name.

    Keeps the machine running the whole time; for a machine-free wait use the
    submit_blocks()/collect_results() split via `--submit`/`--fetch`.
    """
    client = _client(cfg)
    id_to_block = _id_map(blocks)
    batch = client.messages.batches.create(requests=_requests(cfg, blocks))
    logger.info("[batch] submitted %d companies (id=%s) — polling every %ds",
                len(blocks), batch.id, poll_seconds)
    waited = 0
    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        if waited >= _MAX_WAIT_SECONDS:
            raise TimeoutError(f"Batch {batch.id} did not finish within 24h")
        time.sleep(poll_seconds)
        waited += poll_seconds
    return collect_results(cfg, batch.id, id_to_block)


def _safe_id(index: int, name: str) -> str:
    """custom_id must be a stable token; index keeps it unique + short."""
    import re
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:48]
    return f"c{index}-{slug}"
