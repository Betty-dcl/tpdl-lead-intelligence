#!/bin/bash
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
#
# NB : volontairement SANS `set -euo pipefail` — c'est un lanceur grand public
# qui doit tourner sous le bash 3.2 de macOS sans jamais planter en cryptique.
# ─────────────────────────────────────────────────────────────────────────────
cd "$(dirname "$0")" || exit 1

# Homebrew dans le PATH (cloudflared) même lancé par /bin/bash non-login.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PORT="${PORT:-8000}"

# Charger le .env dans l'environnement (gate d'auth + clés) — auth.py lit os.environ.
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# Python du venv en direct (pas d'`activate`, plus robuste).
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

APP_PID=""
CF_PID=""
cleanup() {
  echo
  echo "▶ Arrêt du partage…"
  [ -n "$CF_PID" ]  && kill "$CF_PID"  2>/dev/null
  [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

# 1. App
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▶ App déjà lancée sur le port $PORT."
else
  echo "▶ Démarrage de l'app sur le port $PORT…"
  "$PY" -m uvicorn app.main:app --port "$PORT" --log-level warning &
  APP_PID=$!
  n=0
  while [ "$n" -lt 40 ]; do
    lsof -ti:"$PORT" >/dev/null 2>&1 && break
    sleep 0.5
    n=$((n + 1))
  done
fi

# 2. Tunnel Cloudflare (en tâche de fond, journal capté pour récupérer l'URL)
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "⚠️  cloudflared introuvable. Installe-le une fois : brew install cloudflared"
  read -r -p "Entrée pour fermer…"
  exit 1
fi
LOG="$(mktemp -t tpdl-share)"
echo "▶ Ouverture du lien public (Cloudflare)…"
cloudflared tunnel --url "http://localhost:$PORT" > "$LOG" 2>&1 &
CF_PID=$!

# 3. Attendre l'URL, l'afficher en grand + la copier dans le presse-papier
URL=""
n=0
while [ "$n" -lt 60 ]; do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)"
  [ -n "$URL" ] && break
  sleep 0.5
  n=$((n + 1))
done

echo
if [ -n "$URL" ]; then
  printf '%s' "$URL" | pbcopy 2>/dev/null
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
  echo "⚠️  Lien pas encore prêt. Dernières lignes du journal :"
  tail -8 "$LOG"
fi

# 4. Garder le tunnel en vie jusqu'à Ctrl+C / fermeture de la fenêtre
wait "$CF_PID"
