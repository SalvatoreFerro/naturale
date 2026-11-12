# Immagini: ispezione e pulizia locale

## Ambito e privacy

Questo modulo accetta soltanto JPEG e PNG statici, massimo 100 MiB e 40 milioni
di pixel. Estensione e formato reale devono corrispondere. APNG e immagini
multiple non sono supportati. Non caricare l'immagine nel modello, non invocare
strumenti di visione, browser, detector online o servizi esterni per questo flusso.
Leggere il rapporto JSON dello script è sufficiente. Non installare dipendenze
automaticamente: se mancano, indicare quelle mancanti.

La skill non esegue localmente Claude o Codex: il vincolo locale riguarda
l'elaborazione dei file immagini. Il rapporto può contenere metadati personali;
rimane sul computer e non va pubblicato automaticamente.

## Comandi

Risolvere `scripts/images.py` rispetto alla directory di questa skill, non alla
directory corrente dell'utente. Usare sempre argomenti separati e percorsi
correttamente quotati, senza interpolare nomi di file in comandi shell.

```text
python <percorso-assoluto>/scripts/images.py inspect <input>
python <percorso-assoluto>/scripts/images.py clean <input> --output <nuovo-output>
python <percorso-assoluto>/scripts/images.py inspect <input> --validate-c2pa
```

`inspect` non scrive file. `clean` richiede una destinazione nuova, crea anche
`<nuovo-output>.report.json` e non sovrascrive mai l'originale, un output esistente
o un rapporto esistente. Mantenere il formato: JPEG resta JPEG, PNG resta PNG.
Quando l'utente non indica il nome, proporre/usare `<nome>-clean.<estensione>`;
in presenza di collisioni scegliere `-clean-2`, `-clean-3`, eccetera, senza
cancellare file. Eseguire `clean` solo quando l'utente chiede un'elaborazione,
non su una semplice domanda di provenienza.

Python 3.11+, Pillow ed ExifTool devono essere disponibili nell'ambiente che
esegue lo script. La validazione C2PA è facoltativa e richiede `c2pa-python`
nella versione supportata dal progetto. Non abilitarla se l'utente richiede
soltanto una pulizia o un'ispezione ordinaria.

## Cosa viene modificato

ExifTool opera su una copia, rimuovendo i gruppi **XMP** e **JUMBF/C2PA
incorporati**, senza ricodificare l'immagine. Lo script re-ispeziona l'output e
confronta formato, dimensioni, pixel decodificati, EXIF, trasparenza e profilo
ICC. Se i controlli non passano, non pubblica l'output.

EXIF (inclusi eventuali GPS, Software e orientamento), IPTC, commenti e altri
dati non appartenenti ai gruppi target possono restare e possono ancora
contenere informazioni sull'origine AI. Non presentare questa operazione come
anonimizzazione, eliminazione universale dei metadati o rimozione di ogni segnale.

Lo script non ritaglia, non aggiunge rumore, non comprime e non ricostruisce i
pixel per cercare di eludere watermark invisibili. Non cancella loghi o scritte
visibili: il ritocco grafico non è implementato in questa versione.

## Interpretazione del rapporto

- `metadata.before` / `after`: informazioni lette da ExifTool prima e dopo.
- `removed_groups`: solo i gruppi target presenti prima e assenti dopo.
- `pixel_data_unchanged: true`: pixel e proprietà controllate invariati.
- `c2pa.*.embedded`: `present`, `not_found`, `unreadable` o `not_checked`.
- `c2pa.*.validation`: `valid`, `invalid`, `not_checked` o `unavailable`.
  La validazione locale non certifica il trust del firmatario. Senza SDK non
  viene simulata una verifica crittografica. Manifest remoti e OCSP non vengono
  recuperati; un risultato incompleto resta tale.
- `invisible_watermark: not_checked`: nessuna verifica SynthID o equivalente.
- `instagram_label: unknown`: nessuna previsione affidabile del comportamento Meta.

Un contenitore JUMBF non è necessariamente un manifest C2PA valido. C2PA può
essere usato anche da fotocamere e redazioni: la sua presenza da sola non prova
che l'immagine sia generata da AI. Un segnale non trovato non prova un'origine
umana. Non generare percentuali AI, punteggi “AI-free” o conclusioni analoghe.

Codice di uscita CLI: `0` per operazione verificata; `1` per errore operativo,
con oggetto JSON su stderr; `2` per argomenti CLI non validi.

## Caso ChatGPT → Instagram

L'operazione modifica soltanto i segnali dichiarati. Non dimostra rimozione di
SynthID e non garantisce l'assenza dell'etichetta AI. Un eventuale confronto su
Instagram è manuale e distinto da questo flusso: registrare file, data,
modalità di caricamento e testo dell'etichetta. Non pubblicare nulla né aprire
servizi di verifica senza una richiesta specifica dell'utente.

Fonti: [ExifTool/JUMBF](https://exiftool.org/TagNames/Jpeg2000.html),
[FAQ ExifTool](https://exiftool.org/faq.html),
[provenienza OpenAI](https://help.openai.com/en/articles/8912793-c2pa-in-chatgpt-images),
[informazioni Meta](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/).
