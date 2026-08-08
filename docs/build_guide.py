"""Genera la guida d'uso in PDF.

    python docs/build_guide.py [percorso.pdf]

Nota sui caratteri: i font incorporati di ReportLab usano WinAnsi, che NON
contiene sigma, delta, la freccia o il segno meno tipografico. Scritti a mano
diventano quadratini neri nel PDF, quindi qui si usa solo Latin-1: "sigma" per
esteso, "->" per le frecce, il trattino normale per il meno.
"""
from __future__ import annotations

import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

# Palette allineata alla dashboard (tema chiaro).
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
FAINT = colors.HexColor("#657485")
LINE = colors.HexColor("#E2E8F0")
PANEL = colors.HexColor("#F8FAFC")
ACCENT = colors.HexColor("#B45309")
DANGER = colors.HexColor("#B42318")
OK = colors.HexColor("#067647")
BLUE = colors.HexColor("#0369A1")

URL = "https://lttech00.github.io/dislocation-screener/"

ss = getSampleStyleSheet()


def style(name, parent="BodyText", **kw):
    return ParagraphStyle(name, parent=ss[parent], **kw)


BODY = style("body", fontName="Helvetica", fontSize=9.7, leading=14.6,
             textColor=INK, spaceAfter=7, alignment=TA_LEFT)
LEAD = style("lead", fontName="Helvetica", fontSize=11, leading=16.5,
             textColor=MUTED, spaceAfter=11)
H1 = style("h1", fontName="Helvetica-Bold", fontSize=17, leading=21,
           textColor=INK, spaceBefore=2, spaceAfter=3)
H2 = style("h2", fontName="Helvetica-Bold", fontSize=11.6, leading=15,
           textColor=INK, spaceBefore=15, spaceAfter=5)
KICKER = style("kicker", fontName="Helvetica-Bold", fontSize=7.6, leading=10,
               textColor=ACCENT, spaceAfter=3)
BULLET = style("bullet", parent="BodyText", fontName="Helvetica", fontSize=9.7,
               leading=14.3, textColor=INK, leftIndent=11, bulletIndent=1,
               spaceAfter=4)
CELL = style("cell", fontName="Helvetica", fontSize=8.7, leading=12, textColor=INK)
CELLB = style("cellb", fontName="Helvetica-Bold", fontSize=8.7, leading=12, textColor=INK)
CELLH = style("cellh", fontName="Helvetica-Bold", fontSize=7.4, leading=10,
              textColor=FAINT)
NOTE = style("note", fontName="Helvetica", fontSize=9.2, leading=13.6, textColor=INK)
CAP = style("cap", fontName="Helvetica-Oblique", fontSize=8.4, leading=12,
            textColor=FAINT, spaceAfter=9)


def para(text, st=BODY):
    return Paragraph(text, st)


def bullets(items, st=BULLET):
    return [Paragraph(t, st, bulletText="•") for t in items]


def callout(title, text, tint=PANEL, bar=ACCENT):
    """Riquadro con barra colorata a sinistra: usato per le regole che
    contano davvero e per gli avvisi."""
    inner = [Paragraph(title, style("cot", fontName="Helvetica-Bold", fontSize=8.6,
                                    leading=11.5, textColor=bar, spaceAfter=3))]
    inner.append(Paragraph(text, NOTE))
    t = Table([[inner]], colWidths=[163 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def table(header, rows, widths):
    data = [[Paragraph(h.upper(), CELLH) for h in header]]
    for r in rows:
        data.append([Paragraph(c, CELLB if i == 0 else CELL) for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.white]),
    ]))
    return t


# ------------------------------------------------------------------ pagina
def decorate(canvas, doc, cover=False):
    canvas.saveState()
    w, h = A4
    if cover:
        canvas.setFillColor(INK)
        canvas.rect(0, h - 88 * mm, w, 88 * mm, stroke=0, fill=1)
    else:
        canvas.setFont("Helvetica", 7.4)
        canvas.setFillColor(FAINT)
        canvas.drawString(24 * mm, h - 13 * mm, "DISLOCATION SCREENER  /  GUIDA D'USO")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(24 * mm, h - 15.5 * mm, w - 24 * mm, h - 15.5 * mm)
        canvas.drawRightString(w - 24 * mm, 13 * mm, str(canvas.getPageNumber()))
    canvas.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A4, title="Dislocation Screener - Guida d'uso",
                         author="Dislocation Screener", leftMargin=24 * mm,
                         rightMargin=24 * mm, topMargin=22 * mm, bottomMargin=20 * mm)
        body = Frame(24 * mm, 20 * mm, A4[0] - 48 * mm, A4[1] - 42 * mm, id="body")
        cover = Frame(24 * mm, 20 * mm, A4[0] - 48 * mm, A4[1] - 42 * mm, id="cover")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover],
                         onPage=lambda c, d: decorate(c, d, cover=True)),
            PageTemplate(id="body", frames=[body], onPage=decorate),
        ])


def build(path):
    doc = Doc(path)
    S = []

    # ---------------------------------------------------------- copertina
    S.append(Spacer(1, 26 * mm))
    S.append(para("GUIDA D'USO", style("ct", fontName="Helvetica-Bold", fontSize=8,
                                       leading=11, textColor=colors.HexColor("#94A3B8"),
                                       spaceAfter=7)))
    S.append(para("Dislocation<br/>Screener",
                  style("ctitle", fontName="Helvetica-Bold", fontSize=34, leading=38,
                        textColor=colors.white, spaceAfter=12)))
    S.append(para("Societ&agrave; di qualit&agrave; il cui prezzo &egrave; sceso molto pi&ugrave; "
                  "delle attese sui loro utili.",
                  style("csub", fontName="Helvetica", fontSize=12, leading=17,
                        textColor=colors.HexColor("#CBD5E1"), spaceAfter=0)))
    S.append(Spacer(1, 34 * mm))
    S.append(para(f'<font color="#0369A1">{URL}</font>',
                  style("curl", fontName="Helvetica-Bold", fontSize=10, leading=14,
                        textColor=BLUE, spaceAfter=4)))
    S.append(para(f"Aggiornato al {date.today().strftime('%d/%m/%Y')} &middot; "
                  "la dashboard si rigenera da sola ogni 3 ore nei feriali",
                  style("cdate", fontName="Helvetica", fontSize=8.6, leading=12,
                        textColor=FAINT)))
    S.append(Spacer(1, 16 * mm))
    S.append(callout(
        "COME &Egrave; FATTA QUESTA GUIDA",
        "Cinque capitoli: l'idea in una pagina, come si legge la schermata "
        "principale, come nasce il punteggio, che cosa mostra il dettaglio di un "
        "titolo e dove i dati sono deboli. Se hai fretta, i due pezzi che servono "
        "davvero sono <b>il Repricing Gap</b> (pagina 2) e <b>la routine in cinque "
        "passi</b> (pagina 5).",
        tint=PANEL, bar=BLUE))

    S.append(NextPageTemplate("body"))
    S.append(PageBreak())

    # ------------------------------------------------------------- 1. idea
    S.append(para("L'IDEA IN UNA PAGINA", KICKER))
    S.append(para("Che cosa cerca", H1))
    S.append(para("Un calo violento su un business che non &egrave; peggiorato quanto il "
                  "prezzo suggerisce. I casi di scuola sono IBM, Ferrari, Luxottica: "
                  "il titolo perde il 25%, ma gli analisti tagliano le stime sugli utili "
                  "solo del 3%. Quella distanza &egrave; l'anomalia.", LEAD))
    S.append(para(
        "L'universo &egrave; S&amp;P 500 pi&ugrave; large cap europee e asiatiche - circa 900-1.100 "
        "titoli, con copertura dedicata ai semiconduttori. Ogni tre ore la pipeline "
        "scarica prezzi, stime e notizie, calcola, e pubblica una pagina sola. "
        "Non c'&egrave; nulla da installare e nulla da tenere acceso."))

    S.append(para("Le tre domande a cui risponde", H2))
    S.extend(bullets([
        "<b>Quali titoli sono crollati in modo statisticamente anomalo?</b> Non "
        "&quot;chi &egrave; sceso di pi&ugrave;&quot;, ma chi &egrave; sceso pi&ugrave; di quanto la sua "
        "volatilit&agrave; renda normale.",
        "<b>Di questi, quali sono aziende decenti?</b> ROIC, conversione di cassa, "
        "copertura degli interessi, stabilit&agrave; dei margini - tutto misurato "
        "<i>dentro il settore</i>, mai contro soglie assolute.",
        "<b>Il mercato sta sbagliando o ha ragione?</b> &Egrave; la domanda vera, e la "
        "risponde una riga sola: il Repricing Gap.",
    ]))

    S.append(callout(
        "LA REGOLA CHE CONTA PI&Ugrave; DI TUTTE",
        "Se le attese sugli utili scendono <i>quanto</i> il prezzo, il mercato non ha "
        "sbagliato: ha riprezzato un'azienda che &egrave; davvero peggiorata. "
        "L'occasione esiste solo quando il prezzo scende <b>molto pi&ugrave;</b> delle stime. "
        "Tutto il resto della dashboard &egrave; contorno intorno a questa distanza.",
        tint=PANEL, bar=BLUE))

    S.append(para("Dove vive e quando cambia", H2))
    S.append(table(
        ["Quando", "Cosa succede"],
        [["Ogni 3 ore, lun-ven", "La pipeline gira su GitHub Actions: scarica, calcola, "
          "verifica. Otto giri al giorno; l'orario pu&ograve; slittare di mezz'ora."],
         ["Il giro delle 23:00 UTC", "&Egrave; quello di riferimento: l'unico momento in cui "
          "USA, Europa e Asia hanno tutti chiuso, quindi l'unico in cui il confronto fra "
          "titoli di regioni diverse &egrave; alla pari. Gli altri sette aggiornano solo le "
          "colonne guidate dal prezzo - qualit&agrave;, valore e stime non si muovono."],
         ["Se i dati bastano", "La pagina viene sostituita con lo screen nuovo."],
         ["Se i dati non bastano", "<b>Non</b> pubblica: resta online l'ultima versione buona, "
          "e il banner di freschezza ingiallisce e poi arrossisce da solo."],
         ["Weekend", "Nessun aggiornamento: i mercati sono chiusi, non c'&egrave; niente "
          "di nuovo da calcolare."]],
        [34 * mm, 129 * mm]))
    S.append(Spacer(1, 3))
    S.append(para("L'indirizzo non cambia mai: mettilo nei preferiti e apri quello.", CAP))

    S.append(PageBreak())

    # --------------------------------------------------------- 2. la pagina
    S.append(para("ANATOMIA", KICKER))
    S.append(para("Leggere la pagina principale", H1))
    S.append(para("Dall'alto verso il basso la dashboard ha quattro fasce: lo stato dei "
                  "dati, i controlli, il conteggio, la tabella.", LEAD))

    S.append(para("1. Lo stato dei dati, in alto a destra", H2))
    S.append(para(
        "&Egrave; la prima cosa da guardare, prima ancora dei titoli. Riporta data e ora "
        "dell'ultimo giro, data dei prezzi, et&agrave; dei fondamentali, copertura delle "
        "stime e stato dei cambi. Il pallino &egrave; verde se il giro &egrave; recente."))
    S.extend(bullets([
        "<font color='#B45309'><b>Fascia ambra</b></font> - i dati hanno pi&ugrave; di 24 ore.",
        "<font color='#B42318'><b>Fascia rossa</b></font> - oltre le 72 ore. La pagina "
        "&egrave; vecchia e te lo sta dicendo: qualcosa nell'automazione si &egrave; inceppato.",
    ]))
    S.append(para("Una pagina vecchia che si dichiara vecchia &egrave; preferibile a una "
                  "pagina fresca con numeri sbagliati. Il banner non &egrave; un difetto, "
                  "&egrave; la funzione di sicurezza.", CAP))

    S.append(para("2. I pesi, regolabili dal vivo", H2))
    S.append(para(
        "I cinque cursori cambiano quanto conta ciascun asse. Il ranking si "
        "ricalcola <b>nel browser</b>, subito: i sotto-punteggi sono salvati "
        "separatamente, quindi non serve rilanciare niente. Alza <i>Qualit&agrave;</i> se "
        "vuoi solo aziende solide, alza <i>Dislocazione</i> se cerchi i crolli pi&ugrave; "
        "estremi. Il pulsante ripristina i pesi di partenza."))

    S.append(para("3. I filtri", H2))
    S.append(para(
        "Regione, settore, ricerca per nome o ticker, il filtro &quot;solo "
        "semiconduttori&quot; e la <b>confidenza minima</b>. Quest'ultima merita "
        "attenzione: scarta i titoli per cui sono stati popolati pochi campi. "
        "Alzarla a 60% toglie di mezzo i nomi su cui i dati sono troppo lacunosi "
        "per fidarsi del punteggio."))

    S.append(para("4. Le colonne della tabella", H2))
    S.append(table(
        ["Colonna", "Che cosa dice"],
        [["Score", "Il punteggio composito 0-100, gi&agrave; al netto delle penalit&agrave;. "
                   "La barretta accanto mostra da quali assi arriva."],
         ["sigma 1M", "Di quante deviazioni standard il titolo &egrave; sceso nell'ultimo "
                      "mese. <b>&Egrave; la colonna pi&ugrave; onesta della tabella:</b> -10% su un "
                      "titolo volatile &egrave; rumore, sullo stesso calo di un titolo tranquillo "
                      "&egrave; un evento raro."],
         ["1M %", "Il calo nudo dell'ultimo mese, in percentuale."],
         ["Scarto 30g", "Il Repricing Gap: quanto il prezzo &egrave; sceso pi&ugrave; delle stime "
                        "negli ultimi 30 giorni. In evidenza quando &egrave; ampio."],
         ["Conf.", "Confidenza dei dati per quel titolo: quanti campi sono stati "
                   "davvero trovati. Barra corta, punteggio da prendere con le pinze."]],
        [26 * mm, 137 * mm]))
    S.append(Spacer(1, 4))
    S.append(para("Ogni intestazione &egrave; cliccabile per ordinare. Clicca una riga "
                  "qualsiasi per aprire il dettaglio.", CAP))

    S.append(PageBreak())

    # ------------------------------------------------------------ 3. assi
    S.append(para("IL PUNTEGGIO", KICKER))
    S.append(para("I cinque assi", H1))
    S.append(para("Ogni asse &egrave; costruito su percentili calcolati dentro il settore, "
                  "mai su soglie assolute: un ROIC del 12% &egrave; ottimo per un'utility e "
                  "mediocre per il software.", LEAD))
    S.append(table(
        ["Asse", "Peso", "Che cosa misura"],
        [["Dislocazione", "25%", "Movimento in sigma, extra-rendimento negativo rispetto "
                                 "alla mediana di settore, drawdown dal massimo, "
                                 "concentrazione del calo in pochi giorni."],
         ["Qualit&agrave;", "25%", "ROIC contro il settore e il suo trend, cassa generata "
                              "rispetto all'utile, copertura degli interessi, stabilit&agrave; "
                              "dei margini."],
         ["Valore", "20%", "EV/EBITDA, P/E forward, FCF yield - sempre relativi al settore."],
         ["Repricing gap", "20%", "La distanza fra caduta del prezzo e revisione delle "
                                  "stime sugli utili, a 30 e 90 giorni."],
         ["Timing", "10%", "Giorni dal minimo del mese, RSI, volume di capitolazione. "
                           "Serve a non prendere il coltello mentre cade."]],
        [30 * mm, 15 * mm, 118 * mm]))

    S.append(para("Le banche non sono escluse", H2))
    S.append(para(
        "Banche e assicurazioni viaggiano su un binario separato, con P/B e ROE al "
        "posto di EV/EBITDA e debito netto: su un bilancio bancario quei multipli non "
        "significano nulla. Restano dentro proprio perch&eacute; &egrave; l&igrave; che capitano i "
        "panici pi&ugrave; irrazionali."))

    S.append(para("Le penalit&agrave;, fino a -30 punti", H2))
    S.append(para(
        "Sottratte dallo score e sempre elencate per esteso nel dettaglio, cos&igrave; "
        "sai <i>perch&eacute;</i> un titolo &egrave; stato retrocesso: leva oltre il limite del "
        "settore, copertura interessi debole, flusso di cassa negativo, ricavi o "
        "ROIC in calo, short interest alto, stime in crollo, dati incompleti."))

    S.append(callout(
        "LA PENALIT&Agrave; PI&Ugrave; IMPORTANTE",
        "Se le stime sull'utile del prossimo esercizio sono scese oltre il 15% in 90 "
        "giorni, l'asse repricing viene compresso e scatta una penalit&agrave;. Qui non c'&egrave; "
        "un errore del mercato: c'&egrave; <i>post-earnings drift</i>. Storicamente i cali "
        "innescati da notizie sui fondamentali proseguono per 60 giorni e oltre.",
        tint=colors.HexColor("#FEF2F2"), bar=DANGER))

    S.append(PageBreak())

    # --------------------------------------------------------- 4. dettaglio
    S.append(para("IL DETTAGLIO", KICKER))
    S.append(para("Che cosa vedi cliccando un titolo", H1))
    S.append(para("Si apre un pannello laterale con sei sezioni, nell'ordine in cui "
                  "conviene leggerle.", LEAD))

    S.append(para("Prezzo, ultimi 12 mesi", H2))
    S.append(para(
        "Il grafico in cima risponde alla domanda che ti fai aprendo la riga: "
        "<b>&egrave; un crollo recente o una discesa lunga un anno?</b> La fascia grigia "
        "a destra &egrave; l'ultimo mese, cio&egrave; la finestra su cui scatta il trigger; le "
        "righe tratteggiate sono minimo e massimo del periodo. Una curva che scende "
        "da dodici mesi racconta un declino strutturale, non una dislocazione."))

    S.append(para("Lo scarto - prezzo contro stime", H2))
    S.append(para(
        "Due barre a confronto: quanto &egrave; sceso il prezzo in un mese, quanto sono "
        "scese le stime in trenta giorni. La banda tratteggiata fra le due <b>&egrave; la "
        "tesi d'investimento</b>. Larga significa che il mercato ha punito il prezzo "
        "senza che gli analisti abbiano toccato i numeri. Stretta significa che non "
        "c'&egrave; nulla da vedere."))

    S.append(para("Contributo degli assi, penalit&agrave;, numeri chiave", H2))
    S.append(para(
        "Le barre mostrano quanto ciascun asse contribuisce con i pesi che hai "
        "impostato in quel momento - se muovi i cursori, cambiano. Sotto, le "
        "penalit&agrave; una per una con i punti sottratti, e una griglia con i "
        "fondamentali: ROIC e suo trend, multipli, leva, CAGR dei ricavi, short "
        "interest, volatilit&agrave;, drawdown, RSI, confidenza."))

    S.append(para("Le notizie, e il limite dello strumento", H2))
    S.append(para(
        "In fondo trovi le ultime notizie sul titolo e un link &quot;Perch&eacute; &egrave; "
        "sceso&quot; che apre la ricerca stampa sul nome. Lo screener <b>non "
        "interpreta</b> le notizie: te le mette davanti. Questa lettura resta "
        "compito tuo, ed &egrave; il passo che nessuna dashboard pu&ograve; eliminare."))

    S.append(Spacer(1, 6))
    S.append(callout(
        "UNA ROUTINE CHE FUNZIONA, IN CINQUE PASSI",
        "<b>1.</b> Guarda il banner: i dati sono freschi?&nbsp;&nbsp; "
        "<b>2.</b> Alza la confidenza minima al 60% e togli il rumore.&nbsp;&nbsp; "
        "<b>3.</b> Ordina per <i>Scarto 30g</i>, non per Score: &egrave; l&igrave; che vive la tesi."
        "&nbsp;&nbsp; <b>4.</b> Apri i primi cinque e guarda il grafico a 12 mesi - "
        "scarta chi scende da un anno.&nbsp;&nbsp; <b>5.</b> Sui sopravvissuti, leggi "
        "le notizie e cerca il motivo del calo. Se non lo trovi, non hai una tesi.",
        tint=PANEL, bar=OK))

    S.append(PageBreak())

    # ------------------------------------------------------------ 5. limiti
    S.append(para("ONEST&Agrave;", KICKER))
    S.append(para("Quando non fidarsi", H1))
    S.append(para("Ogni limite qui sotto &egrave; strutturale, non un bug che verr&agrave; "
                  "sistemato: sono il prezzo di usare solo fonti gratuite.", LEAD))

    S.append(table(
        ["Il limite", "Che cosa comporta"],
        [["Le stime di consenso<br/>sono la parte fragile",
          "Copertura buona su Stati Uniti e ADR, discreta sulle large cap europee, "
          "<b>irregolare sui listini locali asiatici</b>. Poich&eacute; il Repricing Gap "
          "vive sulle stime, su un titolo asiatico con confidenza bassa quel numero "
          "vale poco. Controlla sempre la confidenza del singolo nome."],
         ["Nessun segnale<br/>dal credito",
          "CDS e spread obbligazionari sarebbero il miglior controllo incrociato su "
          "un'azienda in difficolt&agrave;. Non esistono gratis, quindi non ci sono."],
         ["Niente insider buying",
          "Sapere che il management sta comprando sarebbe il segnale di conferma "
          "pi&ugrave; forte. Fuori portata per Europa e Asia."],
         ["Nessun backtest",
          "<b>Non sai se questo punteggio funziona.</b> Non &egrave; mai stato validato "
          "sui dati storici. &Egrave; l'avvertenza pi&ugrave; importante della guida."]],
        [40 * mm, 123 * mm]))

    S.append(para("Zero candidati non &egrave; un guasto", H2))
    S.append(para(
        "Quando il mercato &egrave; calmo il trigger pu&ograve; non restituire nulla, e in quel "
        "caso la pagina <b>non</b> viene sostituita. &Egrave; il comportamento corretto: "
        "non ci sono dislocazioni da mostrare. Una dashboard che trova sempre "
        "qualcosa &egrave; una dashboard che ha abbassato l'asticella."))

    S.append(para("I due modi in cui questa strategia perde denaro", H2))
    S.extend(bullets([
        "<b>Il coltello che cade.</b> Comprare presto durante un calo che continua. "
        "L'asse timing attenua il problema, non lo risolve.",
        "<b>Il declino strutturale scambiato per dislocazione.</b> Un'azienda il cui "
        "modello di business sta finendo sembra identica, nei numeri, a una "
        "temporaneamente sotto pressione. Nessun filtro qui dentro distingue i due casi.",
    ]))
    S.append(para(
        "Un terzo rischio &egrave; pi&ugrave; sottile e riguarda te, non lo strumento: se "
        "trenta candidati sono tutti semiconduttori, non hai trenta scommesse. "
        "Ne hai una."))

    S.append(Spacer(1, 8))
    S.append(callout(
        "L'EFFETTO COLLATERALE DELL'AUTOMAZIONE",
        "Una pagina che si aggiorna da sola invita a fidarsi di pi&ugrave;. Vale il "
        "contrario: nessuno ricontrolla se il dato ha senso, e gli errori silenziosi "
        "durano settimane invece di minuti. I controlli automatici coprono il guasto "
        "grosso - met&agrave; universo mancante - non quello sottile: un ticker delistato "
        "rimasto nell'elenco, una fusione che falsa il CAGR, stime asiatiche "
        "aggiornate con due settimane di ritardo.",
        tint=PANEL, bar=ACCENT))

    doc.build(S)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/guida-dislocation-screener.pdf"
    build(out)
    print(f"scritto {out}")
