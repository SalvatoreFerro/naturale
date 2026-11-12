# Installare Naturale

Per i **testi** basta copiare l'intera cartella `naturale`, lasciando intatti i
file interni, in una delle directory del proprio ambiente:

- Claude Code: `~/.claude/skills/naturale` (invocazione `/naturale`).
- Codex: `~/.agents/skills/naturale` (selezione o richiesta esplicita della skill).

Su Windows `~` indica la propria directory utente. Non sovrascrivere una skill
esistente: spostarla prima in una copia di sicurezza. Non serve un plugin o un
server. La distribuzione è un'anteprima 0.1.0, con licenza MIT.

## Modulo immagini facoltativo

Servono Python 3.11+, Pillow e [ExifTool](https://exiftool.org/install.html),
installato separatamente e disponibile nel PATH. In un proprio ambiente Python:

```sh
python -m pip install -r /percorso/naturale/requirements.txt
exiftool -ver
python /percorso/naturale/scripts/images.py --help
```

Sostituire `/percorso/naturale` con il percorso reale; usare un interprete che
possa importare Pillow. La validazione C2PA è un'aggiunta facoltativa:

```sh
python -m pip install 'c2pa-python>=0.38.1,<0.39'
```

L'installazione scarica le dipendenze; gli script non installano nulla durante
l'uso e non inviano immagini a servizi esterni. Fornire percorsi locali, senza
allegare i file al modello. Claude e Codex possono comunque essere servizi cloud.
Se si fa leggere il rapporto a un assistente cloud, i dati del rapporto entrano
nel suo contesto: per mantenere anche i metadati fuori dal modello, usare solo
la CLI senza condividere il rapporto.

JPEG/PNG statici soltanto: la pulizia rimuove XMP e contenitori JUMBF/C2PA da una
copia, conserva EXIF e ICC e verifica i pixel. Non rimuove watermark invisibili
e non garantisce il risultato delle etichette Instagram. Consulta
[la guida immagini](references/images.md) prima dell'uso.

Il repository completo include benchmark, test e fonti. Questa cartella contiene
il pacchetto operativo; le dipendenze non sono incorporate nell'archivio.
