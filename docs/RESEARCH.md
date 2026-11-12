# Ricerca e limiti della versione 0.1.0

Queste conclusioni guidano l'anteprima di Naturale. Distinguono funzionalità implementabili, evidenze documentali e risultati ancora da misurare. Le documentazioni esterne possono cambiare.

## Portabilità delle skill

La [specifica Agent Skills](https://agentskills.io/specification) definisce una directory con `SKILL.md`, frontmatter YAML e risorse opzionali. [Claude Code](https://code.claude.com/docs/en/skills) e [Codex](https://developers.openai.com/codex/skills) supportano questo formato, con percorsi di installazione diversi. La distribuzione di una skill locale non richiede necessariamente un server MCP o un manifest di plugin. Per il nucleo condiviso usiamo istruzioni e percorsi relativi, evitando funzionalità esclusive di un host.

## Qualità dei testi

La naturalezza va valutata insieme alla fedeltà semantica e all'utilità per il destinatario. Variare automaticamente sintassi, sinonimi o punteggiatura non dimostra un miglioramento. Nemmeno un controllo di numeri, nomi e date basta a escludere cambiamenti di negazioni, condizioni, promesse, responsabilità o grado di certezza.

Lo [studio di Liang e colleghi sui rilevatori GPT](https://arxiv.org/abs/2304.02819) documenta problemi di affidabilità ed equità in uno specifico contesto di testi inglesi. Non permette di dedurre prestazioni per tutti i rilevatori attuali, per l'italiano o per questa skill. I punteggi di rilevamento non sono l'obiettivo del benchmark di Naturale.

Il [protocollo editoriale](../evals/README.md) confronta skill e richiesta senza skill sullo stesso modello, con revisori e risultati anonimi. Gli 80 casi iniziali sono sintetici, originali e pubblici: aiutano a trovare errori ma non rappresentano una popolazione di utenti. **Non è ancora stata eseguita una valutazione umana; lo stato è `not_validated`.** Non sono dichiarate percentuali di miglioramento.

## Immagini e provenienza

La [documentazione OpenAI sui segnali di provenienza](https://help.openai.com/en/articles/8912793-c2pa-in-chatgpt-images) distingue Content Credentials e watermark invisibili SynthID, con copertura dipendente da prodotto, modello ed esportazione. [Meta descrive](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/) etichette basate su segnali condivisi dall'industria o autodichiarazioni. Queste fonti non identificano la causa dell'etichettatura di un file specifico né garantiscono come verrà trattato dopo una modifica.

[ExifTool documenta](https://exiftool.org/TagNames/Jpeg2000.html) la rimozione del gruppo JUMBF per formati scrivibili, inclusi JPEG e PNG. Naturale usa ExifTool per rimuovere XMP e JUMBF da una copia, verificando separatamente la conservazione di pixel decodificati, EXIF e ICC. La copia perde anche eventuali informazioni non AI presenti nei contenitori eliminati. EXIF, incluso l'eventuale GPS, resta presente: non si tratta di anonimizzazione completa.

La verifica facoltativa usa [c2pa-python](https://github.com/contentauth/c2pa-python) con recupero dei manifest remoti e richieste OCSP disabilitati. Un controllo locale delle firme non stabilisce da solo l'affidabilità del firmatario. “Non trovato”, “non controllato”, “non leggibile” e “firma non valida” non significano “immagine umana”.

La versione 0.1.0 non rileva o rimuove SynthID, non modifica intenzionalmente i pixel, non usa classificatori di origine e non promette l'assenza di etichette su Instagram. Non sono stati misurati risultati su pubblicazioni Instagram. Gli script non inviano i file a servizi esterni; l'uso del modello Claude/Codex segue invece l'ambiente scelto dall'utente.

## Affermazioni da non trasferire dalle bozze alla documentazione

- File sciolti in `.claude/skills/*.md` e plugin obbligatori per Codex confondono formati e modalità di distribuzione diverse.
- Perplessità, variabilità delle frasi e punteggi dei detector non certificano qualità editoriale o paternità umana.
- Una riscrittura non costa soltanto i token delle istruzioni: contano anche fonte, risultato e contesto del modello.
- Riferimenti commerciali o accademici privi di collegamenti verificabili non costituiscono evidenza utilizzabile.
- Non esiste qui una valutazione legale generale della rimozione di credenziali: tecnologia, diritti sul contenuto, condizioni dei servizi e contesto d'uso richiedono distinzioni. La documentazione non afferma che ogni rimozione sia sempre lecita o sempre illecita.
