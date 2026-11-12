# Naturale

Una skill open source in italiano per Claude Code e Codex: revisione di e-mail, messaggi e riassunti, con un modulo locale per ispezionare e rimuovere metadati XMP e contenitori JUMBF dalle immagini.

**Stato: anteprima 0.2.1, preparata senza tag o release.** L'efficacia editoriale non è ancora stata misurata con una valutazione umana: lo stato del benchmark è `not_validated`. Le ricerche utilizzate e i relativi limiti sono descritti in [Ricerca](docs/RESEARCH.md).

Il modulo testi guida la revisione di chiarezza, ritmo e tono, richiedendo di conservare il significato. Il modulo immagini lavora su una copia e controlla pixel, orientamento, colore e le modifiche ai metadati ammesse dal profilo scelto. **Non rimuove watermark incorporati nei pixel, non rileva SynthID e non garantisce l'assenza dell'etichetta AI su Instagram.**

| Funzione | Cosa fa |
| --- | --- |
| Voce personale | Usa un profilo stilistico locale, salvato soltanto quando lo chiedi. |
| Intensità | Revisione minima, maggiore fluidità o ristrutturazione del testo. |
| Controllo e differenze | Segnala cambiamenti di numeri, citazioni, link e vincoli; mostra le modifiche su richiesta. |
| Immagini | Elabora singoli file o cartelle, con rapporti sintetici e un profilo distinto per metadati personali. |
| Installazione | Controlla i requisiti e aggiorna da una versione locale scelta, con backup e ripristino. |
| Valutazione | Prepara confronti ciechi per revisori umani e ammette nuovi dataset autorizzati. |

## Installa chiedendolo al tuo agente

Copia questo messaggio in **Claude Code o Codex con accesso al tuo computer**:

```text
Installa in locale la skill Naturale dalla repository
https://github.com/SalvatoreFerro/naturale
Leggi il README e controlla lo script d'installazione, poi installa la skill
per l'agente che sto usando, senza sovrascrivere installazioni esistenti.
Installa l'intera skill; le dipendenze facoltative delle immagini configurale
solo se te lo chiedo. Al termine mostrami il percorso installato e come usarla.
```

La chat web da sola potrebbe non avere accesso ai file locali. Serve un agente
che possa scaricare la repository ed eseguire comandi sul computer. L'installer
copia la skill: **non richiede account GitHub, token, chiavi API aggiuntive,
privilegi amministrativi o servizi di Naturale**. Claude/Codex mantengono i
propri requisiti e costi.

## Installazione locale rapida

Con Git e Python 3.11+ disponibili, in una directory scelta da te:

```sh
git clone https://github.com/SalvatoreFerro/naturale.git
cd naturale
```

Leggi `scripts/install.py`, poi scegli il tuo agente:

```sh
# Anteprima: non scrive file
python3 scripts/install.py --host codex --dry-run

# Installa per Codex
python3 scripts/install.py --host codex

# Oppure per Claude Code
python3 scripts/install.py --host claude

# Oppure per entrambi
python3 scripts/install.py --host both
```

Su Windows usa `py -3` al posto di `python3`. Se Git non è disponibile, puoi
[scaricare lo ZIP](https://github.com/SalvatoreFerro/naturale/archive/refs/heads/main.zip),
estrarlo e aprire un terminale nella cartella estratta prima di eseguire lo script.

L'installer non accede alla rete, non installa pacchetti e non modifica la
configurazione degli agenti. Se una copia identica è già presente non la cambia;
se trova una versione diversa o un collegamento simbolico si ferma. Per i testi
non occorre altro. Per le immagini segui la sezione successiva, usando un
ambiente Python dedicato. Il download iniziale e l'installazione delle
dipendenze richiedono normalmente Internet; l'elaborazione immagini resta locale.

Non ci sono aggiornamenti automatici: [diagnosi, aggiornamento e ripristino](#diagnosi-aggiornamento-e-ripristino)
sono operazioni esplicite. Conserva la copia locale della repository per usare
questi strumenti. Per disinstallare, rimuovi soltanto la cartella `naturale`
dalla directory skill del tuo agente, controllando prima che non contenga
personalizzazioni da salvare. I profili personali sono separati e non vengono
rimossi dalla disinstallazione della skill.

## Requisiti

- Claude Code oppure Codex per usare la skill; il modulo immagini può essere eseguito anche dalla riga di comando.
- Python 3.11 o successivo per l'installer; per gli script immagini serve anche Pillow `>=11,<13`.
- Solo per le immagini: [ExifTool](https://exiftool.org/) **13.60 o successivo**, installato separatamente e disponibile come `exiftool` nel `PATH`.
- Facoltativo: `c2pa-python` per richiedere la verifica delle credenziali C2PA.

Il modulo immagini supporta JPEG e PNG statici, con limiti di **100 MiB per file** e **40 milioni di pixel**. Non supporta APNG, JPEG con contenitori MPF, immagini animate o altri formati.

Gli script di elaborazione non effettuano chiamate di rete e non installano dipendenze automaticamente. Il modello Claude/Codex può essere un servizio cloud e mantiene i propri costi e condizioni: la licenza open source della skill non comprende un abbonamento o crediti del modello. Per mantenere locale il trattamento delle immagini, usa il percorso del file senza allegarlo al modello o aprirlo con strumenti che lo caricano su servizi remoti.

## Installazione degli strumenti

Questa sezione serve soltanto per **abilitare le immagini**. Per rivedere i
testi basta aver copiato la skill con l'installer o manualmente.

Da un checkout di questo repository, su Linux o macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Su Windows, in PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install .
```

Se l'attivazione dell'ambiente non è disponibile, usa direttamente `.venv/bin/python` su Linux/macOS oppure `.venv\Scripts\python.exe` su Windows.

Installa ExifTool con uno dei seguenti metodi:

```sh
# macOS con Homebrew
brew install exiftool
```

```powershell
# Windows con Chocolatey già installato; può richiedere PowerShell amministratore
choco install exiftool -y
```

In alternativa, segui le [istruzioni ufficiali di ExifTool](https://exiftool.org/install.html). Su Windows conserva anche la directory di supporto `exiftool_files` della distribuzione eseguibile. Verifica l'installazione:

```sh
exiftool -ver
```

**Ubuntu 24.04:** il pacchetto apt `libimage-exiftool-perl` fornisce la 12.76,
che non è supportata per il modulo immagini. La 13.59 riproduce lo stesso errore
nei PNG firmati; la 13.60 è la prima versione adiacente verificata che include
la correzione ufficiale e supera la suite. `doctor.py` restituisce
`exiftool_too_old` e `images_ready: false` sotto questa soglia; anche i comandi
immagini si fermano prima di elaborare o pubblicare file.

Per usare il sorgente ufficiale 13.63, fissato allo stesso commit della CI,
su Linux con Git e Perl disponibili:

```sh
mkdir -p "$HOME/.local/share" "$HOME/.local/bin"
git clone --no-checkout https://github.com/exiftool/exiftool.git "$HOME/.local/share/naturale-exiftool-13.63"
git -C "$HOME/.local/share/naturale-exiftool-13.63" checkout --detach 1da714924f67763b6a8a7013dd2aa1983a16f87b
ln -s "$HOME/.local/share/naturale-exiftool-13.63/exiftool" "$HOME/.local/bin/exiftool"
export PATH="$HOME/.local/bin:$PATH"
exiftool -ver
```

La procedura non usa `sudo` e non sovrascrive directory o link già esistenti.
Per le sessioni future aggiungi la directory al PATH secondo il tuo ambiente.
Il requisito minimo è definito una sola volta in
`skills/naturale/scripts/exiftool_runtime.py`, condiviso da immagini e diagnosi.

Per abilitare la verifica C2PA:

```sh
python -m pip install '.[c2pa]'
```

L'installazione iniziale delle dipendenze richiede normalmente una connessione; l'elaborazione dei file è locale. La verifica C2PA locale non equivale a un controllo online aggiornato della fiducia o della revoca dei certificati.

## Installazione come plugin Claude Code (opzionale)

Scegli l'installazione manuale oppure il plugin, evitando di caricare due copie
della stessa skill in Claude Code. L'installazione per Codex rimane quella
descritta sopra: il plugin è un'alternativa riservata a Claude Code.

In una sessione di **Claude Code 2.1.275 o successivo**:

```text
/plugin install naturale --marketplace SalvatoreFerro/naturale
```

Segui il pannello per aggiungere il marketplace e scegliere l'ambito di
installazione. In alternativa, dalla shell usa i due comandi:

```sh
claude plugin marketplace add SalvatoreFerro/naturale
claude plugin install naturale@naturale-marketplace
```

Il marketplace si chiama `naturale-marketplace`; la skill del plugin si richiama
come **`/naturale:naturale`**. I comandi di installazione scaricano il pacchetto
e registrano il plugin nella configurazione di Claude Code. Il pacchetto non
aggiunge hook, servizi MCP o dipendenze eseguite automaticamente; gli script
locali conservano il comportamento senza rete descritto in questo README.

Per controllare i manifest da una copia locale della repository:

```sh
claude plugin validate .
claude plugin list
```

`scripts/doctor.py` controlla le cartelle di installazione manuale, non la cache
dei plugin Claude. Per verificare un'installazione plugin usa `claude plugin list`;
Pillow, ExifTool e l'eventuale SDK C2PA devono comunque essere presenti per le
rispettive funzioni immagini.

## Installazione della skill

Il pacchetto da copiare è **l'intera directory** `skills/naturale`, non soltanto `SKILL.md`. Non sovrascrivere una skill già installata con lo stesso nome: prima confrontala o spostala in una copia di sicurezza.

Su Linux/macOS, scegli il comando per il tuo ambiente:

```sh
# Claude Code
mkdir -p "$HOME/.claude/skills"
test ! -e "$HOME/.claude/skills/naturale" && cp -R skills/naturale "$HOME/.claude/skills/naturale"

# Codex
mkdir -p "$HOME/.agents/skills"
test ! -e "$HOME/.agents/skills/naturale" && cp -R skills/naturale "$HOME/.agents/skills/naturale"
```

Su Windows, in PowerShell:

```powershell
# Claude Code
New-Item -ItemType Directory -Force "$HOME/.claude/skills" | Out-Null
if (Test-Path "$HOME/.claude/skills/naturale") { throw "La skill Naturale esiste già." }
Copy-Item -Recurse skills/naturale "$HOME/.claude/skills/naturale"

# Codex
New-Item -ItemType Directory -Force "$HOME/.agents/skills" | Out-Null
if (Test-Path "$HOME/.agents/skills/naturale") { throw "La skill Naturale esiste già." }
Copy-Item -Recurse skills/naturale "$HOME/.agents/skills/naturale"
```

Per un'installazione limitata a un progetto, usa `.claude/skills/naturale` o `.agents/skills/naturale` nella directory del progetto. Non è necessario un server MCP o un manifest di plugin. Gli script richiedono comunque le dipendenze installate sopra e un interprete Python che possa importarle.

## Uso sui testi

In Claude Code puoi richiamare `/naturale`; in Codex seleziona la skill o richiamala esplicitamente nel prompt. Esempi:

```text
Usa Naturale per rendere questa e-mail più diretta e cordiale.
Mantieni le condizioni e non trasformare le possibilità in promesse:
[testo]
```

```text
Usa Naturale per riassumere questo testo in 150 parole per un pubblico non tecnico.
Conserva le decisioni, le scadenze e le incertezze:
[testo]
```

Puoi fornire destinatario, tono, lunghezza o esempi del tuo stile. La qualità va valutata su chiarezza e fedeltà al contenuto, senza trattare il punteggio di un rilevatore AI come prova di qualità o di paternità umana.

### Intensità e voce personale

```text
Usa Naturale con intervento minimo: correggi solo ciò che serve e mantieni il mio tono.
```

```text
Usa Naturale in modalità strutturale: riordina questa e-mail per renderla chiara,
senza cambiare condizioni, impegni o grado di certezza. Mostrami anche le modifiche.
```

La modalità predefinita è **fluidità**, con intervento conservativo. Una modalità
più intensa non autorizza l'aggiunta di fatti o promesse. Il riassunto rimane
un'operazione distinta e deve essere richiesto esplicitamente.

Puoi chiedere all'agente di ricavare un profilo da alcuni tuoi esempi, mostrandoti
le caratteristiche individuate. Il profilo viene salvato solo se lo chiedi;
contiene indicazioni stilistiche e non una copia dei testi originali. Per esempio:

```text
Da questi esempi ricava il mio stile per le e-mail di lavoro e mostrami il profilo.
```

```text
Salva questo profilo come "lavoro". Poi usalo per riscrivere la prossima e-mail.
```

Per gestirlo direttamente, prepara un JSON approvato da te:

```json
{"register":"professionale, cordiale e diretto","conciseness":"breve","preferred_phrases":[],"avoided_phrases":["con la presente"],"punctuation":["punteggiatura sobria"],"notes":["conserva il tu o il Lei della fonte"]}
```

```sh
python skills/naturale/scripts/text.py profiles create lavoro --from-json profilo-approvato.json
python skills/naturale/scripts/text.py profiles show lavoro
python skills/naturale/scripts/text.py profiles list
python skills/naturale/scripts/text.py profiles delete lavoro
```

I profili risiedono normalmente in `~/.naturale/profiles`, fuori dalla
repository e dalle installazioni degli agenti. Puoi modificare il JSON locale;
il caricamento ne controlla il formato. Nessun profilo viene raccolto o
sincronizzato automaticamente. Se lo fai leggere a un assistente cloud, il suo
contenuto entra nel contesto di quell'assistente.

### Controllo locale e confronto

Su due file già presenti:

```sh
python skills/naturale/scripts/text.py audit --source originale.txt --revision rivisto.txt --diff
```

L'audit controlla elementi riconoscibili come numeri, citazioni e URL. I segnali
su negazioni e incertezza sono euristici, da rivedere: il rapporto mantiene
`semantic_equivalence: not_verified`. Un controllo superato non dimostra che il
significato sia identico. Per richieste delicate l'agente confronta anche fatti,
responsabilità, condizioni e impegni con la fonte.

Puoi indicare vincoli esatti in un JSON, per esempio
`{"preserve_exact":["non è un ordine"],"forbid":["ordine confermato"]}`, e passarlo
con `--constraints vincoli.json`. Per un riassunto aggiungi `--operation summarize`:
le omissioni sono ammesse, mentre i vincoli espliciti rimangono controllati.
Consulta [i dettagli degli strumenti testo](skills/naturale/references/text-tools.md).

## Uso sulle immagini

Esegui i comandi dalla radice del repository, con l'ambiente Python attivo. Per una skill già copiata puoi sostituire il percorso dello script con quello della sua directory di installazione.

Ispezione del file, senza modifiche:

```sh
python skills/naturale/scripts/images.py inspect immagine.png
```

Ispezione con verifica C2PA facoltativa:

```sh
python skills/naturale/scripts/images.py inspect immagine.png --validate-c2pa
```

Rimozione di XMP e JUMBF da una copia:

```sh
python skills/naturale/scripts/images.py clean immagine.png --output immagine-copia.png
```

Con verifica C2PA:

```sh
python skills/naturale/scripts/images.py clean immagine.png --output immagine-copia.png --validate-c2pa
```

Il comando `clean` produce il file richiesto e un report JSON accanto alla copia, nell'esempio `immagine-copia.png.report.json`. Rifiuta l'operazione se la destinazione o il report esistono già. L'originale resta invariato; nel profilo predefinito `provenance` l'elaborazione verifica la conservazione dei pixel decodificati, dei dati EXIF e del profilo ICC.

La CLI restituisce normalmente un **riepilogo sintetico**, senza i valori
grezzi dei metadati e senza i percorsi completi. Il rapporto locale completo
può contenere dati personali: non condividerlo automaticamente con il modello.
Per richiederlo esplicitamente su stdout usa `--full-report`; per salvarlo durante
un'ispezione usa `inspect immagine.png --report rapporto-locale.json`.

La rimozione riguarda **solo XMP e JUMBF**, che possono contenere anche informazioni diverse dalla provenienza AI. Non è una cancellazione selettiva della sola dicitura “generato con AI”, né una pulizia completa dei metadati: EXIF, incluso l'eventuale GPS, viene conservato. Rimuovere un contenitore di credenziali interrompe la disponibilità di quelle informazioni di provenienza nella copia.

Le credenziali C2PA, i watermark invisibili incorporati nel contenuto e i classificatori di immagini sono tecnologie diverse. Un segnale assente o rimosso non dimostra che l'immagine sia di origine umana. I report non certificano immagini “AI-free” e non prevedono l'esito dei sistemi di etichettatura di piattaforme esterne.

### Metadati personali e cartelle

Il profilo predefinito `provenance` mantiene la pulizia XMP/JUMBF descritta
sopra. Il nuovo profilo `privacy` rimuove invece i tag di posizione e gli
identificativi indicati nella [guida immagini](skills/naturale/references/images.md),
conservando orientamento, colore, pixel e il contenitore C2PA. Non è
anonimizzazione completa: altri campi e le stesse credenziali conservate
potrebbero contenere informazioni personali. Le credenziali possono diventare
non valide dopo una modifica del file.

```sh
python skills/naturale/scripts/images.py clean immagine.jpg --output immagine-privacy.jpg --profile privacy
python skills/naturale/scripts/images.py batch foto --output-dir foto-elaborate --dry-run
python skills/naturale/scripts/images.py batch foto --output-dir foto-elaborate --profile privacy
```

Il batch considera soltanto i file JPEG/PNG al primo livello della cartella,
senza seguire collegamenti simbolici. Un file non elaborabile viene segnalato
senza interrompere gli altri; nessuna copia o rapporto esistente viene sovrascritto.

## Diagnosi, aggiornamento e ripristino

```sh
python scripts/doctor.py --host codex
```

La diagnosi controlla l'installazione e i requisiti presenti. Non installa
pacchetti, non legge credenziali e non effettua chiamate di rete. Il modulo
testi può essere disponibile anche quando mancano strumenti facoltativi delle
immagini. Usa `--host claude` o `--host both` per gli altri casi.

Gli aggiornamenti lavorano sul checkout locale che hai scelto e controllato:

```sh
# Seleziona prima un commit verificato nel tuo checkout locale.
# La preparazione 0.2.1 non crea un tag v0.2.1.
python scripts/install.py --host codex --update --dry-run
python scripts/install.py --host codex --update
```

L'installer confronta gli hash della ricevuta con i file installati. Se trova
personalizzazioni, contenuti sconosciuti o un ambiente virtuale interno alla
skill, si ferma senza cancellarli. Se i controlli passano, salva un backup e
mostra dove trovarlo. Per ripristinarlo usa il percorso restituito:

```sh
python scripts/install.py --host codex --rollback /percorso/del/backup
```

I profili in `~/.naturale/profiles` non vengono toccati. Non viene effettuata
una fusione automatica delle personalizzazioni. Se i file cambiano durante un
aggiornamento o un ripristino interrotto, l'installer conserva le copie coinvolte
e indica dove recuperarle manualmente, evitando di cancellare le nuove modifiche.

**Migrazione dalla 0.1:** le vecchie installazioni non hanno una ricevuta di
gestione. Copia o sposta la cartella installata in un backup scelto da te,
fuori dalla directory delle skill dell'agente,
controllando eventuali modifiche personali, poi esegui l'installazione della
0.2 nella destinazione liberata. L'aggiornamento automatico rifiuta una vecchia
copia senza ricevuta, così da non attribuirsi la gestione di file sconosciuti.

## Sviluppo e verifiche

```sh
python -m pip install -e '.[dev]'
python -m pytest
python scripts/evaluate.py --validate-cases evals/cases.jsonl
```

La CI è configurata per eseguire i test con ExifTool su Linux, macOS e Windows, con Python 3.11 e 3.12, più Linux con Python 3.13; la configurazione non attesta che siano già passati su tutti questi ambienti. Linux usa il sorgente ufficiale di ExifTool 13.63; macOS e Windows usano rispettivamente Homebrew e Chocolatey. Una configurazione Linux installa anche l'integrazione C2PA facoltativa.

Il [benchmark editoriale](evals/README.md) include 80 casi sintetici e un protocollo di confronto cieco, ora estensibile a nuovi dataset autorizzati. È disponibile un modello sintetico di formato e uno strumento per preparare pacchetti A/B per revisori, con associazioni private separate. Senza voti umani lo stato resta `not_validated`. Nessuno strumento genera automaticamente risultati di efficacia. Consulta le [conclusioni della ricerca](docs/RESEARCH.md) per fonti, scelte adottate e limiti.

Le [verifiche eseguite](docs/VALIDATION.md) riportano ambiente, 146 test locali passati, rilevamento reale in Codex e controlli ancora da completare.

Per contribuire, apri un issue o una pull request con il comportamento atteso, un esempio minimo e la verifica eseguita. Usa soltanto testi e immagini che puoi condividere; rimuovi dati personali dalle fixture pubbliche. Per le modifiche editoriali includi esempi prima/dopo e controlla che non cambino fatti, negazioni, responsabilità o gradi di certezza.

Per problemi di sicurezza consulta [SECURITY.md](SECURITY.md): non pubblicare
credenziali, immagini personali o dettagli di vulnerabilità nelle issue pubbliche.

## Fonti e licenze

- [Specifica Agent Skills](https://agentskills.io/specification)
- [Skill in Claude Code](https://code.claude.com/docs/en/skills)
- [Skill in Codex](https://developers.openai.com/codex/skills)
- [ExifTool e installazione](https://exiftool.org/install.html)
- [Segnali di provenienza nei contenuti OpenAI](https://help.openai.com/en/articles/8912793-c2pa-in-chatgpt-images)
- [Approccio Meta all'etichettatura AI](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/)

Codice e istruzioni originali: [licenza MIT](LICENSE). Le dipendenze mantengono le proprie licenze; consulta [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
