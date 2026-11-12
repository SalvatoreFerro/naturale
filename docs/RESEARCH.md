# Ricerca e scelte della versione 0.2.0

Naturale usa ricerche esistenti per scegliere **cosa controllare e come misurarlo**.
Non ha riprodotto gli esperimenti dei paper né misurato una percentuale di
miglioramento sui propri utenti. I riferimenti seguenti sono stati verificati
nelle rispettive fonti primarie; i risultati pubblicati nei loro contesti non
sono risultati della skill italiana.

## Quattro basi scientifiche

| Fonte primaria | Risultato utile al progetto | Adozione in Naturale e limite |
| --- | --- | --- |
| Mir e colleghi (2019), [Evaluating Style Transfer for Text](https://arxiv.org/abs/1904.02295) | La valutazione distingue intensità del trasferimento di stile, preservazione del contenuto e naturalezza, con compromessi tra le dimensioni. | Modalità di intervento esplicite e revisione umana di voce, naturalezza e fedeltà. Il lavoro usa principalmente trasferimento di sentiment su dati Yelp: non valida automaticamente e-mail italiane o profili personali. |
| Pagnoni, Balachandran e Tsvetkov (2021), [Understanding Factuality in Abstractive Summarization with FRANK](https://arxiv.org/abs/2104.13346) | Una tipologia di errori fattuali aiuta a valutare incongruenze che un solo voto binario nasconde. | Checklist su soggetti, azioni, condizioni, negazioni, attribuzioni e incertezza; controlli locali su stringhe e valori come segnali aggiuntivi. Non implementiamo un classificatore FRANK e i controlli deterministici non provano equivalenza semantica. |
| Fabbri e colleghi (2021), [SummEval: Re-evaluating Summarization Evaluation](https://arxiv.org/abs/2007.12626) | Mette a confronto metriche automatiche e giudizi umani esperti/crowd e sostiene una valutazione più completa dei riassunti. | Confronto cieco con fonte visibile, più revisori, risultati e versioni registrati, fedeltà distinta dalla fluidità. Il suo corpus di notizie inglesi non viene redistribuito o trattato come benchmark italiano. |
| Madaan e colleghi (2023), [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) | Studia generazione, feedback e revisione iterativa senza ulteriore addestramento. | Separare la stesura dal controllo finale e correggere difetti concreti; il modello non deve inventare modifiche per giustificare un passaggio in più. Non replichiamo la pipeline sperimentale, non promettiamo il miglioramento percentuale del paper e l'autorevisione non è una garanzia di correttezza. |

I controlli testuali locali fanno emergere differenze verificabili e dubbi da
rileggere. Le regole su modalità e profili sono istruzioni per l'agente; la
revisione del significato dipende ancora dal modello e, nei casi importanti,
dall'utente. Nessun punteggio di “umanità” o rilevatore AI è usato come criterio
finale di qualità.

## Valutazione pronta per dati reali, senza inventarli

Il [protocollo editoriale](../evals/README.md) mantiene gli 80 casi sintetici
originali e separa il formato JSONL dalla composizione di quel pilot. Si possono
aggiungere casi realmente autorizzati e anonimizzati, dichiarandone la provenienza;
la dichiarazione non sostituisce il consenso conservato dal responsabile.
Il file `real-world-template.jsonl` è esso stesso sintetico, non un corpus umano.

Lo strumento locale prepara risultati A/B controbilanciati e una mappa privata,
senza generare testi o chiamare servizi. I revisori valutano gli output prima
di vedere quale usa la skill. Il report distingue media per caso e media per
voto, evitando che un singolo caso con molte valutazioni domini la decisione.
La soglia preliminare richiede almeno 40 casi heldout, due revisori per caso,
nessun errore critico e una preferenza media per caso superiore al 60%.

**Non è ancora stata eseguita una valutazione umana: lo stato è `not_validated`.**
Le soglie sono scelte del progetto e non derivano da una garanzia statistica dei
paper. Una prova sul pilot non dimostra prestazioni su ogni genere, modello,
profilo di voce o popolazione di utenti.

## Portabilità e trattamento dei dati

La [specifica Agent Skills](https://agentskills.io/specification),
[Claude Code](https://code.claude.com/docs/en/skills) e
[Codex](https://developers.openai.com/codex/skills) definiscono il formato a
cartella con `SKILL.md`. Il nucleo condiviso usa risorse relative e non richiede
un server MCP o un plugin aggiuntivo. I profili sono opzionali e locali: i testi
campione non vengono archiviati automaticamente. Il modello dell'utente può
essere cloud; leggere un testo o un profilo nel suo contesto è distinto
dall'esecuzione locale degli script.

## Immagini: provenienza, privacy e limiti

La [documentazione OpenAI](https://help.openai.com/en/articles/8912793-c2pa-in-chatgpt-images)
distingue Content Credentials e watermark invisibili SynthID; la copertura
varia secondo prodotto, modello ed esportazione.
[Meta](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/)
descrive etichette basate su segnali condivisi dall'industria o autodichiarazioni.
Queste fonti non identificano la causa dell'etichetta di uno specifico file né
permettono di garantire il trattamento futuro da parte di Instagram.

[ExifTool](https://exiftool.org/TagNames/Jpeg2000.html) documenta la rimozione di
JUMBF nei formati scrivibili, inclusi JPEG e PNG. Il profilo di pulizia della
provenienza rimuove XMP/JUMBF da copie senza ricodificare i pixel, con controlli
di conservazione. Il profilo privacy è una scelta distinta e mirata ai tag
documentati nella [guida immagini](../skills/naturale/references/images.md);
nessuno dei due è una promessa universale di anonimizzazione.

La validazione [c2pa-python](https://github.com/contentauth/c2pa-python) è
facoltativa: il recupero dei manifest remoti e le richieste OCSP sono disabilitati.
Un controllo locale delle firme non stabilisce da solo l'affidabilità del
firmatario. Modificare metadati può anche invalidare credenziali che restano
incorporate: il rapporto deve distinguere presenza, validazione e trust.
“Non trovato”, “non controllato” e “non valido” non significano “immagine umana”.

Non sono stati misurati risultati su Instagram. Naturale non rileva o rimuove
SynthID e non applica trasformazioni ai pixel per dichiarare un'immagine
“non rilevabile”. I rapporti sintetici riducono l'esposizione dei metadati al
modello; i rapporti completi restano locali salvo condivisione esplicita.
Non viene qui formulata una valutazione legale generale della rimozione di
credenziali: contano diritti, condizioni dei servizi e contesto d'uso.
