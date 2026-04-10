import os
import re
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
import anthropic
from datetime import datetime
from menu import MENU_TEXT, SYSTEM_PROMPT
from slang import normalizuj

# ─────────────────────────────────────────────
# DETEKCE FRUSTRACE
# ─────────────────────────────────────────────
FRUSTRACE_SLOVA = [
    "do prdele", "do háje", "kurva", "blbost", "idioti", "nechci", "zavěsím",
    "přepoj", "živého", "člověka", "operátora", "obsluhu", "šéfa",
    "nefunguje", "nerozumíš", "nechápeš", "blbý bot", "hrozný", "k ničemu",
    "to nestačí", "špatně", "znovu", "ještě jednou", "opět", "pořád",
    "stále", "už podruhé", "potřetí", "furt", "zase"
]

def detekuj_frustraci(text: str) -> bool:
    t = text.lower()
    return any(slovo in t for slovo in FRUSTRACE_SLOVA)

def doplnit_strakonice(text: str) -> str:
    """Neupravuje adresu — město se vždy zjistí od zákazníka."""
    return text

app = Flask(__name__)

twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"]
)
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

conversations = {}
voice_conversations = {}
voice_failures = {}
voice_silence = {}

# Paměť posledních objednávek per telefonní číslo
posledni_objednavka = {}

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]
ZIVY_CLOVEK = "+420602123030"
HLAS = "Google.cs-CZ-Wavenet-A"
JAZYK = "cs-CZ"

VOICE_SYSTEM = (
    SYSTEM_PROMPT +
    "\n\nJsi hlasový asistent pizzerie BOOM PIZZA. Chovej se jako profesionální telefonní operátor.\n\n"

    "ZLATÁ PRAVIDLA:\n"
    "1. MAX 1 věta na odpověď. Nikdy víc.\n"
    "2. NIKDY neopakuj GDPR ani žádnou úvodní větu — bylo řečeno jednou, dost.\n"
    "3. NIKDY neshrnuj co zákazník řekl pokud to není nutné pro potvrzení.\n"
    "4. Ptej se vždy jen na JEDNU věc.\n"
    "5. VŽDY vykej.\n"
    "6. Žádné 'Výborně!', 'Skvělé!', 'Samozřejmě!' — rovnou na věc.\n\n"

    "TEMPO HOVORU:\n"
    "Správný tok: zákazník mluví → ty potvrdíš jednou větou → ptáš se na další věc.\n"
    "Špatně: 'Dobře, takže jste si vybrali Boom Pizza, to je výborná volba, přejete si...'\n"
    "Správně: 'Jakou velikost — malou nebo velkou?'\n\n"

    "OBJEDNÁVKA — POŘADÍ OTÁZEK:\n"
    "1. Co si dáte? (pizza + velikost)\n"
    "2. Přidám okraj? (mozzarellový 59 Kč nebo čedarový 69 Kč)\n"
    "3. Ještě něco?\n"
    "4. Vyzvednutí nebo rozvoz?\n"
    "5. Pokud rozvoz: adresa?\n"
    "6. Jméno?\n"
    "7. Na kdy? (co nejdříve nebo konkrétní čas)\n"
    "8. Shrnutí + potvrzení (POUZE jednou, těsně před odesláním)\n\n"

    "SHRNUTÍ — POUZE JEDNOU:\n"
    "Shrnutí řekni POUZE těsně před finálním potvrzením zákazníka.\n"
    "Formát: '[položky], rozvoz na [adresa], jméno [jméno], celkem [cena] korun — potvrzujete?'\n"
    "Po potvrzení okamžitě odešli OBJEDNAVKA_HOTOVA. Nic dalšího neříkej.\n\n"

    "ČÍSLA A ADRESY:\n"
    "Telefonní číslo zákazníka dostaneme automaticky — NIKDY se ho neptej, pokud ho máme.\n"
    "Pokud systém číslo nezná (anonymní hovor nebo FaceTime), zeptej se jednoduše: Vaše číslo prosím?\n"
    "Adresu zopakuj jednou pro potvrzení, pak pokračuj.\n\n"

    "ROZPOZNÁVÁNÍ ADRESY:\n"
    "Adresu sbírej po krocích: ulice a číslo → město.\n"
    "Pokud zákazník řekne jen ulici: 'A číslo popisné?'\n"
    "Pokud zákazník řekne jen číslo: 'A název ulice?'\n"
    "Vždy se zeptej na město: 'A ve kterém městě?'\n"
    "Rozvážíme do 15 km od Strakonic — například Strakonice, Písek, Vodňany, Blatná, Horažďovice a okolí.\n"
    "Pokud zákazník řekne město které je zřejmě dál než 15 km (Praha, Brno, Plzeň...), zdvořile informuj: 'Omlouváme se, do Vašeho města bohužel nerozvážíme. Nabízíme osobní vyzvednutí.'\n\n"

    "VELIKOST PIZZY:\n"
    "malou / malá / menší / třicet dva = 32cm\n"
    "velkou / velká / větší / čtyřicet dva = 42cm\n"
    "Pokud zákazník neřekne velikost: 'Malou nebo velkou?'\n\n"

    "ROZPOZNÁVÁNÍ PIZZ PO TELEFONU:\n"
    "Buď tolerantní ke zkomolenинам od STT.\n"
    "šunková / sunkova = Šunkás\n"
    "salámová / pepperoni / peperoni = Pepperonis\n"
    "sýrová / čtyři sýry / cheesy = Super Cheesys\n"
    "slaninová / slanina = Slaninos\n"
    "margarita / margherita / klasická = Margheritas\n"
    "tuňáková / tuňák = Tunas\n"
    "havajská / hawaii / ananas = Hawais\n"
    "chorizo = Chorizos\n"
    "jalapeño / jalap / ostrá = Pepperoni Jalapeño\n"
    "texaská / texas = Texas\n"
    "kuřecí / kuře = Chicken\n"
    "brusinkova / borůvková = Brusinkys/Borůvkys\n"
    "farmářská / sedlácká = Farmaris\n"
    "bbq / barbecue = Barbecues Chicken\n"
    "mexická / mexiko = Mexicanos\n"
    "caprese / kaprese = Caprisos\n"
    "boom hot / hot / pikantní = Boom Pizza Hot\n"
    "boom / specialita = Boom Pizza\n"
    "vegetářská / bez masa = Vegetarians\n"
    "pivo / pilsner = Pilsner Urquell\n"
    "Pokud si nejsi jistý: 'Myslíte [název]?'\n\n"

    "PAMĚŤ OBJEDNÁVKY BĚHEM HOVORU:\n"
    "Udržuj interní seznam všeho co zákazník objednal.\n"
    "Nikdy nezapomínej předchozí položky.\n"
    "Pokud zákazník řekne 'a ještě' nebo 'přidejte' — přidej a potvrď jednou větou.\n\n"

    "VRACEJÍCÍ SE ZÁKAZNÍK:\n"
    "Pokud má zákazník uloženou předchozí objednávku: 'Vítejte zpět, dáte si znovu to samé?'\n"
    "Pokud ano — přejdi rovnou na způsob převzetí.\n\n"

    "ČAS DORUČENÍ:\n"
    "Vyzvednutí: cca dvacet minut. Rozvoz: cca třicet minut. Vždy orientačně.\n"
)


ANONYMNI_CISLA = {"anonymous", "+266696687", "+86282452253", ""}


def je_anonymni(cislo):
    return not cislo or cislo.lower() in ANONYMNI_CISLA or "anonymous" in cislo.lower()


def je_otevreno():
    now = datetime.now()
    return 10 <= now.hour < 22


def posli_obsluze(zprava):
    twilio_client.messages.create(
        from_=TWILIO_NUMBER,
        to=OBSLUHA_WHATSAPP,
        body=zprava
    )


def prepoj_na_obsluhu(zakaznik="", duvod=""):
    if zakaznik:
        posli_obsluze(
            "PŘÍCHOZÍ PŘEPOJENÍ\n"
            "Tel: " + zakaznik + "\n"
            "Důvod: " + (duvod or "Zákazník požádal o spojení") + "\n"
            "Zákazník čeká na lince!"
        )
    resp = VoiceResponse()
    resp.say(
        "Přepojuji Vás na kolegu.",
        voice=HLAS,
        language=JAZYK
    )
    dial = Dial(action="/po-prepojeni", timeout=30)
    dial.number(ZIVY_CLOVEK)
    resp.append(dial)
    return str(resp)


@app.route("/voice-status", methods=["POST"])
def voice_status():
    """Twilio volá tento endpoint při každé změně stavu hovoru."""
    zakaznik = request.form.get("From", "")
    stav = request.form.get("CallStatus", "")
    doba = request.form.get("CallDuration", "0")

    # Zákazník zavěsil dříve než dokončil objednávku
    if stav in ("completed", "canceled", "no-answer", "busy", "failed"):
        # Pokud hovor trval méně než 60 sekund a není hotová objednávka
        try:
            sekundy = int(doba)
        except ValueError:
            sekundy = 0

        if sekundy < 60 and stav == "completed":
            posli_obsluze(
                "⚠️ ZÁKAZNÍK ZAVĚSIL PŘEDČASNĚ\n"
                "Tel: " + zakaznik + "\n"
                "Doba hovoru: " + doba + " sekund\n"
                "Možná nedokončil objednávku — zavolej zpět!"
            )
        elif stav in ("no-answer", "busy", "failed"):
            posli_obsluze(
                "📵 ZMEŠKANÝ HOVOR\n"
                "Tel: " + zakaznik + "\n"
                "Stav: " + stav + "\n"
                "Zavolej zpět!"
            )

    return "", 204


@app.route("/po-prepojeni", methods=["POST"])
def po_prepojeni():
    dial_status = request.form.get("DialCallStatus", "")
    zakaznik = request.form.get("From", "")
    if dial_status != "completed":
        posli_obsluze(
            "ZMEŠKANÝ HOVOR\n"
            "Tel: " + zakaznik + "\n"
            "Zákazník se nedovolal — zavolej zpět!"
        )
        resp = VoiceResponse()
        resp.say(
            "Kolega je nedostupný. Zavoláme Vám zpět co nejdříve. Děkujeme.",
            voice=HLAS,
            language=JAZYK
        )
        return str(resp)
    return str(VoiceResponse())


@app.route("/webhook", methods=["POST"])
def webhook():
    zakaznik = request.form.get("From")
    zprava = normalizuj(request.form.get("Body", "").strip())

    # Detekce frustrace — pošli notifikaci obsluze
    if detekuj_frustraci(zprava):
        cislo_raw = zakaznik.replace("whatsapp:", "")
        posli_obsluze(
            "⚠️ NESPOKOJENÝ ZÁKAZNÍK — WhatsApp\n"
            "Tel: " + cislo_raw + "\n"
            "Zpráva: " + zprava + "\n"
            "Zkontroluj konverzaci!"
        )

    if not je_otevreno():
        resp = MessagingResponse()
        resp.message(
            "Dobrý den! Děkujeme za Vaši zprávu. "
            "Momentálně jsme zavřeni. "
            "Provozní doba: Po–Ne 10:00–22:00. "
            "Rádi Vám pomůžeme s objednávkou od 10:00!"
        )
        return str(resp)

    history = conversations.get(zakaznik, [])
    history.append({"role": "user", "content": zprava})

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    conversations[zakaznik] = history[-20:]

    cislo = zakaznik.replace("whatsapp:", "")

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        cast = cast.replace("AUTOMATICKY_Z_SYSTEMU", cislo)
        posli_obsluze("NOVÁ OBJEDNÁVKA — BOOM PIZZA\nTel: " + cislo + "\n\n" + cast)
        posledni_objednavka[cislo] = cast
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        posli_obsluze("ZÁKAZNÍK CHCE ZAVOLAT\nTel: " + cislo + "\n\nZavolej z čísla 602 123 030")
        odpoved = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[0].strip()
    elif "SPECIALNI_DOTAZ" in odpoved:
        cast = odpoved.split("SPECIALNI_DOTAZ")[-1].strip()
        posli_obsluze("SPECIÁLNÍ DOTAZ\nTel: " + cislo + "\n\n" + cast + "\n\nZavolej z čísla 602 123 030")
        odpoved = odpoved.split("SPECIALNI_DOTAZ")[0].strip()
    elif "PODEZRELA_ZPRAVA" in odpoved:
        cast = odpoved.split("PODEZRELA_ZPRAVA")[-1].strip()
        posli_obsluze("PODEZŘELÁ ZPRÁVA\nTel: " + cislo + "\n\n" + cast)
        odpoved = odpoved.split("PODEZRELA_ZPRAVA")[0].strip()

    resp = MessagingResponse()
    resp.message(odpoved)
    return str(resp)


@app.route("/voice", methods=["POST"])
def voice():
    zakaznik = request.form.get("From", "")
    voice_failures[zakaznik] = 0
    voice_silence[zakaznik] = 0

    # Načti historii — pokud zákazník volá znovu, vložíme kontext poslední objednávky
    voice_conversations[zakaznik] = []
    posledni = posledni_objednavka.get(zakaznik, "") if not je_anonymni(zakaznik) else ""

    # Předej botovi info o číslu
    if je_anonymni(zakaznik):
        voice_conversations[zakaznik] = [
            {"role": "user", "content": "Telefonní číslo zákazníka není k dispozici (anonymní hovor nebo FaceTime). Až budeš sbírat kontaktní údaje, zeptej se na číslo."},
            {"role": "assistant", "content": "Rozumím, zeptám se zákazníka na číslo při sbírání kontaktů."}
        ]
    elif posledni:
        uvodni_kontext = (
            "Zákazník volá znovu. Jeho poslední objednávka byla:\n" + posledni +
            "\nPozdrav ho jako vracejícího se zákazníka a zeptej se jestli chce to samé."
        )
        voice_conversations[zakaznik] = [
            {"role": "user", "content": uvodni_kontext},
            {"role": "assistant", "content": "Rozumím, zákazníka pozdravím jako vracejícího se hosta."}
        ]

    # DŮLEŽITÉ: V Twilio konzoli nastav Status Callback URL na:
    # https://vypl-takhle-repository-name-napi-production.up.railway.app/voice-status
    resp = VoiceResponse()

    if not je_otevreno():
        resp.say(
            "Dobrý den, BOOM PIZZA. Momentálně jsme zavřeni. "
            "Otevíráme v deset hodin. Zavolejte nám znovu. Děkujeme.",
            voice=HLAS,
            language=JAZYK
        )
        return str(resp)

    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="2",
        timeout=5
    )

    if posledni:
        gather.say(
            "Dobrý den, BOOM PIZZA. "
            "Vítejte zpět! Chcete objednat znovu to samé jako minule?",
            voice=HLAS,
            language=JAZYK
        )
    else:
        gather.say(
            "Dobrý den, BOOM PIZZA. "
            "Tento hovor může být zaznamenán pro účely zpracování objednávky. "
            "Pokračováním v hovoru souhlasíte se zpracováním osobních údajů. "
            "Co Vám mohu dát?",
            voice=HLAS,
            language=JAZYK
        )

    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)


@app.route("/voice-no-input", methods=["POST"])
def voice_no_input():
    zakaznik = request.form.get("From", "")
    silence = voice_silence.get(zakaznik, 0) + 1
    voice_silence[zakaznik] = silence

    if silence >= 2:
        voice_silence[zakaznik] = 0
        return prepoj_na_obsluhu(zakaznik, "Zákazník neodpověděl")

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="2",
        timeout=5
    )
    gather.say(
        "Jste tam? Jak Vám mohu pomoci?",
        voice=HLAS,
        language=JAZYK
    )
    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)


@app.route("/voice-response", methods=["POST"])
def voice_response():
    zakaznik = request.form.get("From", "")
    zprava = normalizuj(request.form.get("SpeechResult", "").strip())
    zprava = doplnit_strakonice(zprava)
    voice_silence[zakaznik] = 0

    # Detekce frustrace — přepoj okamžitě a pošli notifikaci
    if detekuj_frustraci(zprava):
        posli_obsluze(
            "⚠️ NESPOKOJENÝ ZÁKAZNÍK — Telefon\n"
            "Tel: " + zakaznik + "\n"
            "Řekl: " + zprava + "\n"
            "Přepojuji na tebe!"
        )
        return prepoj_na_obsluhu(zakaznik, "Zákazník frustrovaný — automatické přepojení")

    if not zprava:
        failures = voice_failures.get(zakaznik, 0) + 1
        voice_failures[zakaznik] = failures

        if failures >= 2:
            voice_failures[zakaznik] = 0
            return prepoj_na_obsluhu(zakaznik, "Bot nerozuměl zákazníkovi")

        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/voice-response",
            language=JAZYK,
            speech_timeout="2",
            timeout=5
        )
        gather.say(
            "Nerozuměl jsem, zkuste znovu prosím.",
            voice=HLAS,
            language=JAZYK
        )
        resp.append(gather)
        resp.redirect("/voice-response")
        return str(resp)

    voice_failures[zakaznik] = 0

    history = voice_conversations.get(zakaznik, [])
    history.append({"role": "user", "content": zprava})

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=VOICE_SYSTEM,
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[zakaznik] = history[-30:]

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        if je_anonymni(zakaznik):
            # Číslo řekl zákazník sám — bot ho zapsal do objednávky
            pass
        else:
            cast = cast.replace("AUTOMATICKY_Z_SYSTEMU", zakaznik)
        posli_obsluze(
            "NOVÁ OBJEDNÁVKA TELEFON — BOOM PIZZA\n"
            "Tel: " + (zakaznik if not je_anonymni(zakaznik) else "viz objednávka") + "\n\n" + cast
        )
        posledni_objednavka[zakaznik] = cast
        odpoved_text = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
        resp = VoiceResponse()
        resp.say(odpoved_text, voice=HLAS, language=JAZYK)
        return str(resp)

    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        return prepoj_na_obsluhu(zakaznik, "Zákazník požádal o živého člověka")

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="2",
        timeout=5
    )
    gather.say(odpoved, voice=HLAS, language=JAZYK)
    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)


@app.route("/voice-status", methods=["POST"])
def voice_status():
    """Twilio volá tento endpoint po skončení hovoru."""
    zakaznik = request.form.get("From", "")
    status = request.form.get("CallStatus", "")
    doba = request.form.get("CallDuration", "0")

    # Ignoruj hovory které skončily normálně (objednávka hotova nebo přepojení)
    if status in ("completed", "busy", "failed", "no-answer"):
        # Zkontroluj jestli zákazník měl rozdělanou objednávku
        history = voice_conversations.get(zakaznik, [])
        mel_objednavku = any(
            "OBJEDNAVKA_HOTOVA" in msg.get("content", "")
            for msg in history
        )

        if not mel_objednavku and int(doba) > 5:
            # Zákazník zavěsil bez dokončení objednávky
            posli_obsluze(
                "📵 ZÁKAZNÍK ZAVĚSIL BEZ OBJEDNÁVKY\n"
                "Tel: " + zakaznik + "\n"
                "Doba hovoru: " + doba + " sekund\n"
                "Zavolej zpět!"
            )

    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)
