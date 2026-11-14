Lavori in modalità completamente autonoma. Nessun umano risponderà alle domande.

## Contesto
1. Leggi TODO.md, PROGRESS.md e CLAUDE.md (se esiste).
2. Se tutti i punti di TODO.md sono [x] o [!], scrivi solo: <promise>TUTTO_FATTO</promise> e termina.

## Lavora su UN SOLO punto: il primo ancora [ ]
1. **Piano**: scrivi in PROGRESS.md un piano breve (passi, file coinvolti, come testerai).
2. **Decisioni**: quando ci sono più opzioni, scegli quella consigliata/più standard
   e annota in PROGRESS.md la scelta e il motivo in una riga. Non fermarti a chiedere.
3. **Esecuzione**: implementa il piano.
4. **Test**: esegui i test esistenti e aggiungine per il nuovo codice.
   Se falliscono, correggi e riesegui (massimo 3 tentativi).
5. **Miglioramento**: rileggi il codice, rimuovi duplicazioni ed errori evidenti, riesegui i test.
6. **Documenti**: aggiorna README/docs se il comportamento è cambiato.
   Segna il punto come [x] in TODO.md. In PROGRESS.md scrivi: fatto, test passati, problemi aperti.
7. **Commit**: `git add -A && git commit -m "<punto>: <sintesi>"`.

## Regole
- Non passare al punto successivo: termina dopo il commit (il loop esterno ti riavvia).
- Se un punto è bloccato (dipendenza mancante, test impossibile da far passare dopo 3 tentativi),
  segnalo come [!] in TODO.md con il motivo in PROGRESS.md, fai commit e termina.
- Non cancellare file fuori dal progetto e non fare push.
