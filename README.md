# Naturale

Una skill open source in italiano per Claude Code e Codex: revisione di e-mail, messaggi e riassunti, con un modulo locale per ispezionare e rimuovere metadati XMP e contenitori JUMBF dalle immagini.

**Stato: anteprima 0.1.0.** L'efficacia editoriale non è ancora stata misurata con una valutazione umana: lo stato del benchmark è `not_validated`.

Il modulo testi guida la revisione di chiarezza, ritmo e tono, richiedendo di conservare il significato. Il modulo immagini lavora su una copia e controlla che pixel decodificati, EXIF e profilo ICC restino invariati. **Non rimuove watermark incorporati nei pixel, non rileva SynthID e non garantisce l'assenza dell'etichetta AI su Instagram.**

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

Per aggiornare, scarica e controlla la nuova versione; conserva una copia della
skill installata prima di sostituirla manualmente. Non ci sono aggiornamenti
automatici. Puoi rimuovere la cartella clonata dopo l'installazione, ma conserva
l'eventuale ambiente Python se lo usi per il modulo immagini. Per disinstallare,
rimuovi soltanto la cartella `naturale` dalla directory skill del tuo agente,
controllando prima che non contenga personalizzazioni da salvare.

## Requisiti

- Claude Code oppure Codex per usare la skill; il modulo immagini può essere eseguito anche dalla riga di comando.
- Python 3.11 o successivo per l'installer; per gli script immagini serve anche Pillow `>=11,<13`.
- Solo per le immagini: [ExifTool](https://exiftool.org/) installato separatamente e disponibile come `exiftool` nel `PATH`.
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
# Debian / Ubuntu
sudo apt-get update
sudo apt-get install libimage-exiftool-perl

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

I gestori di pacchetti possono fornire versioni meno recenti. La CI Linux usa ExifTool 13.63; se la tua versione non gestisce i contenitori JUMBF del file, installa una distribuzione recente dalle fonti ufficiali.

Per abilitare la verifica C2PA:

```sh
python -m pip install '.[c2pa]'
```

L'installazione iniziale delle dipendenze richiede normalmente una connessione; l'elaborazione dei file è locale. La verifica C2PA locale non equivale a un controllo online aggiornato della fiducia o della revoca dei certificati.

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

Il comando `clean` produce il file richiesto e un report JSON accanto alla copia, nell'esempio `immagine-copia.png.report.json`. Rifiuta l'operazione se la destinazione o il report esistono già. L'originale resta invariato e l'elaborazione verifica la conservazione dei pixel decodificati, dei dati EXIF e del profilo ICC.

La rimozione riguarda **solo XMP e JUMBF**, che possono contenere anche informazioni diverse dalla provenienza AI. Non è una cancellazione selettiva della sola dicitura “generato con AI”, né una pulizia completa dei metadati: EXIF, incluso l'eventuale GPS, viene conservato. Rimuovere un contenitore di credenziali interrompe la disponibilità di quelle informazioni di provenienza nella copia.

Le credenziali C2PA, i watermark invisibili incorporati nel contenuto e i classificatori di immagini sono tecnologie diverse. Un segnale assente o rimosso non dimostra che l'immagine sia di origine umana. I report non certificano immagini “AI-free” e non prevedono l'esito dei sistemi di etichettatura di piattaforme esterne.

## Sviluppo e verifiche

```sh
python -m pip install -e '.[dev]'
python -m pytest
python scripts/evaluate.py --validate-cases evals/cases.jsonl
```

La CI è configurata per eseguire i test con ExifTool su Linux, macOS e Windows, con Python 3.11 e 3.12; la configurazione non attesta che siano già passati su tutti questi ambienti. Linux usa il sorgente ufficiale di ExifTool 13.63; macOS e Windows usano rispettivamente Homebrew e Chocolatey. Una configurazione Linux installa anche l'integrazione C2PA facoltativa.

Il [benchmark editoriale](evals/README.md) include 80 casi sintetici e un protocollo di confronto cieco. Il comando sopra controlla la struttura del dataset; senza voti umani restituisce `not_validated`. Non genera riscritture e non misura da solo la loro qualità. Consulta le [conclusioni della ricerca](docs/RESEARCH.md) per le fonti e i limiti della prima versione.

Le [verifiche eseguite](docs/VALIDATION.md) riportano ambiente, 52 test passati, rilevamento reale in Codex e controlli ancora da completare.

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
