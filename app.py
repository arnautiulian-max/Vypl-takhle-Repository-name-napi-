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

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        notifikace = _extrahuj_notifikaci(odpoved, zakaznik)
        twilio_client.messages.create(
            from_=TWILIO_NUMBER,
            to=OBSLUHA_WHATSAPP,
            body=notifikace
        )
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()

    resp = MessagingResponse()
    resp.message(odpoved)
    return str(resp)

def _extrahuj_notifikaci(text, zakaznik_id):
    cislo = zakaznik_id.replace("whatsapp:", "")
    cast = text.split("OBJEDNAVKA_HOTOVA")[-1].strip() if "OBJEDNAVKA_HOTOVA" in text else text
    return f"🍕 NOVA OBJEDNAVKA - BOOM PIZZA\nTel: {cislo}\n\n{cast}"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
