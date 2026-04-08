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
HLAS = "Google.cs-CZ-Wavenet-A"
JAZYK = "cs-CZ"

def posli_obsluze(zprava):
    twilio_client.messages.create(
        from_=TWILIO_NUMBER,
        to=OBSLUHA_WHATSAPP,
        body=zprava
    )

def prepoj_na_obsluhu():
    resp = VoiceResponse()
    resp.say(
        "Prepojuji vas na naseho kolegu. Okamzik prosim.",
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
        posli_obsluze("NOVA OBJEDNAVKA - BOOM PIZZA\nTel: " + cislo + "\n\n" + cast)
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        cast = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[-1].strip()
        posli_obsluze("ZAKAZNIK CHCE ZAVOLAT\nTel: " + cislo + "\n\n" + cast + "\n\nZavolej zakaznikovi z cisla 602 123 030")
        odpoved = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[0].strip()
    elif "SPECIALNI_DOTAZ" in odpoved:
        cast = odpoved.split("SPECIALNI_DOTAZ")[-1].strip()
        posli_obsluze("SPECIALNI DOTAZ - BOOM PIZZA\nTel: " + cislo + "\n\n" + cast + "\n\nZavolej zakaznikovi z cisla 602 123 030")
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

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="auto",
        timeout=5
    )
    gather.say(
        "Dobry den, vitejte v BOOM PIZZA. Co si prejete objednat?",
        voice=HLAS,
        language=JAZYK
    )
    resp.append(gather)
    resp.say("Nerozumel jsem. Zkusim to znovu.", voice=HLAS, language=JAZYK)
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
                "Bot nerozumel zakaznikovi, hovor prepojeni na 602 123 030"
            )
            return prepoj_na_obsluhu()

        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/voice-response",
            language=JAZYK,
            speech_timeout="auto",
            timeout=5
        )
        gather.say(
            "Omlouvam se, nerozumel jsem. Zkuste to prosim znovu.",
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
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT + "\nDavej kratke odpovedi vhodne pro telefonni hovor. Maximalne 2-3 vety.",
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[zakaznik] = history[-20:]

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        posli_obsluze("NOVA OBJEDNAVKA TELEFON - BOOM PIZZA\nTel: " + zakaznik + "\n\n" + cast)
        odpoved_text = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
        resp = VoiceResponse()
        resp.say(odpoved_text, voice=HLAS, language=JAZYK)
        return str(resp)

    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        posli_obsluze("ZAKAZNIK CHCE MLUVIT S CLOVEKOM\nTel: " + zakaznik + "\nPrepojuji na 602 123 030")
        return prepoj_na_obsluhu()

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="auto",
        timeout=5
    )
    gather.say(odpoved, voice=HLAS, language=JAZYK)
    resp.append(gather)
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
