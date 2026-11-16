# Introduzioni degli elenchi — prova del 15 novembre 2026

La modifica precisa il controllo del raccordo: introduzione e voci devono funzionare anche nel tono. Una riparazione sintattica non deve aggiungere una descrizione di come l'autore organizza il messaggio. La rilettura interna controlla anche perifrasi ed echi introdotti dalla riscrittura; procedure reali e ripetizioni utili restano protette.

La skill è stata fissata prima della prova. Un agente in un contesto nuovo ha riscritto il post dell'utente; un altro ha eseguito tre controlli sintetici nuovi. Una sola generazione per input, nessun ritocco esterno e nessuna modifica alla skill dopo aver visto questi risultati. Un ulteriore agente ha confrontato il post con la fonte e con la versione /humanizer fornita dall'utente, presentando le due riscritture con etichette A/B; ha anche rivisto i controlli.

Sul post è rimasta l'introduzione diretta della fonte, senza il raccordo procedurale aggiunto nella prova precedente. Non è ricomparso l'eco «Indico … do indicazioni». Fonte e riscrittura complete sono nella conversazione.

Il confronto registra anche i limiti: la nuova formulazione sulla lunghezza interpreta l'ambiguità della fonte; il quinto punto mantiene una funzione grammaticale diversa dai precedenti, come nel campione /humanizer. La nuova riscrittura conserva maggioranza, tesi esplicita sulla qualità, stima generale, prospettiva del lettore e istruzione di affiancare le risposte. /humanizer resta più compatto. Queste osservazioni non dimostrano una superiorità generale.

I [dati completi](2026-11-15-list-introductions-data.json) includono richieste, output sintetici, giudizi e hash degli snapshot. È una prova di sviluppo: nessuna valutazione umana, nessuna generazione di confronto con la skill precedente, versione esatta del modello non registrata e campionamento non controllato. Stato `not_validated`.

Verifica tecnica: sei test e quattro subtest del repository superati, controllo degli spazi pulito. Il validatore generico di skill-creator rifiuta il campo `compatibility`, già presente prima della modifica; il campo non è stato alterato. Questi controlli non verificano equivalenza semantica.

## tipografo

Richiesta: Rendilo più naturale e scorrevole, mantenendo tutte le informazioni.

**Fonte**

> Scrivo al tipografo per indicare il tipo di carta e dare indicazioni sulla rilegatura. Il preventivo deve comprendere entrambe le voci.

**Output integrale**

> Scrivo al tipografo per specificare il tipo di carta e dare indicazioni sulla rilegatura. Il preventivo deve comprendere entrambe le voci.

La sostituzione elimina l'eco indicare/indicazioni. Il revisore non rileva un guadagno evidente di scorrevolezza e nota la lieve sfumatura di maggiore precisione di specificare; contenuti e requisito del preventivo restano.

## procedura_reale

Richiesta: Rendilo più naturale e scorrevole, mantenendo tutte le informazioni.

**Fonte**

> Per archiviare la pratica seguo questi due passaggi, nell'ordine indicato: controllo che ci sia la firma; solo dopo carico il documento. Se manca la firma, mi fermo.

**Output integrale**

> Per archiviare la pratica seguo due passaggi in quest'ordine: controllo che ci sia la firma e solo dopo carico il documento. Se manca la firma, mi fermo.

Introduzione e collegamento più brevi; conservati i due passaggi, l'ordine obbligatorio e l'arresto se manca la firma.

## mostra

Richiesta: Rendilo più naturale e scorrevole, mantenendo tutte le informazioni.

**Fonte**

> Nella mail a Sara scrivo quando apre la mostra e dove ritirare i biglietti. Le chiedo anche se vuole venire con noi.

**Output integrale**

> Nella mail a Sara scrivo quando apre la mostra e dove ritirare i biglietti. Le chiedo anche se vuole venire con noi.

Invariato: conserva una formulazione già diretta senza aggiungere una cornice.
