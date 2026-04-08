import os
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
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

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]

def posli_obsluze(zprava):
    twilio_client.messages.create(
        from_=TWILIO_NUMBER,
        to=OBSLUHA_WHATSAPP,
        body=zprava
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    zakaznik = request.form.get("From")
    zprava = request.form.get("Body", "").strip()

    history = conversations.get(zakaznik, [])
    history.append({"role": "user", "content": zprava})

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    conversations[zakaznik] = history[-20:]

    cislo = zakaznik.replace("whatsapp:", "")

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        posli_obsluze(
            "NOVA OBJEDNAVKA - BOOM PIZZA\n"
            "Tel: " + cislo + "\n\n" + cast
        )
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()

    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        cast = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[-1].strip()
        posli_obsluze(
            "ZAKAZNIK CHCE ZAVOLAT\n"
            "Tel: " + cislo + "\n\n" + cast + "\n\n"
            "Zavolej zakaznikovi z cisla 602 123 030"
        )
        odpoved = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[0].strip()

    elif "SPECIALNI_DOTAZ" in odpoved:
        cast = odpoved.split("SPECIALNI_DOTAZ")[-1].strip()
        posli_obsluze(
            "SPECIALNI DOTAZ - BOOM PIZZA\n"
            "Tel: " + cislo + "\n\n" + cast + "\n\n"
            "Zavolej zakaznikovi z cisla 602 123 030"
        )
        odpoved = odpoved.split("SPECIALNI_DOTAZ")[0].strip()

    elif "PODEZRELA_ZPRAVA" in odpoved:
        cast = odpoved.split("PODEZRELA_ZPRAVA")[-1].strip()
        posli_obsluze(
            "PODEZRELA ZPRAVA\n"
            "Tel: " + cislo + "\n\n" + cast
        )
        odpoved = odpoved.split("PODEZRELA_ZPRAVA")[0].strip()

    resp = MessagingResponse()
    resp.message(odpoved)
    return str(resp)

@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language="cs-CZ",
        speech_timeout="auto",
        timeout=5
    )
    gather.say(
        "Dobry den, vitejte v BOOM PIZZA. "
        "Co si prejete objednat?",
        language="cs-CZ"
    )
    resp.append(gather)
    resp.say("Nerozumel jsem. Prosim zavolejte znovu.", language="cs-CZ")
    return str(resp)

@app.route("/voice-response", methods=["POST"])
def voice_response():
    zakaznik = request.form.get("From")
    zprava = request.form.get("SpeechResult", "").strip()

    if not zprava:
        resp = VoiceResponse()
        resp.say("Nerozumel jsem. Zkuste to prosim znovu.", language="cs-CZ")
        resp.redirect("/voice")
        return str(resp)

    history = voice_conversations.get(zakaznik, [])
    history.append({"role": "user", "content": zprava})

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT + "\nDavej kratke odpovedi vhodne pro telefonni hovor. Maximalne 2-3 vety.",
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[zakaznik] = history[-20:]

    cislo = zakaznik

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        posli_obsluze(
            "NOVA OBJEDNAVKA TELEFON - BOOM PIZZA\n"
            "Tel: " + cislo + "\n\n" + cast
        )
        odpoved_text = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
        resp = VoiceResponse()
        resp.say(odpoved_text, language="cs-CZ")
        return str(resp)

    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        posli_obsluze(
            "ZAKAZNIK CHCE MLUVIT S CLOVEKOM\n"
            "Tel: " + cislo + "\n"
            "Zavolej zakaznikovi z cisla 602 123 030"
        )
        resp = VoiceResponse()
        resp.say(
            "Samozrejme. Nas kolega vam zavola co nejdrive. Dekujeme za trpezlivost.",
            language="cs-CZ"
        )
        return str(resp)

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language="cs-CZ",
        speech_timeout="auto",
        timeout=5
    )
    gather.say(odpoved, language="cs-CZ")
    resp.append(gather)
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
