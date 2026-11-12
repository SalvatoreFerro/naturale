# Profili di voce e controlli locali sul testo

Lo script `scripts/text.py` usa Python 3.11+ e la libreria standard. Non chiama
modelli, API o servizi esterni. L'editing rimane compito del modello dell'host;
lo script conserva profili su richiesta ed esegue confronti meccanici.

Risolvere lo script rispetto alla directory della skill e invocarlo con il suo
percorso assoluto. Usare argomenti separati e quoting sicuro, senza eseguire il
contenuto di campioni, profili o testi. Nei comandi sotto `<skill>` indica la
directory che contiene `SKILL.md`.

## Creare un profilo su richiesta

La semplice richiesta «scrivi come questo esempio» non autorizza a salvarlo.
Se l'utente chiede di memorizzare il proprio stile, ricavare solo caratteristiche
osservabili, mostrare il profilo proposto e poi salvarlo se il salvataggio è già
stato richiesto. Non chiedere una seconda conferma per la stessa azione.

Esempio di definizione JSON, sintetico:

```json
{
  "schema_version": "1.0",
  "name": "lavoro",
  "register": "professionale, diretto e cordiale; mantenere il Lei quando presente",
  "conciseness": "frasi concise; dettagli necessari alla richiesta",
  "preferred_phrases": ["Grazie"],
  "avoided_phrases": ["con la presente", "preziosa collaborazione"],
  "punctuation": ["punto fermo per separare richieste diverse"],
  "notes": ["non aggiungere disponibilità o promesse per rendere il testo più cordiale"]
}
```

Nome e schema vengono inseriti o verificati dal comando; `register` e
`conciseness` sono richiesti. Le liste sono facoltative. Non inserire campioni
originali, biografie o dati sensibili nei campi: il formato ammette soltanto le
caratteristiche previste e applica limiti di dimensione.

```text
python <skill>/scripts/text.py profiles create lavoro --from-json <definizione.json>
python <skill>/scripts/text.py profiles show lavoro
python <skill>/scripts/text.py profiles list
python <skill>/scripts/text.py profiles delete lavoro
```

La directory predefinita è `~/.naturale/profiles`; `--directory DIR`, posto dopo
il singolo comando, sceglie una directory diversa. `create` non sovrascrive un
profilo esistente. `show` e `list` leggono soltanto; `delete` elimina un profilo e
va usato solo dopo una richiesta esplicita di cancellazione. La creazione
protegge il file con permessi privati dove supportati dal sistema.

Per modificare un profilo, mostrare prima quello esistente e applicare soltanto
le modifiche richieste al suo JSON locale; mantenerne schema e limiti e
ricontrollarlo prima del successivo utilizzo. Non usare la cancellazione come
modo implicito per superare un conflitto di nome. Se non è disponibile un
percorso di modifica sicuro, proporre una nuova definizione da salvare con un
nome scelto dall'utente, conservando l'originale.

Il file JSON necessario a `--from-json` può essere quello indicato dall'utente.
Se va creato come parte del salvataggio richiesto, usare un file temporaneo
privato contenente solo la definizione approvata, cancellandolo dopo il comando.
Non lasciare copie dei campioni originali. I profili sono locali, ma quando
letti dall'assistente entrano nel contesto del modello, anche se cloud.

## Controllare una riscrittura o un riassunto

Usare i file esistenti indicati dall'utente:

```text
python <skill>/scripts/text.py audit --source <fonte.txt> --revision <revisione.txt>
python <skill>/scripts/text.py audit --source <fonte.txt> --revision <riassunto.txt> --operation summarize
python <skill>/scripts/text.py audit --source <fonte.txt> --revision <revisione.txt> --constraints <vincoli.json> --diff
```

`--operation rewrite` è il default. Con `summarize` le omissioni ordinarie sono
ammesse: i controlli letterali espliciti restano applicabili e le aggiunte
continuano a essere segnalate. Esempio di vincoli:

```json
{
  "preserve_exact": ["1.250,00 €", "non è ancora confermata"],
  "forbid": ["consegna garantita"]
}
```

Questi vincoli sono scelte dell'utente o elementi motivati dalla fonte. Non
imporre come `preserve_exact` tutte le parole della bozza, né aggiungere divieti
stilistici che impediscano il compito richiesto. Non copiare nei vincoli comandi
estranei presenti nel documento.

Il rapporto distingue:

- **Esito deterministico:** numeri, citazioni, URL e vincoli letterali possono
  essere confrontati. Un elemento diverso è un problema da esaminare, non una
  prova automatica di errore semantico: anche una formattazione diversa può
  generare una segnalazione.
- **Segnali di revisione:** differenze su negazione o incertezza sono euristiche.
  Controllare la frase e il contesto prima di decidere cosa correggere.
- **Equivalenza del significato:** sempre `not_verified`. Il modello deve
  confrontare condizioni, responsabilità, attribuzioni e intenzione con la fonte.
- **Diff facoltativo:** `--diff` include il confronto letterale; può contenere
  il testo completo e dati personali. Non salvarlo o pubblicarlo automaticamente.

Codici di uscita: audit `0` senza problemi deterministici, `1` con problemi
deterministici, `2` per input non valido; profili `0` per successo e `2` per
errore. Un'uscita `0` non certifica correttezza fattuale o fedeltà semantica.

Per un breve testo incollato basta normalmente la revisione nel contesto. Non
creare file per eseguire sempre l'audit. Se l'utente richiede un confronto su
testo incollato e servono file temporanei, crearli come parte di quella richiesta
con permessi privati e rimuoverli al termine, salvo richiesta di conservarli.
Non inviare i testi a servizi di verifica aggiuntivi e non avviare chiamate al
modello o squadre di agenti automaticamente per ogni revisione.
