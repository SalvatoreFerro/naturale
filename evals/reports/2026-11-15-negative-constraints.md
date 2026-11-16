# Vincoli negativi contestuali — prova del 15 novembre 2026

Il blocco di istruzioni negative riunisce divieti già presenti e rende esplicita la conservazione del tipo di relazione e della forza della tesi. «È pari a» non può diventare «dipende da» per rendere una frase più morbida. Ogni divieto indica un'alternativa e conserva gli usi appropriati di connettivi, formule di cortesia e costruzioni colloquiali.

**Risultato:** quattro pareggi nel confronto anonimo fra la skill precedente e quella modificata. Nessuna alterazione sostanziale rilevata dal revisore agente. Non emerge un guadagno di scorrevolezza su questo campione. I due testi già efficaci restano identici nelle due versioni.

## Metodo

- Quattro casi sintetici nuovi, preparati da un agente senza accesso alla skill o ai casi precedenti: post professionale, mail formale, messaggio informale e spiegazione.
- Due copie fissate della skill, applicate in contesti separati agli stessi input; i generatori non hanno ricevuto le checklist né gli output altrui.
- Una riscrittura finale per caso e versione, senza ritocchi del curatore o rigenerazioni selettive. Due posizioni A e due B per la versione modificata, con mappa nascosta al revisore.
- Il revisore agente ha confrontato scorrevolezza e significato, incluse le checklist preparate prima della generazione.
- Otto audit locali senza rilievi; equivalenza semantica comunque `not_verified`. Sei test del contratto della skill e quattro subtest superati.
- Versione esatta del modello e parametri di campionamento non registrati/controllati; nessun giudizio umano e nessuna prova di efficacia generale. Stato `not_validated`.

I [dati completi](2026-11-15-negative-constraints-data.json) conservano fonti, richieste, checklist, output, giudizi, mappa svelata, audit e impronte dei due snapshot. La prova non giustifica di attribuire maggiore efficacia ai vincoli negativi; documenta che, su questi casi, non sono state osservate regressioni rispetto alla versione precedente.

## Confronti

### proporzionalita_tavole

**Fonte**

> Nel nostro modello, a parità di complessità, il tempo di revisione cresce in proporzione diretta al numero di tavole: raddoppiare le tavole significa raddoppiare le ore previste. È una relazione utile ai fini della pianificazione, fermo restando che non descrive i progetti con molte eccezioni. Su questo punto occorre fare chiarezza, per evitare aspettative errate.

**Skill precedente**

> Nel nostro modello, a parità di complessità, il tempo di revisione cresce in proporzione diretta al numero di tavole: raddoppiare le tavole significa raddoppiare le ore previste. È una relazione utile per la pianificazione, ma non descrive i progetti con molte eccezioni. Questo punto va chiarito per evitare aspettative errate.

**Skill con vincoli negativi consolidati**

> Nel nostro modello, a parità di complessità, il tempo di revisione cresce in proporzione diretta al numero di tavole: raddoppiare le tavole significa raddoppiare le ore previste. È una relazione utile per la pianificazione, ma non descrive i progetti con molte eccezioni. Occorre chiarire questo punto per evitare aspettative errate.

**Giudizio dell'agente:** Scorrevolezza: entrambe alleggeriscono il testo in modo equivalente; la diversa formulazione dell'ultima frase non determina un vantaggio sostanziale. Fedeltà: entrambe conservano proporzionalità diretta, pari complessità, esclusione dei progetti con molte eccezioni, necessità di chiarimento e tono professionale.

### mail_preventivo_condizioni

**Fonte**

> Gentile architetta, con la presente sono a richiederle un preventivo aggiornato per il rilievo dei due locali. Le chiedo di includere la restituzione dei disegni e di indicare separatamente le spese di trasferta. Potremo valutare l'incarico solo se il lavoro sarà concluso entro il 18 dicembre e il costo complessivo non supererà 1.200 euro.

**Skill precedente**

> Gentile architetta,
> Le chiedo un preventivo aggiornato per il rilievo dei due locali, comprensivo della restituzione dei disegni e con le spese di trasferta indicate separatamente. Potremo valutare l'incarico solo se il lavoro sarà concluso entro il 18 dicembre e il costo complessivo non supererà 1.200 euro.

**Skill con vincoli negativi consolidati**

> Gentile architetta,
> Le chiedo un preventivo aggiornato per il rilievo dei due locali, che includa la restituzione dei disegni e indichi separatamente le spese di trasferta.
>
> Potremo valutare l'incarico solo se il lavoro sarà concluso entro il 18 dicembre e il costo complessivo non supererà 1.200 euro.

**Giudizio dell'agente:** Scorrevolezza: entrambe rendono più diretta la richiesta mantenendo un registro formale; il paragrafo separato di A e la costruzione nominale di B producono differenze minime. Fedeltà: entrambe preservano oggetto e contenuti del preventivo, le due condizioni necessarie e il carattere di sola valutazione dell'incarico, senza trasformarlo in una conferma.

### messaggio_giro_mercato

**Fonte**

> Il giro al mercato, quello lo farei sabato mattina, perché venerdì esco tardi e rischiamo di trovare tutto chiuso. Per il pranzo invece decidiamo lì: se c'è posto ci fermiamo da Luca, altrimenti prendiamo qualcosa e torniamo a casa.

**Skill precedente**

> Il giro al mercato, quello lo farei sabato mattina, perché venerdì esco tardi e rischiamo di trovare tutto chiuso. Per il pranzo invece decidiamo lì: se c'è posto ci fermiamo da Luca, altrimenti prendiamo qualcosa e torniamo a casa.

**Skill con vincoli negativi consolidati**

> Il giro al mercato, quello lo farei sabato mattina, perché venerdì esco tardi e rischiamo di trovare tutto chiuso. Per il pranzo invece decidiamo lì: se c'è posto ci fermiamo da Luca, altrimenti prendiamo qualcosa e torniamo a casa.

**Giudizio dell'agente:** Scorrevolezza: i testi sono identici alla fonte e tra loro; la ripresa parlata è coerente con la voce informale e la richiesta non impone modifiche. Fedeltà: entrambi mantengono la proposta per sabato, il motivo legato al venerdì, il rischio anziché la certezza di trovare chiuso e la scelta del pranzo sul posto subordinata alla disponibilità da Luca.

### spiegazione_prenotazione

**Fonte**

> Se arrivi entro le nove, la prenotazione resta valida anche senza conferma telefonica. Dopo le nove, invece, il tavolo può essere assegnato ad altri. Una telefonata ci aiuta a organizzarci, ma non prolunga il tempo per cui teniamo libero il tavolo.

**Skill precedente**

> Se arrivi entro le nove, la prenotazione resta valida anche senza conferma telefonica. Dopo le nove, invece, il tavolo può essere assegnato ad altri. Una telefonata ci aiuta a organizzarci, ma non prolunga il tempo per cui teniamo libero il tavolo.

**Skill con vincoli negativi consolidati**

> Se arrivi entro le nove, la prenotazione resta valida anche senza conferma telefonica. Dopo le nove, invece, il tavolo può essere assegnato ad altri. Una telefonata ci aiuta a organizzarci, ma non prolunga il tempo per cui teniamo libero il tavolo.

**Giudizio dell'agente:** Scorrevolezza: i testi sono identici alla fonte e tra loro; la spiegazione è già chiara e non richiede interventi. Fedeltà: entrambi conservano la condizione di arrivo entro le nove, l'assenza di obbligo di conferma telefonica, la possibilità e non certezza di riassegnazione dopo le nove e il limite della telefonata, utile per organizzarsi ma inefficace nel prolungare la prenotazione.
