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
# KONFIGURACE A KLIENTI
# ─────────────────────────────────────────────
app = Flask(__name__)

twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"]
)
# Přechod na inteligentnější model Sonnet pro lepší češtinu
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
CLAUDE_MODEL = "claude-3-5-sonnet-20240620"

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]
ZIVY_CLOVEK = "+420602123030"
HLAS = "Google.cs-CZ-Wavenet-A"
JAZYK = "cs-CZ"

# Paměť
conversations = {}
voice_conversations = {}
voice_failures = {}
voice_silence = {}
posledni_objednavka = {}

# ─────────────────────────────────────────────
# VOCO_SYSTEM - VYLEPŠENÝ PRO HLAS
# ─────────────────────────────────────────────
VOICE_SYSTEM = (
    SYSTEM_PROMPT +
    "\n\nJsi HLASOVÝ asistent BOOM PIZZA. Mluv přirozeně, stručně a lidsky.\n"
    "1. Pokud zákazník řekne pizzu, HNED se zeptej na VELIKOST (32cm nebo 42cm).\n"
    "2. Nabídni mozzarellový nebo čedarový OKRAJ.\n"
    "3. Adresu a jméno zapiš přesně. Pokud nerozumíš, slušně se zeptej znovu.\n"
    "4. Na konci VŽDY shrň objednávku a cenu pro finální potvrzení.\n"
    "5. Jakmile zákazník potvrdí 'Ano' nebo 'Souhlasí', ukonči to značkou OBJEDNAVKA_HOTOVA.\n"
)

FRUSTRACE_SLOVA = ["do prdele", "kurva", "blbost", "idioti", "zavěsím", "přepoj", "operátora", "nerozumíš"]

# ─────────────────────────────────────────────
# POMOCNÉ FUNKCE
# ─────────────────────────────────────────────
def detekuj_frustraci(text: str) -> bool:
    t = text.lower()
    return any(slovo in t for slovo in FRUSTRACE_SLOVA)

def je_anonymni(cislo):
    anonymni = {"anonymous", "+266696687", "+86282452253", ""}
    return not cislo or cislo.lower() in anonymni or "anonymous" in cislo.lower()

def je_otevreno():
    now = datetime.now()
    return 10 <= now.hour < 22

def posli_obsluze(zprava):
    twilio_client.messages.create(from_=TWILIO_NUMBER, to=OBSLUHA_WHATSAPP, body=zprava)

def prepoj_na_obsluhu(zakaznik="", duvod=""):
    if zakaznik:
        posli_obsluze(f"⚠️ PŘEPOJENÍ: {zakaznik}\nDůvod: {duvod}")
    resp = VoiceResponse()
    resp.say("Moment, přepojuji Vás na kolegu.", voice=HLAS, language=JAZYK)
    dial = Dial(action="/po-prepojeni", timeout=30)
    dial.number(ZIVY_CLOVEK)
    resp.append(dial)
    return str(resp)

# ─────────────────────────────────────────────
# HLASOVÉ ENDPOINTY (TWILIO)
# ─────────────────────────────────────────────
@app.route("/voice", methods=["POST"])
def voice():
    zakaznik = request.form.get("From", "")
    voice_failures[zakaznik] = 0
    voice_silence[zakaznik] = 0
    voice_conversations[zakaznik] = []

    resp = VoiceResponse()
    if not je_otevreno():
        resp.say("Dobrý den, BOOM PIZZA. Máme zavřeno, otevíráme v 10 hodin.", voice=HLAS, language=JAZYK)
        return str(resp)

    # Gather nastaven na 'auto' pro přirozený konec řeči
    gather = Gather(
        input="speech",
        action="/voice-response",
        language=JAZYK,
        speech_timeout="auto",
        enhanced=True,
        timeout=5
    )

    posledni = posledni_objednavka.get(zakaznik, "")
    if posledni:
        gather.say("Vítejte zpět v BOOM PIZZA! Chcete to samé co minule?", voice=HLAS, language=JAZYK)
    else:
        gather.say("Dobrý den, BOOM PIZZA. Co si dnes dáte?", voice=HLAS, language=JAZYK)

    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)

@app.route("/voice-response", methods=["POST"])
def voice_response():
    zakaznik = request.form.get("From", "")
    vstup = request.form.get("SpeechResult", "").strip()
    zprava = normalizuj(vstup)
    
    if not zprava or len(zprava) < 2:
        return voice_no_input()

    if detekuj_frustraci(zprava):
        return prepoj_na_obsluhu(zakaznik, "Frustrace v hovoru")

    history = voice_conversations.get(zakaznik, [])
    history.append({"role": "user", "content": zprava})

    response = claude.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=VOICE_SYSTEM,
        messages=history
    )
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[zakaznik] = history[-20:]

    resp = VoiceResponse()
    
    if "OBJEDNAVKA_HOTOVA" in odpoved:
        data = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        potvrzeni = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
        posli_obsluze(f"✅ NOVÁ OBJEDNÁVKA\nTel: {zakaznik}\n{data}")
        posledni_objednavka[zakaznik] = data
        resp.say(potvrzeni, voice=HLAS, language=JAZYK)
        resp.hangup()
        return str(resp)

    if "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        return prepoj_na_obsluhu(zakaznik, "Zákazník chce operátora")

    gather = Gather(input="speech", action="/voice-response", language=JAZYK, speech_timeout="auto", enhanced=True)
    gather.say(odpoved, voice=HLAS, language=JAZYK)
    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)

@app.route("/voice-no-input", methods=["POST"])
def voice_no_input():
    zakaznik = request.form.get("From", "")
    silence = voice_silence.get(zakaznik, 0) + 1
    voice_silence[zakaznik] = silence

    if silence >= 2:
        return prepoj_na_obsluhu(zakaznik, "Ticho na lince")

    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice-response", language=JAZYK, speech_timeout="auto")
    gather.say("Jste tam? Jakou pizzu si dáte?", voice=HLAS, language=JAZYK)
    resp.append(gather)
    return str(resp)

# ─────────────────────────────────────────────
# OSTATNÍ (WHATSAPP, STATUS, ATD.)
# ─────────────────────────────────────────────
@app.route("/voice-status", methods=["POST"])
def voice_status():
    zakaznik = request.form.get("From", "")
    stav = request.form.get("CallStatus", "")
    doba = request.form.get("CallDuration", "0")
    if stav == "completed" and int(doba) < 15:
        posli_obsluze(f"⚠️ KRÁTKÝ HOVOR ({doba}s): {zakaznik} - možná selhání AI.")
    return "", 204

@app.route("/webhook", methods=["POST"])
def webhook():
    zakaznik = request.form.get("From")
    zprava = normalizuj(request.form.get("Body", "").strip())
    history = conversations.get(zakaznik, [])
    history.append({"role": "user", "content": zprava})
    response = claude.messages.create(model=CLAUDE_MODEL, max_tokens=500, system=SYSTEM_PROMPT, messages=history)
    odpoved = response.content[0].text
    history.append({"role": "assistant", "content": odpoved})
    conversations[zakaznik] = history[-20:]
    
    if "OBJEDNAVKA_HOTOVA" in odpoved:
        posli_obsluze(f"WA OBJEDNÁVKA: {zakaznik}\n{odpoved}")
    
    resp = MessagingResponse()
    resp.message(odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip())
    return str(resp)

@app.route("/po-prepojeni", methods=["POST"])
def po_prepojeni():
    return str(VoiceResponse())

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
