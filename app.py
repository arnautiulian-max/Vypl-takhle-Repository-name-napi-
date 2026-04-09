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

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]
ZIVY_CLOVEK = "+420602123030"
HLAS = "Google.cs-CZ-Wavenet-A"
JAZYK = "cs-CZ"

VOICE_SYSTEM = (
    SYSTEM_PROMPT +
    "\n\nJsi na telefonu. Pravidla:\n"
    "1. Odpovídej VELMI kratce - max 1-2 vety.\n"
    "2. Zadne emoji ani hvezdicky.\n"
    "3. Ptej se vzdy jen na jednu vec.\n"
    "4. Mluv prirozene, VZDY vykej.\n"
    "5. Bud rychly a efektivni.\n"
    "6. Cas doruceni: osobni vyzvednuti cca 20 minut, rozvoz cca 30 minut - vzdy rikej ze je to orientacni.\n\n"
    "CISLA A ADRESY:\n"
    "Kdyz zakaznik rika telefonni cislo nebo adresu, VZDY to zopakuj zpet pro potvrzeni.\n"
    "Priklad: Zakaznik rekne 777 123 456, ty reknees: Takze cislo 777 123 456, je to spravne?\n"
    "Priklad adresy: Zakaznik rekne Machackova 8, ty reknees: Takze adresa Machackova 8, je to spravne?\n"
    "Pokud zakaznik rekne ne, pozadej ho aby zopakoval cislo nebo adresu pomalu.\n\n"
    "ROZPOZNAVANI PIZZ PO TELEFONU:\n"
    "Speech-to-text muze zkomolid nazvy. Bud tolerantni.\n"
    "sunkova / sunkavu / sunkov / sunkavou = Sunkas\n"
    "salamova / salami / pepperoni / peperoni = Pepperonis\n"
    "syrova / ctyr syry / ctyri syry / cheesy = Super Cheesys\n"
    "slaninova / slanina / slaninovu = Slaninos\n"
    "margarita / margherita / margerita / klasicka = Margheritas\n"
    "tunakova / tunak / tunac / tuna = Tunas\n"
    "havajska / hawaii / havaj / ananas = Hawais\n"
    "chorizo / choriza = Chorizos\n"
    "jalapeno / jalap / ostra salami = Pepperoni Jalapeno\n"
    "texaska / texas = Texas\n"
    "kureci / kure / chicken = Chicken\n"
    "brusinkova / boruvkova = Brusinkys/Boruvkys\n"
    "farmarska / farmar / sedlacka = Farmaris\n"
    "bbq / barbecue / grilova = Barbecues Chicken\n"
    "mexicka / mexiko = Mexicanos\n"
    "caprese / kaprese = Caprisos\n"
    "boom hot / hot / ostra / pikantni = Boom Pizza Hot\n"
    "boom / specialita = Boom Pizza\n"
    "vegetarska / bez masa / zeleninova = Vegetarians\n"
    "pivo / pilsner / urquell = Pilsner Urquell\n"
    "Pokud si nejsi jisty, zeptej se: Myslite pizzu [nazev]?\n"
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
            "PRICHOZI PREPOJENI\n"
            "Tel: " + zakaznik + "\n"
            "Duvod: " + (duvod or "Zakaznik pozadal o spojeni") + "\n"
            "Zakaznik ceka na lince!"
        )
    resp = VoiceResponse()
    resp.say(
        "Prepojuji Vas na kolegu.",
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
            "ZMESKANY HOVOR\n"
            "Tel: " + zakaznik + "\n"
            "Zakaznik se nedovolal - zavolej zpet!"
        )
        resp = VoiceResponse()
        resp.say(
            "Kolega je nedostupny. Zavolame Vam zpet co nejdrive. Dekujeme.",
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
            "Dobry den! Dekujeme za Vasi zpravu. "
            "Momentalne jsme zavreni. "
            "Provozni doba: Po-Ne 10:00-22:00. "
            "Rádi Vam pomuzeme s objednavkou od 10:00!"
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
        posli_obsluze("NOVA OBJEDNAVKA - BOOM PIZZA\nTel: " + cislo + "\n\n" + cast)
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        cast = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[-1].strip()
        posli_obsluze("ZAKAZNIK CHCE ZAVOLAT\nTel: " + cislo + "\n\nZavolej z cisla 602 123 030")
        odpoved = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[0].strip()
    elif "SPECIALNI_DOTAZ" in odpoved:
        cast = odpoved.split("SPECIALNI_DOTAZ")[-1].strip()
        posli_obsluze("SPECIALNI DOTAZ\nTel: " + cislo + "\n\n" + cast + "\n\nZavolej z cisla 602 123 030")
        odpoved = odpoved.split("SPECIALNI_DOTAZ")[0].strip()
    elif "PODEZRELA_ZPRAVA" in odpoved:
        cast = odpoved.split("PODEZRELA_ZPRAVA")[-1].strip()
        posli_obsluze("PODEZRELA ZPRAVA\nTel: " + cislo + "\n\n" + cast)
        odpoved = odpoved.split("PODEZRELA_ZPRAVA")[0].strip()

    resp = MessagingResponse()
    resp.message(odpoved)
    return str(resp)

@app.route("/voice", methods=["POST"])
def voice():
    zakaznik = request.form.get("From", "")
    voice_failures[zakaznik] = 0
    voice_silence[zakaznik] = 0
    voice_conversations[zakaznik] = []

    resp = VoiceResponse()

    if not je_otevreno():
        resp.say(
            "Dobry den, BOOM PIZZA. Momentalne jsme zavreni. "
            "Otevirame v deset hodin. Zavolejte nam znovu. Dekujeme.",
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
    gather.say(
        "Dobry den, BOOM PIZZA, co Vam mohu dat?",
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
        return prepoj_na_obsluhu(zakaznik, "Zakaznik neodpovedal")

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="2",
        timeout=5
    )
    gather.say(
        "Jste tam? Jak Vam mohu pomoci?",
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
            return prepoj_na_obsluhu(zakaznik, "Bot nerozumel zakaznikovi")

        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/voice-response",
            language=JAZYK,
            speech_timeout="2",
            timeout=5
        )
        gather.say(
            "Nerozumel jsem, zkuste znovu prosim.",
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
        max_tokens=200,
        system=VOICE_SYSTEM,
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[zakaznik] = history[-16:]

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        posli_obsluze(
            "NOVA OBJEDNAVKA TELEFON - BOOM PIZZA\n"
            "Tel: " + zakaznik + "\n\n" + cast
        )
        odpoved_text = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
        resp = VoiceResponse()
        resp.say(odpoved_text, voice=HLAS, language=JAZYK)
        return str(resp)

    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        return prepoj_na_obsluhu(zakaznik, "Zakaznik pozadal o ziveho cloveka")

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
