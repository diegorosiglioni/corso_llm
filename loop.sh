#!/usr/bin/env bash
# Esegue una sessione nuova di Claude Code per ogni punto di TODO.md
set -uo pipefail
MAX_ITER=20

for i in $(seq 1 "$MAX_ITER"); do
  echo "=== Sessione $i ==="
  if ! out=$(claude -p "$(cat PROMPT.md)" --allowedTools "Read,Edit,Write,Bash"); then
    echo "Errore o limite di utilizzo raggiunto. I documenti sono aggiornati: rilancia più tardi."
    exit 1
  fi
  echo "$out" | tail -n 15
  if grep -q "<promise>TUTTO_FATTO</promise>" <<<"$out"; then
    echo "Tutti i punti completati."
    exit 0
  fi
done
echo "Raggiunto MAX_ITER. Rilancia per continuare."
