#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# TPDL — GROS RUN, lancé depuis le Terminal. Objectif (Betty 23/07) :
#   CHERCHER PLUS LOIN que vendredi, GARDER LES DEUX RUNS SÉPARÉS, et VOIR LA
#   DIFFÉRENCE (communes / nouvelles). La fusion se fera PLUS TARD, pas maintenant.
#
# Ce que ça fait, dans l'ordre :
#   1. Met de côté la liste de vendredi (les 122) → discovery_friday.csv (intacte).
#   2. Découverte LIVE → trouve les sociétés du GROS RUN + capture leur ville quand
#      la source la donne → discovery_candidates.csv (le gros run, séparé de vendredi).
#   3. COMPARAISON vendredi ↔ gros run → discovery_comparison.csv (communes / nouvelles /
#      seulement-vendredi) + résumé à l'écran. AUCUNE fusion.
#   4. Soumet le SCORING en BATCH (submit) du GROS RUN SEUL (ses propres découvertes),
#      avec enrichissement ville + revenue, tech-scan frais, plafond budget.
#      Rend la main (le Mac peut dormir).
#   5. Affiche la commande --fetch à lancer plus tard (≤ 24 h) + l'import.
#
# SERP : SerpAPI est DRAINÉ d'abord, Serper prend le relais quand il est vide.
# STOP d'urgence à tout moment : Ctrl-C, ou dans un autre onglet : pkill -f pipeline.runner
#
# Usage :   bash scripts/run_big_launch.sh [PLAFOND_USD]
#   PLAFOND_USD : plafond de dépense dur (défaut 60). Le run s'arrête avant de le dépasser.
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")/.."          # racine du projet

MAX_USD="${1:-60}"
OUT="data/csv/engine_run_big.csv"
CANDIDATES="data/csv/discovery_candidates.csv"   # sera écrasé par le gros run
FRIDAY="data/csv/discovery_friday.csv"           # copie figée de vendredi
COMPARE="data/csv/discovery_comparison.csv"      # vendredi ↔ gros run

# Python : le venv du projet en priorité (il a les dépendances), sinon PATH.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python || command -v python3)"
fi
if [ -z "$PY" ]; then echo "❌ Python introuvable (ni .venv ni PATH)."; exit 1; fi
echo "▶ Python : $PY"
echo "▶ Plafond budget : \$$MAX_USD"
echo ""

# ── Étape 1 — Figer la liste de vendredi (ne PAS la perdre / ne pas la fusionner)
if [ -f "$CANDIDATES" ]; then
  cp "$CANDIDATES" "$FRIDAY"
  echo "═══ 1/5  Liste de vendredi figée → $FRIDAY"
else
  echo "═══ 1/5  (pas de liste de vendredi trouvée — on part de la seule découverte)"
  : > "$FRIDAY"
fi

# ── Étape 2 — Découverte du gros run (live) ─────────────────────────────────
echo "═══ 2/5  Découverte du gros run (live)…"
"$PY" -m pipeline.runner --discover --live      # écrit discovery_candidates.csv

# ── Étape 3 — Comparaison vendredi ↔ gros run (SANS fusion) ─────────────────
echo ""
echo "═══ 3/5  Comparaison vendredi ↔ gros run (aucune fusion)…"
"$PY" scripts/compare_discoveries.py "$FRIDAY" "$CANDIDATES" "$COMPARE"

# ── Liste des noms du GROS RUN SEUL (pas d'union avec vendredi) ─────────────
NAMES="$("$PY" scripts/_names_from_csv.py "$CANDIDATES")"
COUNT="$(echo "$NAMES" | tr ';' '\n' | grep -c . || true)"
if [ "$COUNT" -eq 0 ]; then echo "Aucune société découverte. Arrêt."; exit 0; fi

# ── Étape 4 — Soumettre le scoring du gros run en batch (submit) ────────────
echo ""
echo "═══ 4/5  Scoring du gros run ($COUNT sociétés) — soumission batch (submit)…"
"$PY" -m pipeline.runner \
  --names "$NAMES" \
  --live --batch --submit \
  --enrich-location --enrich-revenue \
  --rescan-tech \
  --max-usd "$MAX_USD" \
  --out "$OUT"

# ── Étape 5 — Rappels ───────────────────────────────────────────────────────
echo ""
echo "═══ 5/5  Batch soumis. À faire PLUS TARD (quand Anthropic a fini, ≤ 24 h) :"
echo ""
echo "    $PY -m pipeline.runner --fetch $OUT.pending.json"
echo "    $PY import_csv.py $OUT       # réinjecte dans la base + crée un run distinct"
echo ""
echo "📊 Comparaison vendredi ↔ gros run : $COMPARE"
echo "   (colonne Status : common = dans les deux · new = seulement gros run · dropped = seulement vendredi)"
echo "✅ Terminé. Vendredi ($FRIDAY) et le gros run restent SÉPARÉS — fusion plus tard."
