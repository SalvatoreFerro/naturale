# Verifiche dell'anteprima 0.2.0

Esecuzione locale del 12 novembre 2026. Questi risultati descrivono i controlli
eseguiti, non una garanzia universale sul comportamento dei modelli o di Meta.

## Ambiente e risultati

| Voce | Risultato |
| --- | --- |
| Ambiente | Linux, Python 3.12.14 |
| Pillow / ExifTool | 12.3.0 / 13.63 |
| SDK C2PA facoltativo | c2pa-python 0.38.1 |
| Suite Python completa locale | 144 test passati, 37 sottocasi passati; nessun test saltato |
| Dataset editoriale | 80 casi validi, 40 sviluppo e 40 heldout |
| Valutazione umana | Non eseguita; `not_validated` |
| Codex reale | 0.167.0-alpha.4: rilevamento `naturale` riuscito via `skills/list`, skill abilitata, nessun errore |
| Claude Code | Non installato nell'ambiente; formato e struttura verificati, esecuzione nell'host non verificata |
| macOS / Windows | Matrice remota su GitHub Actions con Python 3.11 e 3.12; [esiti delle esecuzioni](https://github.com/SalvatoreFerro/naturale/actions/workflows/ci.yml) |
| Instagram / SynthID | Nessun test su Instagram, nessuna verifica o rimozione SynthID |

Il controllo Codex usa una copia temporanea nella directory di skill di un
progetto. Invia soltanto messaggi di inizializzazione e lettura dell'elenco:
non genera testi, non modifica configurazioni utente e non prova la qualità
editoriale della skill. La copia, il file VERSION e i metadati del progetto
riportano tutti `0.2.0`.

Uno smoke test su una home temporanea verifica l'installazione del pacchetto
completo per entrambi gli host, un aggiornamento locale e il successivo rollback.
Un profilo stilistico esterno rimane byte per byte invariato durante il ciclo.
I comandi del pacchetto copiato sono eseguiti anche da una directory indipendente.

## Cosa coprono i test

- JPEG/PNG con XMP, EXIF, orientamento, profilo ICC e trasparenza.
- Rimozione XMP e contenitore JUMBF, pixel e originale invariati.
- Credenziali C2PA originali firmate con certificati e chiavi effimere locali;
  distinzione tra integrità valida e fiducia nel firmatario.
- PNG ancora decodificabile con dati modificati e hash C2PA non valido.
- SDK assente o risultati incompleti; impostazioni di rete disabilitate
  nell'adattatore C2PA tramite test del contesto passato al SDK.
- Riepiloghi immagini senza valori di metadati o percorsi completi, rapporti
  completi espliciti, pulizia mirata GPS/identificativi e conservazione JUMBF.
- Batch con anteprima senza scritture, file corrotti, collisioni e risultati
  indipendenti per immagine.
- Collisioni, permessi privati su Unix, file corrotti o non supportati,
  percorsi Unicode, errori di scrittura e assenza di output dopo verifica fallita.
- Canonicalizzazione della directory di output per alias di filesystem
  macOS/Windows, conservando il rifiuto dei symlink sul file finale.
- Contratto Agent Skills e riferimenti locali.
- Installer locale: anteprima, ricevute, aggiornamento e ripristino per entrambi
  gli agenti, collisioni, symlink, FIFO, copie legacy e personalizzazioni.
  Modifiche concorrenti conservate insieme al backup, senza cancellare dati nuovi;
  rilevamento della skill soltanto dopo la copia dei file di supporto.
- Profili stilistici espliciti: schema, permessi, nomi, cancellazione richiesta,
  dati non validi e nessun file parziale dopo errori Unicode.
- Audit: numeri, citazioni, URL, vincoli, riassunti e diff; limiti dimostrati con
  scambi di responsabilità che un confronto meccanico non può certificare.
- Output CLI UTF-8 anche con codifica di pipe Windows simulata, inclusi emoji.
- Diagnosi locale e rapporti privi di percorsi o messaggi grezzi degli strumenti.
- Formato di valutazione estensibile, pacchetti ciechi, assegnazioni bilanciate,
  modello/versione registrati, soglia per caso, copertura minima e dati autorizzati
  solo dichiarati, senza inventare revisioni umane.

Prima della pubblicazione è stato controllato l'elenco dei file versionati e
usato `detect-secrets` 1.5.0 senza verifica di credenziali via rete. L'unico
candidato segnalato era lo SHA pubblico del sorgente ExifTool nel workflow,
controllato come riferimento di dipendenza e non come credenziale. Cache,
ambienti virtuali, rapporti privati e strumenti scaricati non sono versionati.
Questo controllo non costituisce una garanzia generale di assenza di segreti.

Le prove del codice e quelle dei modelli sono distinte. La configurazione
offline è verificata nel codice e nei test dell'adattatore;
non è stata eseguita una cattura del traffico di ogni possibile percorso nativo
del SDK. Manifest remoti e richieste OCSP sono disabilitati esplicitamente.

## Riproduzione

Da un ambiente con ExifTool nel PATH:

```sh
python -m pip install -e '.[dev,c2pa]'
python -m pytest -q
python scripts/evaluate.py --validate-cases evals/cases.jsonl --pilot
python scripts/evaluate.py --validate-cases evals/real-world-template.jsonl
```

Senza l'extra C2PA i test che richiedono il SDK reale vengono saltati; senza
ExifTool non si eseguono i test di integrazione immagini. Controllare sempre
il riepilogo dei test prima di confrontare risultati.
