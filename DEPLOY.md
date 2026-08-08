# Mettere lo screener online

Obiettivo: una pagina HTML sempre raggiungibile, che si aggiorna da sola ogni
notte, senza server e senza costi.

L'architettura si presta bene perché la pipeline è già batch e produce un file
statico: **GitHub Actions** fa il calcolo (gratis), **GitHub Pages** serve il
risultato (gratis). Nessun database, nessun processo da tenere vivo.

```
cron ogni 3h (lun-ven) → Actions: scarica, calcola, verifica → site/ → Pages
                     ↑                        ↓
                  cache .cache/        se i dati non bastano
                  e output/            NON pubblica: resta online l'ultimo buono
```

---

## Il problema vero: Yahoo blocca i datacenter

Va detto prima di tutto il resto, perché è ciò che romperà l'automazione.

I runner di GitHub Actions escono da IP datacenter Azure. Yahoo Finance li
tratta da bot. I sintomi non sono errori puliti: sono **HTTP 429**, risposte
200 con corpo vuoto, `Ticker.info` che restituisce dizionari vuoti su tutto
l'universo. Dal tuo portatile gli stessi ticker funzionano — è l'IP, non il
codice, e nessun tutorial lo dice.

Cosa è già stato messo nel progetto per attenuarlo:

- `screener/net.py` installa una sessione **curl_cffi** che imita il
  fingerprint TLS di Chrome. È la mitigazione singola più efficace.
- Le pause fra richieste vengono **triplicate in CI** (`SCREENER_PACING=3.0`).
  Il giro notturno non ha fretta.
- La cache di `.cache/` viene ripristinata a ogni run: al secondo giro i
  fondamentali arrivano da disco e le richieste a Yahoo crollano.
- `screener/publish.py` **rifiuta di pubblicare** una run degradata.

Nessuna di queste rende l'IP residenziale. Riducono i blocchi, non li
eliminano. Se dopo qualche settimana il blocco diventa sistematico, la
soluzione definitiva è il **self-hosted runner** — vedi in fondo.

---

## Setup, una volta sola

**1. Repository.** Metti il progetto su GitHub. Il file
`.github/workflows/screen.yml` è già pronto.

**2. Attiva Pages.** Settings → Pages → *Source*: **GitHub Actions**
(non "Deploy from a branch").

**3. Primo giro a mano.** Actions → *screen* → **Run workflow**. Il primo giro
è il lento: scarica i fondamentali di tutto l'universo. Da 40 a 90 minuti,
molto più dei giri successivi.

**4. L'URL.** `https://<tuo-utente>.github.io/<nome-repo>/`
Sempre lo stesso, sempre l'ultima versione buona.

Da lì in poi gira da solo **ogni 3 ore, dal lunedì al venerdì**.

Il giro delle 23:00 UTC resta quello di riferimento: è l'unico momento in cui
USA, Europa e Asia hanno tutti chiuso, quindi l'unico in cui i percentili di
settore confrontano prezzi nello stesso stato. Gli altri sette giri servono a
vedere i movimenti durante la giornata — aggiornano le colonne guidate dal
prezzo (σ 1M, drawdown, RSI, il lato-prezzo dello scarto), mentre qualità,
valore e stime restano fermi fino al rinnovo delle rispettive cache.

Il workflow passa `--force-prices`: senza, i giri dal secondo in poi
rileggerebbero la cache prezzi del giorno — che è **un file al giorno** — e
ripubblicherebbero una pagina identica. Costa circa 6 richieste a giro
(i prezzi si scaricano in batch da 80 ticker), non 452.

### Cosa finisce online

| Percorso | Contenuto |
|---|---|
| `/` | l'ultimo screen valido |
| `/archive/screen_YYYY-MM-DD.html` | ultimi 60 giorni |
| `/archive/screen_YYYY-MM-DD.csv` | i primi 100 in CSV |
| `/status.json` | copertura e data dell'ultima run, per monitoraggio |
| `/history.json` | elenco dei report archiviati |

---

## Pubblico o privato

GitHub Pages su piano gratuito funziona **solo con repository pubblici**. La
tua dashboard sarebbe raggiungibile da chiunque conosca l'URL. Non contiene
dati personali — sono società quotate — ma è comunque la tua strategia in
chiaro. Tre strade:

| Opzione | Costo | Privacy |
|---|---|---|
| Repo pubblico + GitHub Pages | 0 € | pagina pubblica |
| Repo privato + **Cloudflare Pages** | 0 € | sorgente privata, e Cloudflare Access dà login vero fino a 50 utenti, gratis |
| Repo privato + GitHub Pages | ~4 €/mese (GitHub Pro) | tutto privato |

Se ti interessa tenerla riservata senza pagare, Cloudflare Pages è la scelta
migliore: cambia solo l'ultimo passo del workflow, il resto resta identico.

---

## Quando qualcosa va storto

**Il sito non si aggiorna e non capisci perché.** Guarda `/status.json`: c'è
`generatedAt`. Se è vecchio, la run è fallita o è stata bloccata dal gate.
Actions → ultima run → il *Summary* riporta i numeri di copertura.

**Il gate blocca ogni notte.** Quasi sempre è rate limiting. Nell'ordine:
alza `SCREENER_PACING` a `5.0` nel workflow; lancia a mano con `fast: true`
(fondamentali solo per chi passa il trigger, molte meno richieste); riduci
l'universo in `config.py`. Se non basta, passa al self-hosted runner.

**"Zero candidati oltre il trigger."** Non è un guasto: è un mercato calmo.
Il workflow esce con un *notice* e non pubblica, così l'ultima pagina buona
resta al suo posto. Per pubblicare comunque, lancia a mano con
`allow_empty: true`.

**La pagina c'è ma i dati sono di tre giorni fa.** È il comportamento
progettato: meglio una pagina vecchia che si dichiara vecchia — il banner di
freschezza nel report diventa rosso da solo dopo 72 ore — che una pagina
fresca con dentro numeri sbagliati.

**L'archivio è sparito.** Vive nella cache di Actions, che GitHub sfratta dopo
7 giorni di inutilizzo o oltre i 10 GB. Girando otto volte al giorno resta
caldissima, ma proprio per questo il tetto dei 10 GB arriva prima: ogni giro
salva uno snapshot completo di `.cache` e `output`, e lo sfratto è LRU — le
voci vecchie cadono per prime, quella nuova sopravvive. Se sospendi il
workflow per una settimana l'archivio si perde comunque. Il report corrente
no: quello sta su Pages.

---

## Self-hosted runner, se Yahoo ti blocca davvero

È la soluzione definitiva perché sposta le richieste sul tuo IP residenziale,
che Yahoo non ha motivo di bloccare. Serve una macchina accesa la notte: un
Raspberry Pi basta, o il tuo computer se lo lasci acceso.

Settings → Actions → Runners → *New self-hosted runner*, segui le istruzioni,
poi nel workflow cambia una riga:

```yaml
runs-on: self-hosted      # al posto di ubuntu-latest
```

Tutto il resto continua a funzionare, deploy su Pages compreso. Vale la pena
solo se il rate limiting diventa sistematico: prova prima qualche settimana su
runner GitHub.

---

## Costi

Zero, con repo pubblico. Actions è illimitato sui repository pubblici; su
quelli privati il piano gratuito dà 2.000 minuti al mese e una run notturna
da 25 minuti ne consuma circa 550. Ci sta comodamente, ma tienilo d'occhio se
aggiungi altri workflow.

---

## Un promemoria che l'automazione rende più necessario, non meno

Una pagina che si aggiorna da sola invita a fidarsi di più. Vale il contrario:
nessuno controlla più se il dato ha senso, e gli errori silenziosi durano
settimane invece di minuti. I gate di `publish.py` coprono il guasto grosso —
metà universo mancante — non quello sottile: un ticker delistato che resta
nell'universo, un cambio societario che falsa il CAGR, stime di consenso
aggiornate con due settimane di ritardo su un titolo asiatico.

Lo score continua a produrre **candidati da analizzare**, non decisioni, e la
riga che conta resta il Repricing Gap: se le attese sugli utili scendono quanto
il prezzo, il mercato non ha sbagliato.
