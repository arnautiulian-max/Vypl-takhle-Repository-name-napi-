import os
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import anthropic
from menu import MENU_TEXT, SYSTEM_PROMPT

app = Flask(__name__)

twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"]
)
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

conversations = {}

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER    = os.environ["TWILIO_NUMBER"]

def posli_obsluze(zprava):
    twilio_client.messages.create(
        from_=TWILIO_NUMBER,
        to=OBSLUHA_WHATSAPP,
        body=zprava
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    zakaznik = request.form.get("From")
    zprava   = request.form.get("Body", "").strip()

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

    # Hotova objednavka
    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        posli_obsluze(
            f"🍕 NOVA OBJEDNAVKA - BOOM PIZZA\n"
            f"Tel: {cislo}\n\n{cast}"
        )
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()

    # Zakaznik chce zavolat / bot nerozumi
    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        cast = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[-1].strip()
        posli_obsluze(
            f"📞 ZAKAZNIK CHCE ZAVOLAT\n"
            f"Tel: {cislo}\n\n{cast}\n\n"
            f"➡️ Zavolej zakaznikovi z cisla 602 123 030"
        )
        odpoved = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[0].strip()

    # Specialni dotaz (akce, spoluprace, velka objednavka)
    elif "SPECIALNI_DOTAZ" in odpoved:
        cast = odpoved.split("SPECIALNI_DOTAZ")[-1].strip()
        posli_obsluze(
            f"⭐ SPECIALNI DOTAZ - BOOM PIZZA\n"
            f"Tel: {cislo}\n\n{cast}\n\n"
            f"➡️ Zavolej zakaznikovi z cisla 602 123 030"
        )
        odpoved = odpoved.split("SPECIALNI_DOTAZ")[0].strip()

    # Podezrela zprava
    elif "PODEZRELA_ZPRAVA" in odpoved:
        cast = odpoved.split("PODEZRELA_ZPRAVA")[-1].strip()
        posli_obsluze(
            f"⚠️ PODEZRELA ZPRAVA\n"
            f"Tel: {cislo}\n\n{cast}"
        )
        odpoved = odpoved.split("PODEZRELA_ZPRAVA")[0].strip()

    resp = MessagingResponse()
    resp.message(odpoved)
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
