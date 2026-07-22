#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# share.sh — met l'app en ligne sur un LIEN PUBLIC gratuit (Cloudflare tunnel).
#
#   ./share.sh          (ou double-clic sur « Partager TPDL.command »)
#
# Affiche une URL https://….trycloudflare.com, LA COPIE dans le presse-papier,
# et la garde en ligne. Chacun se connecte : prénom + mot de passe d'équipe (TPDL).
#
# ⚠️  Le lien marche TANT QUE cette fenêtre reste ouverte et que ton Mac est
#     allumé. Ferme la fenêtre (Ctrl+C) = le lien s'éteint. À chaque relance,
#     l'URL change (lien gratuit, non permanent).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

# Charger le .env dans l'environnement (gate d'auth + clés) — auth.py lit os.environ.
set -a; [ -f .env ] && . ./.env; set +a
PORT="${PORT:-8000}"

# venv
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

APP_PID=""
CF_PID=""
cleanup() {
  echo
  echo "▶ Arrêt du partage…"
  [ -n "$CF_PID" ]  && kill "$CF_PID"  2>/dev/null || true
  [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 1. App
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▶ App déjà lancée sur le port $PORT."
else
  echo "▶ Démarrage de l'app sur le port $PORT…"
  python -m uvicorn app.main:app --port "$PORT" --log-level warning &
  APP_PID=$!
  for _ in $(seq 1 40); do
    lsof -ti:"$PORT" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

# 2. Tunnel Cloudflare (en tâche de fond, journal capté pour récupérer l'URL)
LOG="$(mktemp -t tpdl-share)"
echo "▶ Ouverture du lien public (Cloudflare)…"
cloudflared tunnel --url "http://localhost:$PORT" > "$LOG" 2>&1 &
CF_PID=$!

# 3. Attendre l'URL, l'afficher en grand + la copier dans le presse-papier
URL=""
for _ in $(seq 1 60); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 0.5
done

echo
if [ -n "$URL" ]; then
  printf '%s' "$URL" | pbcopy 2>/dev/null || true
  echo "══════════════════════════════════════════════════════════════"
  echo "  ✅  TON LIEN À PARTAGER (déjà copié dans le presse-papier) :"
  echo
  echo "      $URL"
  echo
  echo "  → Colle-le (Cmd+V) dans un message à Andrés / Paula / Nathalie."
  echo "  → Connexion : prénom + mot de passe  TPDL"
  echo "  → LAISSE CETTE FENÊTRE OUVERTE. Pour arrêter : Ctrl+C."
  echo "══════════════════════════════════════════════════════════════"
else
  echo "⚠️  Lien pas encore prêt — regarde le journal : $LOG"
fi

# 4. Garder le tunnel en vie jusqu'à Ctrl+C / fermeture de la fenêtre
wait "$CF_PID"
