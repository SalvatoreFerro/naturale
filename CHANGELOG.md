# Changelog

## In lavorazione

- Scorrevolezza dei periodi: riferimenti meno ripetitivi, ellissi degli
  elenchi chiarite quando il contesto lo consente e pause fra azioni diverse.
  Esempio operativo con condizioni, responsabilità e scadenza conservate.
- Scorrevolezza: eliminazione dei doppioni a parità di informazioni, raccordi
  più diretti e controllo della fedeltà in entrambe le direzioni. Esplicitati
  ambito dei quantificatori, stato delle azioni e prospettiva io/tu;
  le limitazioni esplicite restano esplicite anche quando si ricompone il ritmo.
- Esempi su mail formali, messaggi informali e post; set separato di 12 casi
  sintetici per confrontare scorrevolezza e conservazione delle sfumature.
- Rapporto di sviluppo su 8 casi con output e giudizi degli agenti conservati:
  corretta una regressione; scorrevolezza finale comparabile alla versione
  precedente, senza nuova validazione umana dichiarata.

- Guida italiana documentata su sintassi, punteggiatura, ortografia e registri
  formali/informali, con fonti Crusca e Treccani; distinzione fra errori,
  varianti, scelte editoriali e ambiguità, senza normalizzazione automatica.
- Esempi di adattamento del registro e sintassi; 12 casi sintetici diagnostici
  aggiuntivi, validati nel formato anche dalla CI.

- Revisione editoriale: diagnosi di struttura e ritmo prima del lessico;
  richieste come «umanizza» consentono di riorganizzare dove serve, con
  precedenza ai vincoli espliciti e alla conservazione del significato.
- Esempi di post, voce già efficace, contrasti informativi e intervento minimo;
  nessuna autobiografia o dettaglio aggiunti per simulare spontaneità.
- Set diagnostico separato con 8 casi sintetici per struttura e fedeltà;
  pilot originale invariato, nessuna nuova valutazione umana dichiarata.

## 0.2.1 — preparazione, non rilasciata

- Audit e-mail: recuperata la sensibilità alle negazioni con conteggi globali
  di negatori primari e «né»; distinte le domande indirette con «anche se».
- Periodi relativi plurali e registro tu/Lei ampliati, anche per revisioni
  miste, possessivi di cortesia e omografi degli enclitici.

- Audit e-mail: condizioni equivalenti e concessive, negazioni coordinate,
  scadenze articolate, date relative, domini, e-mail, codici, segnali di registro
  e frammenti contestuali; ambito esplicito quando si omette la cronologia citata.
- Istruzioni editoriali: verifica di riferimenti, date relative e persona dei
  verbi; conversazioni citate conservate invariate oppure omesse su richiesta.
- Audit: ridotti i falsi allarmi sugli omografi numerici e sugli orari equivalenti, conservando i controlli sulle quantità.
- Audit testi: calendario italiano, numeri in lettere, scadenze, negazioni e
  incertezza; normalizzazione di euro e orari, JSON su stdin ed exit `3` per
  segnali che richiedono revisione. Responsabilità e significato restano
  soggetti a controllo editoriale.
- ExifTool minimo 13.60 condiviso fra diagnostica e immagini, verificato sul
  difetto dei PNG firmati; guida Ubuntu 24.04 per aggiornare la 12.76.
- Privacy GPS-only JPEG/PNG: conservati i campi tecnici IFD0 già presenti,
  con blocco invariato su qualsiasi altra modifica EXIF.
- Avvisi espliciti per nessuna rimozione, testo PNG/commenti JPEG e GPS
  conservati. Il profilo provenance continua a rimuovere solo XMP/JUMBF.
- Errori immagini tipizzati senza valori personali nei riepiloghi.
- Profili utilizzabili attraverso home/base simboliche, con rifiuto dei
  symlink nel deposito e sui file finali e nessuna sovrascrittura.
- Action CI aggiornate e fissate per SHA, matrice estesa a Linux/Python 3.13;
  limite Pillow `<13` conservato.
- Description della skill ridotta a 189 caratteri e manifest facoltativi
  plugin/marketplace Claude, validati con Claude Code 2.1.275.
- Dataset editoriale invariato; nessuna nuova misura della qualità dei modelli.

## 0.2.0 — anteprima

- Profili di voce locali riutilizzabili, creati solo su richiesta, modificabili
  e separati dai campioni originali.
- Tre intensità editoriali: minima, fluidità e strutturale; verifica esplicita
  di fatti, condizioni, responsabilità e incertezza.
- Audit locale di numeri, citazioni, URL e vincoli espliciti, con differenze
  facoltative; nessuna certificazione automatica di equivalenza semantica.
- Rapporti immagini sintetici per impostazione predefinita; dettagli completi
  disponibili esplicitamente e conservabili in file locali privati.
- Elaborazione di cartelle e profilo di pulizia mirata dei metadati personali,
  distinto dalla rimozione XMP/JUMBF già disponibile.
- Diagnosi dell'installazione, ricevute con hash, aggiornamenti da checkout
  locale verificato, backup e ripristino con controllo delle personalizzazioni.
- Dataset di valutazione estensibili e preparazione di confronti ciechi per
  revisori umani. Nessun voto umano o miglioramento misurato viene inventato.
- Fonti e scelte documentate in `docs/RESEARCH.md`; elaborazione immagini
  locale, senza detector o servizi remoti aggiuntivi.

## 0.1.0 — anteprima iniziale

- Skill portabile Claude Code/Codex per testi italiani.
- Ispezione e rimozione locale XMP/JUMBF da JPEG/PNG su copia.
- Installer senza sovrascrittura, protocollo editoriale con 80 casi sintetici
  e CI Linux, macOS e Windows.
