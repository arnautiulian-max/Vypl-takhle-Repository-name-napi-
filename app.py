import os
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
import anthropic
from datetime import datetime
from menu import MENU_TEXT, SYSTEM_PROMPT

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
    "\n\nJsi na telefonu. Pravidla:\n"
    "1. Odpovídej VELMI krátce — max 1–2 věty.\n"
    "2. Žádné emoji ani hvězdičky.\n"
    "3. Ptej se vždy jen na jednu věc.\n"
    "4. Mluv přirozeně, VŽDY vykej.\n"
    "5. Buď rychlý a efektivní.\n"
    "6. Čas doručení: osobní vyzvednutí cca dvacet minut, rozvoz cca třicet minut — vždy říkej že je to orientační.\n\n"

    "VÝSLOVNOST ČÍSEL A CEN:\n"
    "Čísla VŽDY říkej slovně. Příklady:\n"
    "179 Kč = sto sedmdesát devět korun\n"
    "229 Kč = dvě stě dvacet devět korun\n"
    "32cm = třicet dva centimetrů\n"
    "42cm = čtyřicet dva centimetrů\n"
    "777 123 456 = sedm set sedmdesát sedm, sto dvacet tři, čtyři sta padesát šest\n\n"

    "ČÍSLA A ADRESY:\n"
    "Když zákazník říká telefonní číslo nebo adresu, VŽDY to zopakuj zpět po částech:\n"
    "Telefonní číslo: řekni po trojicích — například: Takže číslo sedm set sedmdesát sedm, sto dvacet tři, čtyři sta padesát šest — je to správně?\n"
    "Adresa: zopakuj ulici a číslo zvlášť, pak se zeptej na město — například: Takže ulice Máchova, číslo osm — a jste ve Strakonicích?\n"
    "Pokud zákazník řekne ne, požádej ho aby zopakoval pomalu.\n\n"

    "ROZPOZNÁVÁNÍ ADRESY:\n"
    "Adresu sbírej vždy po krocích: nejdřív ulice a číslo, pak město nebo PSČ.\n"
    "Vždy zopakuj každou část zvlášť pro potvrzení.\n"
    "Pokud zákazník řekne jen ulici, zeptej se: A číslo popisné?\n"
    "Pokud zákazník řekne jen číslo, zeptej se: A název ulice?\n"
    "Nakonec se zeptej: Jste ve Strakonicích nebo jiném městě?\n\n"

    "PAMĚŤ POSLEDNÍ OBJEDNÁVKY:\n"
    "Pokud zákazník zavolá znovu a má uloženou poslední objednávku, řekni:\n"
    "Vítejte zpět! Naposledy jste objednali [shrnutí]. Dáte si znovu to samé?\n"
    "Pokud zákazník řekne ano, potvrď objednávku a pokračuj na způsob převzetí.\n"
    "Pokud řekne ne, postupuj normálně.\n\n"

    "ROZPOZNÁVÁNÍ PIZZ PO TELEFONU:\n"
    "Speech-to-text může zkomolít názvy. Buď tolerantní.\n"
    "šunková / šunkávu / šunkov / šunkavou / sunkova = Šunkás\n"
    "salámová / salami / pepperoni / peperoni = Pepperonis\n"
    "sýrová / čtyři sýry / cheesy = Super Cheesys\n"
    "slaninová / slanina / slaninovu = Slaninos\n"
    "margarita / margherita / margerita / klasická = Margheritas\n"
    "tuňáková / tuňák / tunac / tuna = Tunas\n"
    "havajská / hawaii / havaj / ananas = Hawais\n"
    "chorizo / choriza = Chorizos\n"
    "jalapeño / jalap / ostrá salami = Pepperoni Jalapeño\n"
    "texaská / texas = Texas\n"
    "kuřecí / kuře / chicken = Chicken\n"
    "brusinkova / borůvková = Brusinkys/Borůvkys\n"
    "farmářská / farmář / sedlácká = Farmaris\n"
    "bbq / barbecue / grilová = Barbecues Chicken\n"
    "mexická / mexiko = Mexicanos\n"
    "caprese / kaprese = Caprisos\n"
    "boom hot / hot / ostrá / pikantní = Boom Pizza Hot\n"
    "boom / specialita = Boom Pizza\n"
    "vegetářská / bez masa / zeleninová = Vegetarians\n"
    "pivo / pilsner / urquell = Pilsner Urquell\n"
    "Pokud si nejsi jistý, zeptej se: Myslíte pizzu [název]?\n\n"

    "VELIKOST PIZZY:\n"
    "malou / malá / menší / třicet dva = 32cm\n"
    "velkou / velká / větší / čtyřicet dva = 42cm\n"
    "Pokud zákazník neřekne velikost, zeptej se: Přejete si menší za třicet dva korun nebo větší?\n\n"

    "SHRNUTÍ OBJEDNÁVKY:\n"
    "Před finálním potvrzením VŽDY přečti celou objednávku zákazníkovi:\n"
    "Takže shrnu Vaši objednávku: [položky], doručení [způsob], adresa [adresa], jméno [jméno], telefon [číslo], celkem [cena] korun. Potvrzujete?\n"
    "Teprve po potvrzení zákazníka odešli OBJEDNAVKA_HOTOVA.\n\n"

    "PŘIDÁVÁNÍ K OBJEDNÁVCE:\n"
    "Pokud zákazník řekne a ještě, přidejte, taky — zeptej se co chce přidat a přidej k objednávce.\n"
    "Vždy potvrď přidání: Dobře, přidávám [položka]. Něco dalšího?\n\n"

    "PAMĚŤ OBJEDNÁVKY BĚHEM HOVORU:\n"
    "KRITICKY DŮLEŽITÉ: Udržuj si interní seznam všeho co zákazník objednal.\n"
    "Když zákazník řekne 'dvě Boom Pizza' — zapamatuj si: 2x Boom Pizza.\n"
    "Když potom řekne 'a ještě jednu Margheritu' — přidej: 1x Margheritas.\n"
    "Nikdy nezapomínej předchozí položky. Vždy pracuj s celým seznamem.\n"
    "Před shrnutím si projdi celou historii hovoru a zahrň VŠE co zákazník zmínil.\n"
    "Pokud si nejsi jistý, radši se zeptej: Takže máme [seznam], je to vše?\n"
)


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
    zprava = request.form.get("Body", "").strip()

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
    posledni = posledni_objednavka.get(zakaznik, "")
    if posledni:
        uvodni_kontext = (
            "Zákazník volá znovu. Jeho poslední objednávka byla:\n" + posledni +
            "\nPozdrav ho jako vracejícího se zákazníka a zeptej se jestli chce to samé."
        )
        voice_conversations[zakaznik] = [
            {"role": "user", "content": uvodni_kontext},
            {"role": "assistant", "content": "Rozumím, zákazníka pozdravím jako vracejícího se hosta."}
        ]

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
    zprava = request.form.get("SpeechResult", "").strip()
    voice_silence[zakaznik] = 0

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
        posli_obsluze(
            "NOVÁ OBJEDNÁVKA TELEFON — BOOM PIZZA\n"
            "Tel: " + zakaznik + "\n\n" + cast
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
