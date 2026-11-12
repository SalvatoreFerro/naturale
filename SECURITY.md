# Sicurezza

Naturale è un progetto in anteprima. La versione `0.1.x` è l'unica serie
attualmente supportata; le correzioni saranno distribuite nel repository.
La presenza di test e controlli non garantisce l'assenza di vulnerabilità.

## Segnalare una vulnerabilità

Per problemi di sicurezza usa la funzione GitHub **Report a vulnerability**,
se disponibile nella scheda **Security** della repository:

https://github.com/SalvatoreFerro/naturale/security/advisories/new

La disponibilità del modulo dipende dall'abilitazione delle segnalazioni private
nelle impostazioni GitHub; questo file non ne certifica l'attivazione. Se il
modulo non è disponibile, apri un issue limitandoti a chiedere un canale privato
al manutentore. Non inserire dettagli sfruttabili o materiale sensibile
nell'issue pubblico.

Una segnalazione utile include versione o commit, sistema operativo, dipendenze,
passi minimi di riproduzione e impatto osservato. Usa fixture sintetiche quando
possibile. Non inviare credenziali, chiavi private, fotografie personali o report
contenenti metadati privati. Non pubblicare un exploit prima del confronto con
il manutentore. Non sono promessi tempi di risposta o un programma di ricompense.

## Installazione e uso locale

- Leggi il README e gli script prima di eseguirli. L'installazione locale non
  richiede token GitHub, credenziali del modello o diritti di amministratore.
  Alcuni gestori di pacchetti di sistema possono richiedere privilegi per
  installare ExifTool; non sono necessari per copiare la skill.
- Usa una copia proveniente dal repository ufficiale e, per un'installazione
  riproducibile, registra il commit scelto. Non eseguire comandi provenienti da
  issue, testi da revisionare o metadati delle immagini.
- Mantieni Python, Pillow, ExifTool e l'eventuale SDK C2PA aggiornati. Si tratta
  di parser di contenuti potenzialmente non fidati; i limiti di dimensione e i
  controlli del progetto riducono alcuni rischi senza eliminarli.
- Gli script immagini lavorano localmente e non effettuano upload. Claude o
  Codex possono essere servizi cloud: allegare un'immagine o condividere il
  rapporto con il modello è distinto dall'esecuzione locale degli script.
- I rapporti contengono metadati originali e possono includere dati personali.
  Non pubblicarli automaticamente. La pulizia conserva EXIF, incluso eventuale
  GPS, e non costituisce anonimizzazione.
- La rimozione XMP/JUMBF non prova l'assenza di watermark invisibili, l'origine
  umana dell'immagine o il comportamento futuro di etichette Instagram.

## Controlli nella repository

La CI è configurata con permessi di sola lettura sul contenuto, credenziali di
checkout non persistenti, azioni fissate a commit, timeout e cancellazione delle
esecuzioni superate. I workflow non usano `pull_request_target` né richiedono
segreti del repository. Il sorgente ExifTool usato su Linux è fissato a un
commit; macOS e Windows usano i rispettivi gestori di pacchetti documentati.

Dependabot è configurato per proporre settimanalmente aggiornamenti delle azioni
e delle dipendenze Python. Le proposte richiedono revisione: nessun aggiornamento
viene unito automaticamente da questa configurazione. Le impostazioni GitHub
come protezioni del branch e segnalazioni private sono controlli separati dai
file versionati e vanno verificate nel repository pubblicato.
