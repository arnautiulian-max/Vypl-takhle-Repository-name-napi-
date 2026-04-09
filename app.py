import os
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
import anthropic
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

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]
ZIVY_CLOVEK = "+420602123030"
HLAS = "Google.cs-CZ-Wavenet-B"
JAZYK = "cs-CZ"

VOICE_SYSTEM = (
    SYSTEM_PROMPT +
    "\n\nJsi na telefonu. Pravidla pro telefonni hovor:\n"
    "1. Odpovídej VELMI kratce - maximálne 1-2 vety.\n"
    "2. Nepouzivej emoji ani hvezdicky.\n"
    "3. Ptej se vzdy jen na jednu vec najednou.\n"
    "4. Mluv prirozene jako clovek na telefonu.\n"
    "5. VZDY vykej zakaznikovi.\n"
    "6. Nerikej ceny pokud se zakaznik nezepta - jen potvrd pizzu a zeptej se na dalsi vec.\n"
    "7. Po potvrzeni objednavky rekni jen: Dekujeme, pizzu mame za X minut."
)

def posli_obsluze(zprava):
    twilio_client.messages.create(
        from_=TWILIO_NUMBER,
        to=OBSLUHA_WHATSAPP,
        body=zprava
    )

def prepoj_na_obsluhu():
    resp = VoiceResponse()
    resp.say(
        "Prepojuji Vas na naseho kolegu. Okamzik prosim.",
        voice=HLAS,
        language=JAZYK
    )
    dial = Dial()
    dial.number(ZIVY_CLOVEK)
    resp.append(dial)
    return str(resp)

@app.route("/webhook", methods=["POST"])
def webhook():
    zakaznik = request.form.get("From")
    zprava = request.form.get("Body", "").strip()

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
        posli_obsluze("ZAKAZNIK CHCE ZAVOLAT\nTel: " + cislo + "\n\n" + cast + "\n\nZavolej z cisla 602 123 030")
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
    voice_conversations[zakaznik] = []

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="1",
        timeout=4
    )
    gather.say(
        "Dobry den, BOOM PIZZA, co si Vas mohu dat?",
        voice=HLAS,
        language=JAZYK
    )
    resp.append(gather)
    resp.redirect("/voice")
    return str(resp)

@app.route("/voice-response", methods=["POST"])
def voice_response():
    zakaznik = request.form.get("From", "")
    zprava = request.form.get("SpeechResult", "").strip()

    if not zprava:
        failures = voice_failures.get(zakaznik, 0) + 1
        voice_failures[zakaznik] = failures

        if failures >= 2:
            voice_failures[zakaznik] = 0
            posli_obsluze(
                "PREPOJENY HOVOR\nTel: " + zakaznik + "\n"
                "Bot nerozumel, prepojeno na 602 123 030"
            )
            return prepoj_na_obsluhu()

        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/voice-response",
            language=JAZYK,
            speech_timeout="1",
            timeout=4
        )
        gather.say(
            "Promiñte, nerozumel jsem. Zkuste to prosim znovu.",
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
        max_tokens=150,
        system=VOICE_SYSTEM,
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[zakaznik] = history[-10:]

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
        posli_obsluze(
            "ZAKAZNIK CHCE CLOVEKA\n"
            "Tel: " + zakaznik + "\n"
            "Prepojuji na 602 123 030"
        )
        return prepoj_na_obsluhu()

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="1",
        timeout=4
    )
    gather.say(odpoved, voice=HLAS, language=JAZYK)
    resp.append(gather)
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
