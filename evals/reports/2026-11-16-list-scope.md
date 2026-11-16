# Ambito, vincoli e richieste negli elenchi — 16 novembre 2026

La modifica distingue un dettaglio indeterminato da una relazione già esplicita: un'etichetta retta da un divieto conserva quel divieto. Una voce senza relazione dichiarata non diventa automaticamente un'istruzione. Le precisazioni comuni precedono gli esempi; le richieste vengono raccordate all'intero elenco, valutando insieme introduzione e forma delle voci.

Sono stati eseguiti tre passaggi sul post dell'utente e sugli stessi quattro controlli sintetici, con snapshot fissate e contesti nuovi. Una generazione per input e snapshot, nessun ritocco esterno. Nel primo passaggio il punto 5 del post era una frase autonoma fra voci nominali. Nel secondo l'elenco era parallelo, ma l'introduzione restava sospesa; un controllo attribuiva a etichette neutre la funzione di indicazioni. Sono stati corretti anche gli esempi della guida che favorivano quei risultati.

Nell'ultimo passaggio il post mantiene un'introduzione completa e cinque voci verbali. L'integralità del materiale precede gli esempi; il punto 5 esprime la richiesta; sulla lunghezza resta il rapporto di esclusione originale, senza inventare limiti o trasformarlo in indicazioni generiche. Il revisore segnala ancora la ripetizione del pronome del destinatario come possibile attrito stilistico. Fonte, output integrale e confronto con il campione /humanizer sono nella conversazione.

I quattro controlli finali sono stati giudicati fedeli dal revisore agente. I [dati completi](2026-11-16-list-scope-data.json) conservano tutte le riscritture sintetiche, le richieste e gli hash delle snapshot. Gli esiti negativi dei passaggi precedenti restano registrati.

È una prova di sviluppo: gli stessi casi sono stati riutilizzati per correggere la guida. Non è una validazione indipendente né un confronto controllato con la precedente installazione o con il programma Humanizer. Nessun giudizio umano; versione esatta del modello e campionamento non registrati/controllati. Stato `not_validated`.

Il contratto della skill ha superato sei test e quattro subtest; entrypoint e parti coperte da questi test sono rimasti invariati nei tre passaggi. Il validatore generico rifiuta il campo `compatibility`, già presente e non modificato. Questi controlli non certificano equivalenza semantica.

## esclusioni

Richiesta: Rendi il testo più naturale e scorrevole, senza cambiarne il significato o risolverne le ambiguità.

**Fonte**

> Nel messaggio al grafico scrivo cosa escludere: caratteri, effetti, dimensioni.

**Primo passaggio**

> Nel messaggio al grafico indico cosa escludere: caratteri, effetti e dimensioni.

**Secondo passaggio**

> Nel messaggio al grafico indico i caratteri, gli effetti e le dimensioni da escludere.

**Terzo passaggio, versione installata**

> Nel messaggio al grafico indico quali caratteri, effetti e dimensioni escludere.

L'esclusione resta esplicita in tutti i passaggi; la versione finale non inventa caratteri, effetti o dimensioni specifici.

## qualificatore

Richiesta: Rendi il testo più naturale e scorrevole, senza cambiarne il significato o risolverne le ambiguità.

**Fonte**

> Per il catalogo invio i testi: schede dei prodotti, didascalie, note. Tutti già approvati.

**Primo passaggio**

> Per il catalogo invio i testi, tutti già approvati: schede dei prodotti, didascalie e note.

**Secondo passaggio**

> Per il catalogo invio i testi, tutti già approvati: schede dei prodotti, didascalie e note.

**Terzo passaggio, versione installata**

> Per il catalogo invio i testi, tutti già approvati: schede dei prodotti, didascalie e note.

La precisazione precede gli esempi e continua a riguardare tutti i testi. Stesso risultato nei tre passaggi.

## richiesta

Richiesta: Rendi il testo più naturale e scorrevole, senza cambiarne il significato o risolverne le ambiguità.

**Fonte**

> Nella mail al centro sportivo scrivo tre cose: il corso che mi interessa, i giorni in cui sono libero, che mi dicano se c'è ancora posto.

**Primo passaggio**

> Nella mail al centro sportivo indico il corso che mi interessa e i giorni in cui sono libero e chiedo di farmi sapere se c'è ancora posto.

**Secondo passaggio**

> Nella mail al centro sportivo indico il corso che mi interessa e i giorni in cui sono libero, e chiedo che mi dicano se c'è ancora posto.

**Terzo passaggio, versione installata**

> Nella mail al centro sportivo indico il corso che mi interessa e i giorni in cui sono libero, e chiedo che mi dicano se c'è ancora posto.

La richiesta di risposta diventa esplicita senza cambiare disponibilità, corso o domanda sul posto. Nel primo passaggio la doppia congiunzione lasciava un attrito. Il conteggio non è più dichiarato, ma i tre contenuti restano distinti.

## parametri_neutri

Richiesta: Rendi il testo più naturale e scorrevole, senza cambiarne il significato o risolverne le ambiguità.

**Fonte**

> Nel messaggio al grafico scrivo: caratteri, effetti, dimensioni.

**Primo passaggio**

> Nel messaggio al grafico scrivo: caratteri, effetti e dimensioni.

**Secondo passaggio**

> Nel messaggio al grafico do indicazioni su caratteri, effetti e dimensioni.

**Terzo passaggio, versione installata**

> Nel messaggio al grafico scrivo: caratteri, effetti e dimensioni.

Nel secondo passaggio 'do indicazioni' attribuiva una funzione non dichiarata. L'esempio nella guida che autorizzava questa trasformazione è stato corretto. Nel terzo resta soltanto la coordinazione delle etichette.
