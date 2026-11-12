# Verifica della preparazione 0.2.1

Controlli del 12 novembre 2026 sul branch `fix/verifica-0.2.1`, a partire dalla
0.2.0 (`3c6f7d3374d332306c82d7fa1f17d6ca5be60496`). Nessun tag o release.
I risultati riguardano il codice e i contratti della skill, non una misura
universale della qualità editoriale o dei sistemi di etichettatura esterni.

## Ambiente e risultati

| Voce | Risultato |
| --- | --- |
| Ambiente finale | Linux, Python 3.13.5 |
| Pillow / SDK facoltativo | 12.3.0 / c2pa-python 0.38.1 |
| ExifTool 13.63 | Sorgente ufficiale, commit `1da714924f67763b6a8a7013dd2aa1983a16f87b`; 195 test passati, nessun salto |
| ExifTool 13.60 | Minimo supportato, 195 test passati, nessun salto |
| ExifTool 12.76 | 145 passati, 50 integrazioni incompatibili saltate con motivo esplicito; API/CLI rifiutano l'elaborazione con `exiftool_too_old` |
| Claude Code | Validatore ufficiale 2.1.275: marketplace e plugin validi; nessuna invocazione di modelli |
| Dataset editoriale | Invariato: 80 casi validi, 40 sviluppo e 40 heldout; pilot `not_validated`, zero valutazioni umane |
| CI | Linux/macOS/Windows con Python 3.11 e 3.12, più Linux/Python 3.13; [esecuzioni](https://github.com/SalvatoreFerro/naturale/actions/workflows/ci.yml) |
| Instagram / SynthID | Nessun test né certificazione di assenza o rimozione |

I conteggi finali sono riportati nella PR insieme agli esiti remoti della
matrice. Senza SDK C2PA i test che richiedono firme reali vengono saltati;
senza un ExifTool supportato vengono saltate le integrazioni immagini, mentre
i test del rifiuto delle versioni precedenti continuano a essere eseguiti.

## Perché il minimo è ExifTool 13.60

Sul sorgente 0.2.0, in un ambiente isolato Python 3.12.14, Pillow 12.3.0 e
c2pa-python 0.38.1:

| ExifTool | Prova | Risultato |
| --- | --- | --- |
| 12.76 | Suite completa | 144 passati, 2 falliti: privacy sui PNG C2PA firmati |
| 13.59 | Entrambi i test PNG firmati | 2 falliti |
| 13.60 | Suite completa | 146 passati, 37 sottocasi passati |
| 13.63 | Suite completa | 146 passati, 37 sottocasi passati |

13.59 e 13.60 sono release adiacenti. La
[cronologia ufficiale](https://exiftool.org/history.html) della 13.60 documenta
la correzione dei puntatori nelle directory PNG
([ExifTool #453](https://github.com/exiftool/exiftool/issues/453)).
`PNG.pm` reinizializza `PROCESSED` fra directory incorporate, i cui offset
sono relativi al singolo chunk. La soglia è definita una sola volta in
`exiftool_runtime.py` e usata da diagnostica e API immagini.
La suite della preparazione finale è stata ripetuta anche su Python 3.13
con 13.60, 13.63 e 12.76.

## Regressioni prima e dopo

Per ciascun problema sono stati aggiunti prima test che fallivano, poi la
correzione; i log di lavoro non sono inclusi nel pacchetto pubblico.

| Problema | Prima | Correzione e controlli aggiunti |
| --- | --- | --- |
| 1. Audit | Date, parole numeriche e scadenze perse; negazioni/possibilità ignorate dall'exit; formati equivalenti bloccati | Dieci casi della revisione, marcatori aggiuntivi, segni monetari separati, date e numeri italiani, euro/orari equivalenti, stdin senza file, input invalidi; exit 1/3/0 verificati. Scambio di responsabilità ancora documentato come limite. |
| 2. Versione ExifTool | 12.76 dichiarata pronta ma due verifiche PNG fallivano | Test del confine 13.59/13.60, 13.63 e 12.76, stessa costante per doctor e immagini, rifiuto prima di letture o scritture. |
| 3. GPS-only | Perdita dei tag tecnici IFD0 e blocco su JPEG/PNG | Conservazione dei soli valori tecnici già presenti. JPEG/PNG positivi e manomissioni Make/DateTimeOriginal che devono continuare a bloccare. |
| 4. Rimozioni | Copia dichiarata riuscita senza evidenziare testo o GPS rimasti | `nothing_removed`, `generation_text_retained`, `gps_retained` in sintesi e rapporto. Test tEXt/iTXt/zTXt, keyword note e arbitrarie, commento JPEG e XMP+GPS. Nessuna nuova categoria rimossa. |
| 5. Errori | WebP e altri casi indistinguibili | Codici tipizzati per formato, estensione, limiti, multiframe, collisioni e verifica; messaggi statici. Test input invariato e nessun output dopo errore, dettagli solo full-report. |
| 6. Profili | HOME e basi con alias simbolico rifiutate | Alias base risolti, symlink nel deposito e sui file finali ancora rifiutati; creazione/lettura/lista/cancellazione e collisioni. |
| 7. Dipendenze | PR su base 0.1.0 rosse per alias di percorsi | Pin action aggiornati dopo test della policy CI; credenziali non persistenti e permessi di sola lettura conservati. Pillow resta `<13`; [analisi](DEPENDENCY-REVIEW.md). |
| 8. Description | 469 caratteri e trigger non desiderati | 189 caratteri; test del limite e dei termini esclusi, limiti nel corpo conservati. |
| 9. Plugin Claude | Manifest assenti | Test dei due manifest, sorgente locale `./`, assenza di servizi/hook aggiunti, istruzioni README e validatore ufficiale. |

Restano coperti firme C2PA effimere locali, hash/pixel/EXIF/ICC/colore,
trasparenza, originali invariati, percorsi Unicode e alias macOS/Windows,
output esclusivi, rollback del sidecar, batch e anteprime senza scritture,
installer e profili con permessi privati, input non fidati e output CLI UTF-8.

Il controllo `detect-secrets` 1.5.0 sui file versionati, senza verifica di
credenziali via rete, segnala soltanto tre SHA pubblici: il sorgente ExifTool
nel workflow e i due pin delle action nei test della policy. Sono riferimenti
di dipendenze esaminati come falsi positivi. Cache, tool locali, log e
ambienti virtuali restano esclusi dal repository.

Il modulo testi usa soltanto la libreria standard. Gli script non aggiungono
chiamate di rete; ExifTool non carica configurazioni Perl utente. Il contesto
SDK C2PA disabilita recupero di manifest remoti e OCSP, come verificato nei
test dell'adattatore. Non è stata eseguita una cattura di ogni percorso nativo
possibile del SDK. Installare strumenti e dipendenze richiede separatamente
il loro download: non fa parte dell'elaborazione locale dei file.

## Riproduzione

Con Python 3.13 e l'ExifTool scelto nel PATH:

```sh
python -m pip install -e '.[dev,c2pa]'
exiftool -ver
python -m pytest
python scripts/evaluate.py --validate-cases evals/cases.jsonl --pilot
python scripts/evaluate.py --validate-cases evals/real-world-template.jsonl
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
```

Il validatore Claude controlla il formato; non dimostra l'esecuzione completa
in una sessione del modello. La 0.2.0 aveva già verificato il rilevamento della
skill con Codex 0.167.0-alpha.4; non viene presentato come un nuovo test della
qualità della 0.2.1. Non sono stati modificati il dataset, la policy di
rimozione provenance o il limite di supporto Pillow.
