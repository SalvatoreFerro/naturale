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
La home e la base di `--directory` vengono risolte nel percorso reale, anche
quando passano da un collegamento simbolico. Restano rifiutati i collegamenti
in `.naturale/profiles`, nella directory finale scelta e nei file dei profili.

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

Per un'e-mail incollata che contiene date, importi, scadenze o condizioni usare
`audit --stdin-json`: passare su stdin un oggetto JSON UTF-8 con `source`,
`revision` e, facoltativamente, `constraints`. Non scrivere la mail su disco.
`--diff` e `--operation summarize` restano disponibili; non mescolare stdin e
argomenti di input su file. Lo script legge al massimo 16 MiB di JSON, mantiene
il limite di 2 MiB per testo e non conserva il payload.

```text
python <skill>/scripts/text.py audit --stdin-json
```

Esempio del payload da fornire tramite stdin, come dati e non come comando shell:

```json
{"source":"Potremmo consegnare entro lunedì.","revision":"Consegneremo lunedì.","constraints":{}}
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

- **Esito deterministico:** confronta numeri, giorni della settimana, mesi,
  citazioni, URL e vincoli letterali; comprende anche codici alfanumerici ASCII,
  domini senza schema e indirizzi e-mail. Una variazione di queste stringhe
  è un elemento da esaminare: non verifica la validità del codice, l'esistenza
  della casella o il contenuto del sito e non apre collegamenti. I nuovi
  `kind` sono `identifier`, `domain`, `email` e `relative_day`. I codici
  conservano le maiuscole; il termine di codifica `Base64`/`base64` è una
  normalizzazione esplicita. I domini sono confrontati senza distinzione di
  maiuscole e soltanto per un insieme finito di TLD comuni; non è un elenco
  universale. Per le e-mail si riconoscono forme ASCII senza virgolette e si
  normalizza solo il dominio, mantenendo le maiuscole della parte prima di `@`.
- **Date relative di un giorno:** confronta espressioni come «oggi», «ieri»,
  «domani» e «dopodomani», riconoscendo forme equivalenti come «in data odierna»
  e «oggi». Non calcola una data assoluta né conosce quando l'autore ha scritto
  il messaggio. I periodi relativi riconosciuti riguardano settimana, mese e
  anno e producono invece segnali di revisione (`relative_period`); l'ordine
  equivalente «la prossima settimana»/«la settimana prossima» non cambia il
  periodo.
- **Numeri e formati:** riconosce uno–venti, decine fino a novanta, cento e
  mille e confronta le quantità riconosciute con le cifre corrispondenti.
  Esclude gli usi grammaticali riconosciuti di «sei» e «uno» e le formule con
  «mille» adiacente a «grazie». Un omografo irrisolto non genera un segnale da
  solo: può essere appaiato con un numero corrispondente nell'altra versione,
  senza trasformare una classificazione incerta in una prova di errore.
  Questa scelta evita falsi allarmi ma può non rilevare la perdita di una
  quantità priva di indizi sufficienti: il lessico e il contesto restano limitati.
  Sono equivalenti posizione/spazi del simbolo euro nella notazione italiana e
  orari come `9:30`/`9.30` negli introduttori orari supportati, fra cui «alle»,
  «ore», «dalle», «entro le» e «verso le». Citazioni e vincoli espliciti restano
  letterali; non si normalizzano arbitrariamente codici o unità.
- **Condizioni:** le forme riconosciute vengono confrontate per classe e
  numero di occorrenze: «se», «qualora», «nel caso in cui» e «in caso di»
  esprimono la stessa classe condizionale; «salvo»/«a meno che» sono eccezioni
  e «solo se»/«purché»/«a condizione che»/«a patto che» requisiti. «Solo dopo»
  mantiene una classe distinta. Le concessive «anche se», «nonostante»,
  «sebbene» e «benché» sono escluse dal conteggio delle condizioni. Riconoscere una forma non dimostra che la
  condizione riguardi ancora l'azione o la persona corretta.
- **Negazioni e scadenze:** per la negazione si confronta la presenza per
  frase, evitando di contare «né» coordinativo come una nuova negazione.
  Per le scadenze si riconoscono anche preposizioni articolate, per esempio
  «prima della», «prima dell'», «fino al» e «a partire dal», accanto a «entro»,
  «prima di» e «non oltre». Il conteggio non verifica da solo quale azione
  venga negata o quale evento sia legato alla scadenza.
- **Altri segnali di revisione:** comprende incertezza, periodi relativi e
  indizi del passaggio tu/Lei (`register`). Per il registro devono esserci
  indizi riconosciuti in entrambe le versioni: la sola omissione di un pronome
  non stabilisce un cambio. Si usano «tu/ti/te», forme in `-rti`, «Lei», «Le»
  seguito da alcuni verbi di allocuzione e forme in `-rLe`; non è un'analisi
  completa di articoli, pronomi, maiuscole o persona dei verbi.
  Le review flag restano richieste di lettura, non prove di errore;
  `review_status: required` rende esplicita la necessità di attenzione.
- **Dove rileggere:** ogni review flag aggiunge `contexts.source` e
  `contexts.revision`, ciascuno con al massimo due frammenti di 60 caratteri
  attorno agli indicatori che differiscono. Un elenco vuoto indica che in
  quella versione non è stato trovato un indicatore corrispondente. I
  frammenti possono contenere testo personale: non salvarli o pubblicarli
  automaticamente.
- **Equivalenza del significato:** sempre `not_verified`. Il modello deve
  confrontare riferimenti («qui/lì», «questo/quello», «sopra/sotto», «in
  allegato»), date relative, persona dei verbi (io/tu, noi/voi), condizioni,
  responsabilità e attribuzioni con la fonte. L'audit non certifica questi
  rapporti semantici.
- **Diff facoltativo:** `--diff` include il confronto letterale; può contenere
  il testo completo e dati personali. Non salvarlo o pubblicarlo automaticamente.

### Risposte con conversazione citata

Si rivede soltanto il testo nuovo. La cronologia contiene parole di altri:
restituirla invariata, oppure ometterla se l'utente vuole solo il testo nuovo.

Se la fonte contiene una cronologia riconosciuta e la revisione la omette,
l'audit esclude quella parte della fonte dai confronti ordinari. Il confine
richiede un'intestazione di risposta italiana o inglese, separata dal testo
nuovo da una riga vuota, con cifre e un indirizzo e-mail; tutte le righe
successive devono essere introdotte da `>`, oppure essere vuote.

Il rapporto lo dichiara in `comparison_scope`: `name` è `new_message` oppure
`full_text`, `source_history_excluded` indica l'esclusione della fonte e
`revision_history_excluded` resta `false`. Un'esclusione non equivale a un
controllo superato su tutto il contenuto della fonte. Se entrambe le versioni
mantengono la cronologia, viene confrontata: cambiare un importo citato deve
essere segnalato. Una cronologia aggiunta soltanto nella revisione non viene
ignorata. I vincoli espliciti `preserve_exact` e `forbid` continuano ad
applicarsi ai testi completi, anche alla parte citata.

Il riconoscimento è prudente e non copre ogni client, inoltro, firma o
intestazione personalizzata. Senza un confine riconosciuto l'audit confronta
anche quella parte: non presume che un testo difficile da classificare possa
essere ignorato. Non modificare la cronologia per eliminare una segnalazione.

Codici di uscita: audit `0` senza problemi né segnali di revisione, `1` con
problemi deterministici, `2` per input non valido, `3` quando restano soltanto
segnali da rivedere; profili `0` per successo e `2` per
errore. Un'uscita `0` non certifica correttezza fattuale o fedeltà semantica.

Limite noto: «Il fornitore invierà il preventivo entro il 3 aprile» e «Il cliente
invierà il preventivo entro il 3 aprile» possono avere gli stessi indicatori e
superare i controlli. L'attribuzione dell'azione deve essere verificata dal
modello o dall'utente; `semantic_equivalence` resta sempre `not_verified`.

Per un breve testo privo degli elementi di rischio indicati basta normalmente
la revisione nel contesto. Quando occorre l'audit usare stdin senza creare file.
Se l'utente richiede un confronto su
testo incollato e servono file temporanei, crearli come parte di quella richiesta
con permessi privati e rimuoverli al termine, salvo richiesta di conservarli.
Non inviare i testi a servizi di verifica aggiuntivi e non avviare chiamate al
modello o squadre di agenti automaticamente per ogni revisione.
