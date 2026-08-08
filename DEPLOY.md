# Mettere lo screener online

Obiettivo: una pagina HTML sempre raggiungibile, che si aggiorna da sola ogni
notte, senza server e senza costi.

L'architettura si presta bene perché la pipeline è già batch e produce un file
statico: **GitHub Actions** fa il calcolo (gratis), **Cloudflare Pages** serve
il risultato (gratis) e **Cloudflare Access** ci mette davanti un login vero.
Nessun database, nessun processo da tenere vivo.

```
cron 23:00 UTC → Actions: scarica, calcola, verifica → site/ → Cloudflare Pages
                     ↑                        ↓                      ↓
                  cache .cache/        se i dati non bastano     Access: login
                  e output/            NON pubblica: resta online l'ultimo buono
```

Il repository è **privato**. GitHub Pages sul piano gratuito serve solo repo
pubblici, ed è il motivo per cui il deploy non passa di lì.

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

**1. Repository.** Il progetto sta su GitHub in un repo privato. Il file
`.github/workflows/screen.yml` è già pronto.

**2. Progetto Cloudflare Pages.** Su dash.cloudflare.com → *Workers & Pages* →
*Create* → *Pages* → **Upload assets** (non "Connect to Git": il deploy lo fa
Actions con wrangler). Nome del progetto: `dislocation-screener` — deve
combaciare con `--project-name` nel workflow. Un caricamento fittizio basta a
crearlo, la prima run vera lo sovrascrive.

**3. Credenziali come secret di GitHub.** Servono due valori:

- **API token**: Cloudflare → *My Profile* → *API Tokens* → *Create Token* →
  template **Edit Cloudflare Workers**, oppure un token custom con il permesso
  `Account · Cloudflare Pages · Edit`.
- **Account ID**: è nell'URL della dashboard, `dash.cloudflare.com/<account-id>`.

Poi, senza incollarli in chiaro da nessuna parte:

```bash
gh secret set CLOUDFLARE_API_TOKEN   # incolla il token quando lo chiede
gh secret set CLOUDFLARE_ACCOUNT_ID  # incolla l'account id
```

**4. Primo giro a mano.** Actions → *screen* → **Run workflow**. Il primo giro
è il lento: scarica i fondamentali di tutto l'universo. Da 40 a 90 minuti,
molto più dei giri successivi.

**5. Il login davanti alla pagina.** Cloudflare → *Zero Trust* → *Access* →
*Applications* → *Add an application* → **Self-hosted**, dominio quello del
progetto Pages. Policy: *Allow*, con `Emails` → il tuo indirizzo. Da lì in poi
chi apre l'URL deve autenticarsi; gratis fino a 50 utenti.

**6. L'URL.** `https://dislocation-screener.pages.dev/`
Sempre lo stesso, sempre l'ultima versione buona.

Da lì in poi gira da solo alle 23:00 UTC dal lunedì al venerdì — cioè dopo la
chiusura di New York, quando anche l'Asia ha già chiuso da un pezzo.

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

GitHub Pages su piano gratuito funziona **solo con repository pubblici**: la
dashboard sarebbe raggiungibile da chiunque conosca l'URL, e per giunta
indicizzabile da Google, perché Pages non mette `noindex`. Non contiene dati
personali — sono società quotate — ma è comunque la tua strategia in chiaro,
codice compreso. Le tre strade:

| Opzione | Costo | Privacy |
|---|---|---|
| Repo pubblico + GitHub Pages | 0 € | pagina pubblica |
| **Repo privato + Cloudflare Pages** ← in uso | 0 € | sorgente privata, e Cloudflare Access dà login vero fino a 50 utenti, gratis |
| Repo privato + GitHub Pages | ~4 €/mese (GitHub Pro) | tutto privato |

È stata scelta la seconda. Senza una policy di Access davanti, però, un
progetto Pages resta pubblico: **il repo privato protegge il codice, non la
pagina**. Il login è il passo 5 del setup, non un extra facoltativo.

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
7 giorni di inutilizzo o oltre i 10 GB. Girando ogni notte resta calda, ma se
sospendi il workflow per una settimana l'archivio si perde. Il report corrente
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

Zero in euro, ma con il repo privato i minuti di Actions **non sono più
illimitati**: il piano gratuito ne dà 2.000 al mese, e una run notturna da 25
minuti ne consuma circa 550. Ci sta comodamente, però il margine adesso esiste
davvero — tienilo d'occhio se aggiungi workflow o se aumenti la frequenza.
Alzare la cadenza a ogni 3 ore, per dire, significa 8 run al giorno: sopra i
2.000 minuti si paga a consumo.

Cloudflare Pages e Access restano gratuiti: build illimitate su Pages, Access
gratis fino a 50 utenti.

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
