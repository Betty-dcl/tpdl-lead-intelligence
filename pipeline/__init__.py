"""TPDL Lead Intelligence engine — reconstruction of the Neotek 6-step pipeline.

    0 Load → 1 Tech scan → 2 Research → 3 Extract (Sonnet 5)
           → 4 Score (Opus 4.8) → 5 Batch → 6 Output CSV

Design source of truth: .claude/neotek-process.md + CLAUDE.md.
Non-negotiable: structural extraction/interpretation split —
the extractor (Sonnet 5) touches raw text but never judges; the
interpreter (Opus 4.8) judges but never sees raw text, only isolated
verbatim evidence.

ZERO-SPEND GUARANTEE: everything runs in dry-run mode by default
(fixtures, mock extractor/interpreter, no network, no API cost).
Live calls require BOTH `--live` AND the relevant API key.
"""
