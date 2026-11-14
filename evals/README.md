# Valutazione editoriale di Naturale

Gli **80 casi sintetici originali** di `cases.jsonl` restano il pilot iniziale:
40 di sviluppo e 40 riservati al confronto finale. Non sono un corpus umano e
non rappresentano una popolazione di utenti. La versione 0.2 aggiunge un formato
estensibile per casi autorizzati e strumenti per preparare un confronto cieco.
**Non sono stati raccolti giudizi umani: lo stato resta `not_validated`.**

## Dati e autorizzazione

Ogni riga JSONL contiene `id`, `split` (`development` o `heldout`), `genre`
(`email`, `summary`, `message`, `professional`), `operation` (`summarize` per
summary, `rewrite` per gli altri), `instruction`, `text` e `checks`.

`checks` contiene `preserve_exact`, `exclude_exact` e `reviewer_checks` come liste
di stringhe, più `already_good` e `embedded_instruction` come booleani.
`preserve_exact` deve comparire nella fonte; sono controlli di stringhe, non
prove di equivalenza semantica. I revisori devono valutare negazioni, condizioni,
incertezza, responsabilità, promesse, attribuzioni e copertura del riassunto.

Il campo facoltativo `provenance` dichiara l'origine del caso:

```json
{"kind":"synthetic"}
```

Per testi realmente forniti con autorizzazione e anonimizzati:

```json
{"kind":"human_authorized","consent":"confirmed","anonymized":true}
```

La seconda dichiarazione va usata **solo dopo** avere ottenuto il consenso
necessario e rimosso i dati personali. Il validatore controlla la dichiarazione,
non verifica l'autenticità del consenso. Se manca `provenance`, i casi sono
conteggiati come sintetici per compatibilità con il pilot 0.1.

`real-world-template.jsonl` è un **esempio sintetico di formato**, non una
raccolta di dati reali: duplicarlo come base e sostituirlo con casi autorizzati,
conservando il consenso fuori dal dataset pubblico. Non pubblicare e-mail,
campioni di voce o rapporti personali senza un'autorizzazione specifica.

```sh
# Controllo del formato, indipendente dal numero di casi
python scripts/evaluate.py --validate-cases evals/real-world-template.jsonl

# Anche la composizione del pilot originale: 80 casi, 10 per genere/split
python scripts/evaluate.py --validate-cases evals/cases.jsonl --pilot
```

Il formato richiede almeno un caso `heldout`. `--pilot` aggiunge i vincoli di
composizione originali, compresi testi già efficaci e istruzioni incorporate.
Il file originale non è stato alterato. Gli input JSONL hanno un limite di 20 MiB,
devono essere file regolari (non symlink o FIFO) e accettano UTF-8 anche con BOM.

## Preparare il confronto cieco

Usare `development` per migliorare le istruzioni. Prima del test finale fissare
versione della skill, versione esatta del modello e impostazioni di generazione.
Essendo pubblico, il set `heldout` non è segreto: se ne usi i risultati per
ottimizzare la skill, prepara un nuovo insieme indipendente per la prova seguente.

Per ogni caso heldout, produrre un risultato con skill e uno senza skill, usando
**lo stesso modello, la stessa richiesta, la stessa fonte e le stesse impostazioni**.
Per la baseline anteporre il prompt fisso: «Migliora chiarezza e naturalezza di
questo testo, rispettando la richiesta e preservando il significato».
Non fornire al modello `checks`, etichette, risposte o altri casi del benchmark.
Non rigenerare selettivamente i risultati meno riusciti. Registrare anche budget,
strumenti e parametri non controllabili nel registro dell'esperimento.

Il programma non genera testi e non chiama API. Riceve risultati prodotti
separatamente, un oggetto per ogni caso heldout, senza campi aggiuntivi:

```json
{"case_id":"email-11","model":"modello-versione-esatta","skill_version":"0.2.0","skill_output":"Risultato con la skill","baseline_output":"Risultato con il prompt generico"}
```

Ogni preparazione richiede una sola versione del modello e della skill e tutti
i casi heldout esattamente una volta. La directory di output deve essere nuova.

```sh
python scripts/evaluate.py --validate-cases evals/cases.jsonl \
  --prepare-comparison /percorso/risultati.jsonl \
  --output-dir /percorso/confronto-nuovo
```

Il comando crea una directory privata con:

- `packets.jsonl`: fonte, richiesta, risultati A/B anonimi e checklist per i revisori.
- `mapping-private.json`: associazione A/B a skill/baseline, versioni e seme.
  **Non condividere questa mappa prima del blocco dei giudizi.**

La posizione A della skill è controbilanciata tra i casi e mescolata casualmente.
`--seed 42` permette di riprodurre l'assegnazione; il seme resta nella mappa
privata. Con un numero dispari di casi, le due posizioni differiscono di un caso.
I file sono creati con permessi `0600` e la directory con `0700` su Unix; su
Windows si applicano anche le autorizzazioni del filesystem dell'utente.
Anche i pacchetti contengono i testi: inviarli solo a revisori autorizzati e
non pubblicarli automaticamente. Nessun file preesistente viene sovrascritto.

## Giudizi e risultati

Coinvolgere almeno **due revisori distinti per caso**, nascondendo loro la mappa.
Valutare separatamente naturalezza, utilità, aderenza alla voce/registro e fedeltà:
un testo elegante può alterare una condizione importante. Valutare positivamente
la capacità di lasciare quasi invariati i testi già buoni. Non premiare sinonimi,
lunghezza o punteggi dei rilevatori AI in modo automatico.

Dopo avere bloccato i giudizi, rivelare la mappa e convertire le scelte A/B in un
file JSONL di voti. I campi sono esattamente questi:

```json
{"case_id":"email-11","reviewer_id":"r01","preference":"tie","critical_error":false}
```

È un esempio di formato, **non un voto raccolto**. Preferenze ammesse: `skill`,
`baseline`, `tie`. Una coppia caso/revisore duplicata viene rifiutata. I voti
devono riferirsi a casi heldout esistenti. `critical_error` riguarda il risultato
**della skill**: fatti inventati, negazioni o impegni alterati, condizioni decisive
omesse, istruzioni incorporate eseguite. Un errore della baseline non annulla
quello della skill. Conservare output e voti grezzi, usando revisori pseudonimi.

```sh
python scripts/evaluate.py --validate-cases evals/cases.jsonl --votes /percorso/voti.jsonl
```

Il report distingue:

- `vote_weighted_preference` e il campo compatibile `skill_preference`: quota dei
  voti skill più metà dei pareggi; ogni voto pesa allo stesso modo.
- `case_mean_preference`: media delle preferenze per caso; ogni caso pesa allo
  stesso modo anche se un caso ha ricevuto molti più voti. È la metrica decisionale.
- `critical_errors`, copertura dei revisori, dimensioni e dichiarazioni di origine.

`passed` richiede contemporaneamente **almeno 40 casi heldout**, almeno due
revisori per ciascuno, **zero** errori critici segnalati e preferenza media per
caso **strettamente superiore a 0.60**; il valore esatto 0.60 non passa. Senza voti,
con copertura incompleta o con campioni più piccoli, il risultato rimane
`not_validated`, anche se le preferenze osservate sono alte.

Queste sono soglie preliminari di progetto, non un'analisi di potenza statistica
né una garanzia di efficacia generale. `passed` vale solo per il campione e le
condizioni dichiarate. Nessun risultato del pilot sintetico dimostra prestazioni
su tutti gli utenti o sull'italiano in generale. Il programma segnala il proprio
ambito come `preliminary_sample_only` e le autorizzazioni come `declarations_only`.

Input validi producono exit code 0 anche quando il test non passa; errori di
formato o operativi producono exit code 2 e JSON su stderr. Lo strumento richiede
solo Python 3.11 e libreria standard e non invia dati all'esterno.

## Diagnostica della struttura editoriale

`editorial-structure.jsonl` aggiunge **8 casi sintetici originali**, 4 di sviluppo
e 4 heldout, per osservare ritmo, formule di raccordo, struttura dei paragrafi e
rischio di revisione eccessiva. Include liste utili, voce colloquiale già efficace,
interventi minimi, registro formale, attribuzioni e citazioni da preservare. È un
piccolo set diagnostico separato dal pilot: non è un corpus umano né una
validazione della qualità della skill.

```sh
python scripts/evaluate.py --validate-cases evals/editorial-structure.jsonl
```

Le checklist richiedono un giudizio sul testo completo: non prescrivono parole
vietate, quote di modifiche o punteggi dei rilevatori. Per un confronto usare le
stesse condizioni e il procedimento cieco descritti sopra, valutando insieme
naturalezza e fedeltà. Con soli 4 casi heldout il risultato resta
`not_validated`, anche raccogliendo voti favorevoli. Se i casi heldout vengono
letti per tarare le istruzioni o se ne usano i risultati per modificarle, non
costituiscono più una prova indipendente: occorre un nuovo insieme per la
valutazione successiva.

## Diagnostica della lingua italiana

`italian-language.jsonl` contiene **12 casi sintetici originali**, 8 di sviluppo
e 4 heldout, su sintassi, punteggiatura, ortografia e registri. Le checklist
distinguono gli errori da correggere dalle costruzioni ammissibili da conservare
e richiedono di controllare anche soggetti, riferimenti, modalità e significato.
Citazioni e URL protetti non devono essere uniformati al testo corrente.

```sh
python scripts/evaluate.py --validate-cases evals/italian-language.jsonl
```

È un set diagnostico aggiuntivo, non un corpus umano né una prova di miglioramento
della skill. Non sono stati raccolti giudizi umani: il risultato resta
`not_validated`. Usare i casi development per la taratura; riservare gli heldout
al confronto successivo nelle condizioni descritte sopra. Leggerli per definire
le istruzioni o correggere la skill sulla base dei loro risultati ne elimina
l'indipendenza e richiede un nuovo insieme per la valutazione seguente. Quattro
casi heldout non raggiungono comunque la soglia minima del protocollo.

## Scorrevolezza e fedeltà a confronto

`fluency-fidelity.jsonl` contiene 12 casi sintetici originali: 8 development
e 4 heldout. Copre mail formali, messaggi informali e post, con attenzione a
condizioni, alternative, quantificatori, prospettiva e formule di cortesia.
Include testi già efficaci che possono restare invariati.

```sh
python scripts/evaluate.py --validate-cases evals/fluency-fidelity.jsonl
```

Per le prove di sviluppo si possono confrontare due copie fissate della
skill sugli stessi input, nascondendo la provenienza al revisore. Distinguere
la preferenza per una lettura più scorrevole dal riscontro di aggiunte o
omissioni: un testo più breve non è automaticamente migliore. Registrare
anche pareggi, regressioni e differenze non risolte.

Una revisione svolta da agenti non è una raccolta di giudizi umani e non va
inserita nel file dei voti umani del protocollo. Le prove development non
costituiscono validazione indipendente; conservare i casi heldout per una
prova successiva. Lo stato resta `not_validated`.

La [prova di sviluppo del 14 novembre 2026](reports/2026-11-14-fluency.md)
conserva otto confronti su mail, messaggi e post: una regressione nel primo
aggiornamento, la correzione e otto pareggi nella revisione finale. Fonti,
riscritture, giudizi degli agenti e impronte degli snapshot sono allegati al
rapporto. Non dimostra una superiorità generale né rispetto a `/humanizer`.

La [prova successiva su sei testi nuovi](reports/2026-11-14-fresh-registers.md)
confronta originali e riscritture di tre mail formali e tre messaggi informali,
senza modificare la skill durante il test. Riporta separatamente i giudizi
degli agenti su scorrevolezza e significato, inclusi i due testi invariati.
