# Prova su mail e messaggi nuovi — 14 novembre 2026

La nuova versione di Naturale è stata applicata a sei testi sintetici inediti in questa serie di prove: tre mail formali e tre messaggi informali. La skill è rimasta invariata durante il test; tutte le riscritture sono riportate senza ritocchi successivi.

**Esito osservato:** il revisore agente della scorrevolezza ha preferito la riscrittura in quattro casi, con due miglioramenti estesi e due locali. I due testi già efficaci sono rimasti identici. Un secondo revisore agente non ha rilevato alterazioni sostanziali del significato nei sei casi.

## Come è stata svolta la prova

1. Un agente senza accesso alla skill o ai casi precedenti ha creato sei fonti e le relative checklist. Quattro hanno attriti leggeri o moderati; due sono già naturali.
2. Un agente nuovo ha ricevuto soltanto fonti, richieste e una copia fissata della skill. Le checklist e l'etichetta dei testi già buoni non erano visibili.
3. Un revisore distinto ha confrontato le coppie A/B senza conoscere le etichette fonte/riscrittura. La posizione della riscrittura era controbilanciata: tre A e tre B. Ha valutato scorrevolezza e registro, senza premiare automaticamente la brevità.
4. Un secondo revisore ha confrontato fonti e risultati per fedeltà, controllando testi completi e checklist. L'audit locale è stato eseguito separatamente sui sei casi.
5. È stato verificato che i sei testi non coincidessero, anche normalizzando spazi e maiuscole, con quelli dei dataset JSONL precedenti. Le impronte dei file della skill sono rimaste identiche a quelle della copia usata nel test.

I [dati completi](2026-11-14-fresh-registers-data.json) conservano fonti, richieste, checklist, output integrali, giudizi, mappa A/B svelata, audit e impronte della skill.

Questa prova confronta ciascuna riscrittura con il proprio originale, non con la versione precedente della skill. I casi sono sintetici, con una sola generazione per caso e giudizi di agenti, senza valutazioni umane. Versione esatta del modello e parametri di campionamento non sono registrati/controllati. Il risultato descrive questo campione; lo stato resta `not_validated`.

## Risultati caso per caso

| Caso | Scorrevolezza | Significato |
| --- | --- | --- |
| Mail formale: sala del centro civico | Riscrittura preferita; più passaggi migliorati | Nessuna alterazione sostanziale rilevata |
| Mail formale: correzione del certificato | Riscrittura preferita; miglioramento locale | Nessuna alterazione sostanziale rilevata |
| Mail formale: sopralluogo | Parità; testo invariato | Nessuna alterazione sostanziale rilevata |
| Messaggio informale: cura del gatto | Riscrittura preferita; miglioramento locale | Nessuna alterazione sostanziale rilevata |
| Messaggio informale: recupero dello zaino | Parità; testo invariato | Nessuna alterazione sostanziale rilevata |
| Messaggio informale: spesa condivisa | Riscrittura preferita; più passaggi migliorati | Nessuna alterazione sostanziale rilevata |

## Audit locale

Cinque casi non hanno generato rilievi. Nella mail sulla sala l'audit ha segnalato un diverso numero di indicatori di condizione: l'apertura ora contiene «per sapere se la sala [...] è disponibile». La richiesta di disponibilità era già presente nella fonte; questa interrogativa indiretta non aggiunge un vincolo. La condizione sulla gratuità è rimasta esplicita. Il controllo nel contesto non ha rilevato una variazione di significato.

I sei audit non hanno trovato differenze deterministiche. Il loro risultato dichiara comunque `semantic_equivalence: not_verified`: l'assenza di segnali non certifica il significato.

## Prima e dopo

### Mail formale: sala del centro civico

**Prima**

> Gentile dottoressa Serra,
> le scrivo in merito alla possibilità di utilizzare la sala del centro civico per un incontro del nostro gruppo di lettura. L'incontro sarebbe sabato 12 dicembre, dalle 16 alle 18, e per quanto riguarda i partecipanti prevediamo circa quindici persone. Avremmo necessità della sala soltanto se fosse disponibile gratuitamente. Per il riordino finale ce ne occuperemmo noi, mentre per l'apertura avremmo bisogno di sapere se è prevista la presenza di un vostro incaricato. Le chiedo quindi un riscontro sulla disponibilità della sala e su questo aspetto dell'apertura.
> Cordiali saluti,
> Marta Riva

**Dopo**

> Gentile dottoressa Serra,
> le scrivo per sapere se la sala del centro civico è disponibile per un incontro del nostro gruppo di lettura. L'incontro sarebbe sabato 12 dicembre, dalle 16 alle 18, con circa quindici partecipanti. Avremmo necessità della sala soltanto se fosse disponibile gratuitamente.
> Ci occuperemmo noi del riordino finale; per l'apertura, invece, le chiedo se è prevista la presenza di un vostro incaricato.
> Cordiali saluti,
> Marta Riva

**Scorrevolezza:** B rende più immediata la richiesta iniziale, integra con naturalezza il numero dei partecipanti e presenta con maggiore fluidità riordino e apertura. La separazione in paragrafi facilita la lettura; la chiusura evita di ripetere richieste già espresse chiaramente. Il tono resta cortese e adeguato a una richiesta formale.

**Contenuto conservato:**

- Restano invariati destinataria, mittente, sala del centro civico e finalità dell'incontro del gruppo di lettura.
- Sono conservati sabato 12 dicembre, l'orario 16–18 e la stima di circa quindici partecipanti.
- L'utilizzo resta subordinato alla gratuità e il riordino finale rimane a carico del gruppo, con la stessa formulazione condizionale.
- La richiesta di disponibilità è espressa nella frase iniziale; la domanda sulla presenza di un incaricato per l'apertura resta esplicita. L'eliminazione della ricapitolazione finale non elimina queste richieste.
- Restano il registro formale, la cortesia e il carattere proposto dell'incontro.

### Mail formale: correzione del certificato

**Prima**

> Buongiorno,
> con riferimento al certificato di partecipazione ricevuto ieri, segnalo che nel documento il mio cognome risulta scritto come «Bellini», mentre il cognome corretto è «Bettini». La data del corso e il numero delle ore risultano invece corretti. Avrei necessità di consegnare il certificato al mio ufficio entro venerdì; qualora la correzione richiedesse più tempo, vi chiederei di indicarmi una data orientativa, così da poter avvisare l'ufficio. Allego il documento ricevuto per consentirvi di verificare quanto segnalato. Per l'invio della versione corretta potete utilizzare questo stesso indirizzo.
> Grazie per l'assistenza,
> Luca Bettini

**Dopo**

> Buongiorno,
> nel certificato di partecipazione ricevuto ieri il mio cognome è riportato come «Bellini», mentre quello corretto è «Bettini». La data del corso e il numero delle ore risultano invece corretti.
> Avrei necessità di consegnare il certificato al mio ufficio entro venerdì; qualora la correzione richiedesse più tempo, vi chiederei una data orientativa per poter avvisare l'ufficio. Allego il documento ricevuto per consentirvi di verificare quanto segnalato. Per inviare la versione corretta potete utilizzare questo stesso indirizzo.
> Grazie per l'assistenza,
> Luca Bettini

**Scorrevolezza:** Il vantaggio principale di B è nell'apertura: l'errore sul cognome emerge senza il doppio passaggio introduttivo «con riferimento» e «segnalo che nel documento». Il capoverso separa utilmente la segnalazione dalla richiesta sui tempi. Il resto mantiene sostanzialmente lo stesso ritmo e registro, con differenze modeste.

**Contenuto conservato:**

- Restano il certificato di partecipazione ricevuto ieri, il cognome errato Bellini e quello corretto Bettini.
- Restano corrette sia la data del corso sia il numero delle ore.
- Sono conservati la necessità di consegna all'ufficio entro venerdì e, se la correzione richiedesse più tempo, la richiesta di una data orientativa per avvisare l'ufficio.
- Restano l'allegato per la verifica della segnalazione e la possibilità di inviare la versione corretta allo stesso indirizzo.
- Identità del mittente, registro formale, ringraziamento e gradi di certezza restano invariati.

### Mail formale: sopralluogo

**Prima**

> Gentile architetta Neri,
> le propongo un sopralluogo nell'appartamento mercoledì prossimo alle 10, per valutare insieme la parete da rimuovere. L'amministratore dovrebbe inviarmi la planimetria entro martedì; se non arrivasse, preferirei rinviare l'incontro. Le confermerò quindi l'appuntamento martedì pomeriggio. Sarò presente anch'io e mi occuperò di ritirare le chiavi dal custode. Mi faccia sapere se l'orario proposto è compatibile con i suoi impegni.
> Cordiali saluti,
> Elena Conti

**Dopo**

> Gentile architetta Neri,
> le propongo un sopralluogo nell'appartamento mercoledì prossimo alle 10, per valutare insieme la parete da rimuovere. L'amministratore dovrebbe inviarmi la planimetria entro martedì; se non arrivasse, preferirei rinviare l'incontro. Le confermerò quindi l'appuntamento martedì pomeriggio. Sarò presente anch'io e mi occuperò di ritirare le chiavi dal custode. Mi faccia sapere se l'orario proposto è compatibile con i suoi impegni.
> Cordiali saluti,
> Elena Conti

**Scorrevolezza:** I testi sono identici. La sequenza proposta, condizione per il rinvio, conferma e organizzazione è leggibile; il registro cortese è coerente con il destinatario professionale.

**Contenuto conservato:**

- La revisione coincide integralmente con la fonte.
- Restano proposta di sopralluogo nell'appartamento mercoledì prossimo alle 10 e valutazione congiunta della parete da rimuovere.
- Restano l'attesa non certa della planimetria dall'amministratore entro martedì e la preferenza di rinviare in caso di mancato arrivo.
- Restano conferma martedì pomeriggio, presenza di Elena, ritiro delle chiavi dal custode a suo carico e domanda sulla compatibilità dell'orario.
- Sono invariati destinataria, mittente, cortesia e registro formale.

### Messaggio informale: cura del gatto

**Prima**

> Ciao Bea, per il gatto volevo dirti che sabato posso passare io, ma riesco a passare solo dopo le sei. Per domenica invece non te lo so ancora dire, perché forse devo accompagnare mia madre alla stazione. Il cibo lo trovo nel mobile vicino al frigo, giusto? Per le medicine preferirei che ci pensassi tu prima di partire, visto che non gliele ho mai date. Se domenica serve trovare qualcun altro, dimmelo: posso chiedere a Davide, però non so se sia libero.

**Dopo**

> Ciao Bea, sabato posso passare io per il gatto, ma solo dopo le sei. Per domenica invece non te lo so ancora dire, perché forse devo accompagnare mia madre alla stazione. Il cibo lo trovo nel mobile vicino al frigo, giusto? Per le medicine preferirei che ci pensassi tu prima di partire, visto che non gliele ho mai date. Se domenica serve trovare qualcun altro, dimmelo: posso chiedere a Davide, però non so se sia libero.

**Scorrevolezza:** A ha un'apertura più fluida: comunica disponibilità e limite orario senza la ripetizione ravvicinata di «passare» presente in B. Entrambe le aperture sono plausibili in un messaggio informale; la preferenza riguarda soltanto il ritmo della prima frase, mentre il resto è identico.

**Contenuto conservato:**

- La disponibilità del mittente per il gatto resta limitata a sabato dopo le sei.
- La disponibilità domenicale resta incerta per il possibile accompagnamento della madre alla stazione.
- La collocazione del cibo nel mobile vicino al frigo resta una domanda di conferma.
- Resta la preferenza che Bea si occupi delle medicine prima della partenza, motivata dalla mancanza di esperienza del mittente nel somministrarle al gatto.
- Restano la richiesta di essere avvisato se serve un'altra persona domenica, la possibilità di chiedere a Davide e l'incertezza sulla sua disponibilità.
- Il taglio dell'introduzione e della ripetizione iniziale mantiene destinataria, tono informale e intenzione del messaggio.

### Messaggio informale: recupero dello zaino

**Prima**

> Ciao Leo, ho lasciato lo zaino blu sotto il tavolo in cucina. Dentro ci sono anche le chiavi della bici, quindi mi servirebbe recuperarlo stasera. Posso passare verso le otto, se sei a casa. Altrimenti, se per te va bene, potresti lasciarlo alla portiera? La avviso io, ma aspetta la mia conferma prima di portarglielo.

**Dopo**

> Ciao Leo, ho lasciato lo zaino blu sotto il tavolo in cucina. Dentro ci sono anche le chiavi della bici, quindi mi servirebbe recuperarlo stasera. Posso passare verso le otto, se sei a casa. Altrimenti, se per te va bene, potresti lasciarlo alla portiera? La avviso io, ma aspetta la mia conferma prima di portarglielo.

**Scorrevolezza:** I testi sono identici. Il tono è naturale per un messaggio personale e i riferimenti allo zaino, alla portiera e alla conferma si seguono senza difficoltà.

**Contenuto conservato:**

- La revisione coincide integralmente con la fonte.
- Restano colore e posizione dello zaino, presenza delle chiavi della bici e necessità di recuperarlo stasera.
- Il passaggio verso le otto resta subordinato alla presenza di Leo a casa.
- Resta l'alternativa della consegna alla portiera, subordinata all'assenso di Leo.
- Il mittente resta responsabile di avvisare la portiera e Leo deve attendere la sua conferma prima della consegna.
- Destinatario, tono informale, cortesia e natura condizionale delle proposte restano invariati.

### Messaggio informale: spesa condivisa

**Prima**

> Ragazzi, per la spesa di domani posso andare io dopo il lavoro. Per quello che riguarda le cose da prendere, mandatemi la lista entro le quattro, perché dopo potrei non riuscire a guardare il telefono. Pensavo di anticipare io fino a 60 euro; se viene di più vi scrivo prima di pagare. Le bevande però restano a carico di ciascuno, come avevamo detto. Per dividere il resto farei in parti uguali, se siete d'accordo. Per il pane preferirei prenderlo sabato mattina, quindi quello domani lo lascerei fuori.

**Dopo**

> Ragazzi, domani posso andare io a fare la spesa dopo il lavoro. Mandatemi la lista entro le quattro, perché dopo potrei non riuscire a guardare il telefono. Pensavo di anticipare io fino a 60 euro; se viene di più, vi scrivo prima di pagare. Le bevande però restano a carico di ciascuno, come avevamo detto. Il resto lo dividerei in parti uguali, se siete d'accordo. Il pane preferirei prenderlo sabato mattina, quindi domani lo lascerei fuori.

**Scorrevolezza:** B migliora il ritmo in più punti: l'apertura è più lineare, la richiesta della lista arriva subito e la divisione delle spese è espressa con una costruzione più naturale. Riduce inoltre la serie di frasi introdotte da «Per», che in A rende il messaggio più scandito e macchinoso. Il tono resta adatto a un gruppo informale e le condizioni rimangono facili da seguire.

**Contenuto conservato:**

- Restano la disponibilità a fare la spesa domani dopo il lavoro e la richiesta della lista entro le quattro.
- L'impossibilità di controllare il telefono dopo le quattro resta una possibilità, non una certezza.
- L'anticipo fino a 60 euro resta una proposta; oltre tale importo resta l'impegno di scrivere al gruppo prima di pagare.
- Le bevande restano a carico di ciascuno secondo un accordo già preso.
- La divisione del resto in parti uguali resta subordinata all'accordo del gruppo.
- Restano la preferenza di acquistare il pane sabato mattina e la proposta di escluderlo dalla spesa di domani, insieme al tono informale rivolto al gruppo.
