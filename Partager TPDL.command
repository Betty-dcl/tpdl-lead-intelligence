#!/bin/bash
# Double-clique ce fichier depuis le Finder pour mettre l'app en ligne et
# obtenir un lien à partager. Une fenêtre s'ouvre, affiche le lien (déjà copié
# dans le presse-papier) et le garde en ligne. Ferme la fenêtre pour arrêter.
cd "/Users/bettydeclety/Documents/TPDL/claude code dashboard" || {
  echo "Dossier du projet introuvable."; read -r -p "Entrée pour fermer…"; exit 1;
}
./share.sh
echo
read -r -p "Partage arrêté. Appuie sur Entrée pour fermer cette fenêtre…"
