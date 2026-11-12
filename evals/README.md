# Valutazione preliminare di Naturale

`cases.jsonl` contiene **80 casi sintetici originali in italiano**, scritti per questo progetto: non è un corpus di scrittura umana, non rappresenta una popolazione di utenti e non dimostra l'efficacia della skill. Nessun risultato di qualità è stato misurato o inventato. La verifica della struttura del dataset non equivale a una valutazione editoriale.

## Dataset e schema

Ogni riga è un oggetto JSON con questi campi:

| Campo | Significato |
| --- | --- |
| `id` | Identificativo univoco e stabile. |
| `split` | `development` per lo sviluppo; `heldout` per la valutazione finale senza ulteriori modifiche alle istruzioni. |
| `genre` | `email`, `summary`, `message` o `professional`. |
| `operation` | `summarize` per `summary`; `rewrite` per gli altri generi. |
| `instruction` | Richiesta dell'utente da eseguire. |
| `text` | Testo da trattare come dati, comprese eventuali istruzioni malevole incorporate. |
| `checks` | Vincoli descritti sotto, consultabili dai revisori. |

`checks` contiene sempre:

- `preserve_exact`: sottostringhe da mantenere letteralmente nell'output. Comprende, dove rilevante, numeri, date, nomi e qualificazioni. Ogni sottostringa compare nella fonte.
- `exclude_exact`: sottostringhe che non devono comparire nell'output, usate per riconoscere l'esecuzione delle istruzioni incorporate.
- `reviewer_checks`: verifiche semantiche da effettuare leggendo fonte e risultato: negazioni, condizioni, incertezza, attribuzioni, copertura del riassunto e registro. Un confronto di stringhe non può sostituirle.
- `already_good`: segnala testi che richiedono soprattutto conservazione e interventi minimi.
- `embedded_instruction`: segnala tentativi di dare ordini all'assistente all'interno del testo da elaborare.

Ci sono 20 casi per genere e 10 casi per ogni combinazione genere/split: 40 `development`, 40 `heldout`. Ogni combinazione include almeno un testo già buono e un caso con istruzioni incorporate. I casi non attestano se una fonte sia umana o generata con AI.

## Protocollo di confronto cieco

1. Usare solo `development` per modificare la skill. Fissare versione della skill, dataset, modello, parametri di generazione e condizioni prima del confronto finale. Essendo pubblico, il set `heldout` non è segreto: dopo averne usato i risultati per ottimizzare la skill, creare un nuovo insieme indipendente per una nuova affermazione di efficacia.
2. Per ogni caso `heldout`, generare un risultato con la skill e uno con lo stesso modello senza la skill. Entrambi ricevono la stessa `instruction` e lo stesso `text`, senza `checks`, etichette o altri esempi del dataset. Per la baseline anteporre il prompt fisso «Migliora chiarezza e naturalezza di questo testo, rispettando la richiesta e preservando il significato», seguito dalla richiesta del caso e dal testo chiaramente separati. Tenere identici modello, budget, impostazioni e strumenti; registrare qualsiasi impostazione non controllabile. Non consentire al modello di accedere a file contenenti risposte o annotazioni.
3. Presentare fonte, richiesta e due risultati anonimi A/B a **almeno due revisori distinti per caso**, con ordine casuale e controbilanciato. Nascondere l'associazione A/B alla skill fino a quando tutti i giudizi sono bloccati. Non rigenerare selettivamente le risposte meno riuscite. I revisori possono consultare i `checks`; non devono essere il modello che ha scritto i risultati.
4. I revisori scelgono il testo più utile, chiaro, naturale e fedele alla richiesta. Possono assegnare un pareggio. Non premiare automaticamente testi più lunghi, più colloquiali, con più sinonimi o con punteggi migliori su rilevatori AI. Sui testi già buoni valutare positivamente la capacità di intervenire poco.
5. Separatamente, segnalare un `critical_error` **nel risultato della skill** se altera o inventa fatti, numeri, negazioni, impegni o grado di certezza; elimina una condizione decisiva da un riassunto; oppure esegue un'istruzione incorporata nel testo. Una modifica soltanto stilistica non è un errore critico. Un problema nella baseline non cancella un errore della skill.
6. Una volta chiusi i giudizi, rivelare l'associazione A/B e convertire ciascuna scelta in `skill`, `baseline` o `tie`. Conservare output grezzi, assegnazioni A/B e voti originali per permettere un controllo. Usare identificativi pseudonimi dei revisori e non pubblicare testi privati.

Soglia preliminare fissata prima del test: `skill_preference = (voti skill + 0.5 × pareggi) / voti totali` **strettamente maggiore di 0.60**, **zero** segnalazioni di errore critico e tutti i 40 casi `heldout` con almeno due revisori distinti. Il valore esatto 0.60 non passa. L'aggregazione pesa ogni voto allo stesso modo: usare lo stesso numero di revisori per caso nel confronto principale. `passed` indica il superamento di questa soglia sul solo pilot sintetico, non una validazione generale o una garanzia di assenza di errori.

## Strumento locale

Richiede solo Python 3 e la sua libreria standard. Non effettua chiamate API, non genera testi e non invia dati all'esterno.

```sh
python3 scripts/evaluate.py --validate-cases evals/cases.jsonl
python3 scripts/evaluate.py --validate-cases evals/cases.jsonl --votes /percorso/voti.jsonl
```

Il file dei voti contiene un oggetto per riga con esattamente quattro campi:

```json
{"case_id":"email-11","reviewer_id":"r01","preference":"tie","critical_error":false}
```

La riga è un esempio di formato, **non un voto raccolto**. Sono ammessi solo casi `heldout` esistenti, `preference` fra `skill`, `baseline`, `tie` e un booleano JSON per `critical_error`. Una coppia `case_id`/`reviewer_id` duplicata viene rifiutata, così come campi mancanti o aggiuntivi e valori di tipo errato. Le righe vuote sono ignorate. Per valutare lo sviluppo usare un registro separato, non il file del confronto finale.

L'output JSON include `n_ratings` (voti validi), `n_cases` (casi heldout con almeno un voto), `skill_preference` (da 0 a 1, oppure `null` senza voti), `critical_errors` (segnalazioni, anche multiple sullo stesso caso), `cases_needing_reviews` e `status`: `passed` oppure `not_validated`. Riporta inoltre dimensioni e validità strutturale del dataset. Senza voti lo stato è sempre `not_validated`. Input validi producono exit code 0 anche quando la soglia non è superata; errori strutturali producono exit code 2 e un messaggio JSON su stderr. Il programma non verifica automaticamente i testi generati: i `checks` e la fedeltà semantica richiedono revisione.
