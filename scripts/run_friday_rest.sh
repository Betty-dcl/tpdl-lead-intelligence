#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# TPDL — PETIT BATCH « reste de vendredi » (Betty 23/07).
# Score les sociétés de la liste de vendredi que le gros run n'a PAS reprises
# (les 71 « seulement vendredi »), pour valider TOUTE la liste de vendredi.
# Ne re-score PAS les 51 déjà dans le gros run (pas de doublon).
#
# À lancer APRÈS run_big_launch.sh (il a besoin de discovery_friday.csv +
# discovery_candidates.csv). Batch séparé → son propre CSV et son propre run.
#
# SERP : SerpAPI d'abord (probablement déjà vide après le gros run) → Serper.
# STOP : Ctrl-C, ou dans un autre onglet : pkill -f pipeline.runner
#
# Usage :   bash scripts/run_friday_rest.sh [PLAFOND_USD]   (défaut 30)
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")/.."

MAX_USD="${1:-30}"
OUT="data/csv/engine_run_friday_rest.csv"
FRIDAY="data/csv/discovery_friday.csv"
CANDIDATES="data/csv/discovery_candidates.csv"

if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY="$(command -v python || command -v python3)"; fi
if [ -z "$PY" ]; then echo "❌ Python introuvable."; exit 1; fi

if [ ! -f "$FRIDAY" ]; then
  echo "❌ $FRIDAY introuvable — lance d'abord run_big_launch.sh."; exit 1
fi

echo "▶ Python : $PY · Plafond : \$$MAX_USD"
NAMES="$("$PY" scripts/_friday_only_names.py "$FRIDAY" "$CANDIDATES")"
COUNT="$(echo "$NAMES" | tr ';' '\n' | grep -c . || true)"
echo "═══ Sociétés « seulement vendredi » à scorer : $COUNT"
if [ "$COUNT" -eq 0 ]; then echo "Rien à faire — tout vendredi est déjà couvert."; exit 0; fi

echo ""
echo "═══ Soumission du batch (submit)…"
"$PY" -m pipeline.runner \
  --names "$NAMES" \
  --live --batch --submit \
  --enrich-location --enrich-revenue \
  --rescan-tech \
  --max-usd "$MAX_USD" \
  --out "$OUT"

echo ""
echo "═══ Batch soumis. À faire PLUS TARD (≤ 24 h), comme pour le gros run :"
echo ""
echo "    $PY -m pipeline.runner --fetch $OUT.pending.json"
echo "    $PY import_csv.py $OUT"
echo ""
echo "✅ Terminé. Le Mac peut être fermé. (Run distinct du gros run.)"
