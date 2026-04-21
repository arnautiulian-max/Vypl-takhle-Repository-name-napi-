import os
import re
import sys
import traceback
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
import anthropic
from datetime import datetime
from zoneinfo import ZoneInfo
from cachetools import TTLCache
from menu import MENU_TEXT, SYSTEM_PROMPT
from slang import normalizuj

# ─────────────────────────────────────────────
# LOGGING — vše vypisujeme do stdout, Railway to ukáže v Logs
# ─────────────────────────────────────────────
def log(msg):
    """Vypíše zprávu s časem do Railway logů."""
    cas = datetime.now(ZoneInfo("Europe/Prague")).strftime("%H:%M:%S")
    print("[" + cas + "] " + str(msg), flush=True)


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


app = Flask(__name__)

twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"]
)
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ─────────────────────────────────────────────
# TTL CACHE — automaticky mažou staré záznamy
# ─────────────────────────────────────────────
conversations = TTLCache(maxsize=1000, ttl=3600)
voice_conversations = TTLCache(maxsize=200, ttl=1800)
voice_failures = TTLCache(maxsize=200, ttl=1800)
voice_silence = TTLCache(maxsize=200, ttl=1800)
posledni_objednavka = TTLCache(maxsize=5000, ttl=2592000)

OBSLUHA_WHATSAPP = os.environ["OBSLUHA_WHATSAPP"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]
# Volitelně: SMS fallback pokud WhatsApp selže
OBSLUHA_SMS = os.environ.get("OBSLUHA_SMS", "")
ZIVY_CLOVEK = "+420602123030"
HLAS = "Google.cs-CZ-Wavenet-A"
JAZYK = "cs-CZ"

# ─────────────────────────────────────────────
# STT HINTS
# ─────────────────────────────────────────────
PIZZA_HINTS = (
    "Margheritas, Šunkás, Pepperonis, Super Cheesys, Slaninos, "
    "Tunas, Hawais, Chicken, Texas, Farmaris, Barbecues Chicken, "
    "Mexicanos, Caprisos, Chorizos, Boom Pizza, Boom Pizza Hot, "
    "Vegetarians, Vegetarians Special, Pepperoni Jalapeño, "
    "Brusinkys, Borůvkys, "
    "šunková, salámová, sýrová, slaninová, margarita, tuňáková, "
    "havajská, kuřecí, vegetariánská, mexická, ostrá, pikantní, "
    "brusinková, borůvková, farmářská, texaská, pepperoni, chorizo, "
    "malou, velkou, malá, velká, menší, větší, "
    "třicet dva, čtyřicet dva, "
    "mozzarellový okraj, čedarový okraj, bez okraje, "
    "rozvoz, vyzvednutí, s sebou, osobní vyzvednutí, "
    "Strakonice, Písek, Vodňany, Blatná, Horažďovice, "
    "Čelakovského, Máchackova, Palackého, Nábřeží, Náměstí, "
    "Pilsner Urquell, Coca Cola, Coca Cola Zero, Fanta, Sprite, "
    "Monster, Fuze Tea, Ayran, Natura, Powerade, "
    "česnekový dip, box, ingredience navíc, "
    "co nejdříve, na konkrétní čas, ano, ne, potvrzuji"
)


def novy_gather(action_url="/voice-response", include_dtmf=False):
    """Vytvoří Gather s optimalizovaným STT pro češtinu.

    include_dtmf=True → zákazník může ALTERNATIVNĚ vyťukat odpověď na klávesnici
    Používá se pro sběr čísel (popisné, telefon) protože Twilio STT komolí česká čísla.
    """
    input_types = "speech dtmf" if include_dtmf else "speech"

    return Gather(
        input=input_types,
        action=action_url,
        language=JAZYK,
        speech_timeout="3",
        timeout=7,
        enhanced=True,
        speech_model="phone_call",
        hints=PIZZA_HINTS,
        profanity_filter=False,
        action_on_empty_result=True,
        finish_on_key="#" if include_dtmf else "",   # # = uzavření zadání čísla
        num_digits=10 if include_dtmf else 0          # max 10 číslic
    )


ANONYMNI_CISLA = {"anonymous", "+266696687", "+86282452253", ""}


def je_anonymni(cislo):
    if not cislo:
        return True
    c = cislo.lower()
    return c in ANONYMNI_CISLA or "anonymous" in c


def normalizuj_cislo(s: str) -> str:
    if not s:
        return ""
    return s.replace("whatsapp:", "").strip()


def je_otevreno():
    now = datetime.now(ZoneInfo("Europe/Prague"))
    return 10 <= now.hour < 22


def posli_obsluze(zprava: str) -> bool:
    """
    Pošle zprávu obsluze přes WhatsApp.
    Pokud WhatsApp selže, zkusí SMS fallback.
    NIKDY nehází exception — vrací True/False.
    """
    log("📤 POSÍLÁM NOTIFIKACI: " + zprava[:100].replace("\n", " | "))

    # Zkus WhatsApp
    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_NUMBER,
            to=OBSLUHA_WHATSAPP,
            body=zprava
        )
        log("✅ WhatsApp odesláno, SID: " + msg.sid + ", status: " + msg.status)
        return True
    except Exception as e:
        log("❌ WhatsApp SELHAL: " + str(e))
        log(traceback.format_exc())

    # Fallback: SMS na obsluhu (pokud je nastavena proměnná OBSLUHA_SMS)
    if OBSLUHA_SMS:
        try:
            # SMS bere zdrojové Twilio číslo bez "whatsapp:" prefixu
            sms_from = TWILIO_NUMBER.replace("whatsapp:", "")
            msg = twilio_client.messages.create(
                from_=sms_from,
                to=OBSLUHA_SMS,
                body=zprava[:1500]  # SMS má limit
            )
            log("✅ SMS fallback odesláno, SID: " + msg.sid)
            return True
        except Exception as e:
            log("❌ SMS fallback SELHAL: " + str(e))
            log(traceback.format_exc())

    return False


def prepoj_na_obsluhu(zakaznik="", duvod=""):
    if zakaznik:
        posli_obsluze(
            "PŘÍCHOZÍ PŘEPOJENÍ\n"
            "Tel: " + zakaznik + "\n"
            "Důvod: " + (duvod or "Zákazník požádal o spojení") + "\n"
            "Zákazník čeká na lince!"
        )
    resp = VoiceResponse()
    resp.say("Přepojuji Vás na kolegu.", voice=HLAS, language=JAZYK)
    dial = Dial(action="/po-prepojeni", timeout=30)
    dial.number(ZIVY_CLOVEK)
    resp.append(dial)
    return str(resp)


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/voice-status", methods=["POST"])
def voice_status():
    zakaznik = request.form.get("From", "")
    stav = request.form.get("CallStatus", "")
    doba = request.form.get("CallDuration", "0")

    log("📞 STATUS: " + stav + " | " + zakaznik + " | " + doba + "s")

    if stav in ("completed", "canceled", "no-answer", "busy", "failed"):
        try:
            sekundy = int(doba)
        except ValueError:
            sekundy = 0

        if sekundy < 60 and stav == "completed":
            posli_obsluze(
                "⚠️ ZÁKAZNÍK ZAVĚSIL PŘEDČASNĚ\n"
                "Tel: " + zakaznik + "\n"
                "Doba: " + doba + "s"
            )
        elif stav in ("no-answer", "busy", "failed"):
            posli_obsluze(
                "📵 ZMEŠKANÝ HOVOR\n"
                "Tel: " + zakaznik + "\n"
                "Stav: " + stav
            )
    return "", 204


@app.route("/po-prepojeni", methods=["POST"])
def po_prepojeni():
    dial_status = request.form.get("DialCallStatus", "")
    zakaznik = request.form.get("From", "")
    if dial_status != "completed":
        posli_obsluze("ZMEŠKANÝ HOVOR\nTel: " + zakaznik + "\nZavolej zpět!")
        resp = VoiceResponse()
        resp.say(
            "Kolega je nedostupný. Zavoláme Vám zpět co nejdříve. Děkujeme.",
            voice=HLAS, language=JAZYK
        )
        return str(resp)
    return str(VoiceResponse())


@app.route("/webhook", methods=["POST"])
def webhook():
    zakaznik = request.form.get("From", "")
    zprava = normalizuj(request.form.get("Body", "").strip())
    cislo = normalizuj_cislo(zakaznik)

    log("💬 WhatsApp od " + cislo + ": " + zprava[:100])

    if detekuj_frustraci(zprava):
        posli_obsluze("⚠️ NESPOKOJENÝ ZÁKAZNÍK — WhatsApp\nTel: " + cislo + "\nZpráva: " + zprava)

    if not je_otevreno():
        resp = MessagingResponse()
        resp.message(
            "Dobrý den! Momentálně jsme zavřeni. "
            "Provozní doba: Po–Ne 10:00–22:00."
        )
        return str(resp)

    history = conversations.get(cislo, [])
    history.append({"role": "user", "content": zprava})

    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=history
        )
        odpoved = response.content[0].text
    except Exception as e:
        log("❌ Claude API SELHALO: " + str(e))
        resp = MessagingResponse()
        resp.message("Omlouváme se, nastala technická chyba. Zkuste to prosím znovu za chvíli.")
        return str(resp)

    history.append({"role": "assistant", "content": odpoved})
    conversations[cislo] = history[-20:]

    if "OBJEDNAVKA_HOTOVA" in odpoved:
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        cast = cast.replace("AUTOMATICKY_Z_SYSTEMU", cislo)
        posli_obsluze("🍕 NOVÁ OBJEDNÁVKA — WhatsApp\nTel: " + cislo + "\n\n" + cast)
        posledni_objednavka[cislo] = cast
        odpoved = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()
    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        posli_obsluze("ZÁKAZNÍK CHCE ZAVOLAT\nTel: " + cislo)
        odpoved = odpoved.split("ZAKAZNIK_CHCE_ZAVOLAT")[0].strip()
    elif "SPECIALNI_DOTAZ" in odpoved:
        cast = odpoved.split("SPECIALNI_DOTAZ")[-1].strip()
        posli_obsluze("SPECIÁLNÍ DOTAZ\nTel: " + cislo + "\n\n" + cast)
        odpoved = odpoved.split("SPECIALNI_DOTAZ")[0].strip()
    elif "PODEZRELA_ZPRAVA" in odpoved:
        cast = odpoved.split("PODEZRELA_ZPRAVA")[-1].strip()
        posli_obsluze("PODEZŘELÁ ZPRÁVA\nTel: " + cislo + "\n\n" + cast)
        odpoved = odpoved.split("PODEZRELA_ZPRAVA")[0].strip()

    resp = MessagingResponse()
    resp.message(odpoved)
    return str(resp)


VOICE_SYSTEM = (
    SYSTEM_PROMPT +
    "\n\nJsi hlasový asistent pizzerie BOOM PIZZA. Chovej se jako profesionální telefonní operátor.\n\n"

    "ZLATÁ PRAVIDLA:\n"
    "1. MAX 1 věta na odpověď. Nikdy víc.\n"
    "2. NIKDY neopakuj GDPR ani uvítání.\n"
    "3. Ptej se vždy jen na JEDNU věc.\n"
    "4. VŽDY vykej.\n"
    "5. Žádné 'Výborně!', 'Skvělé!', 'Samozřejmě!' — rovnou na věc.\n\n"

    "NEÚPLNÁ ŘEČ:\n"
    "Pokud zákazník řekne jen 'dobrý', 'ano', 'haló' nebo jednoslovnou odpověď bez kontextu,\n"
    "zeptej se krátce: 'Co si dáte?'\n\n"

    "OBJEDNÁVKA — POŘADÍ OTÁZEK:\n"
    "1. Co si dáte? (pizza + velikost)\n"
    "2. Přidám okraj? (mozzarellový 59 Kč nebo čedarový 69 Kč)\n"
    "3. Ještě něco?\n"
    "4. Vyzvednutí nebo rozvoz?\n"
    "5. Pokud rozvoz: adresa (po částech — viz níže)\n"
    "6. Jméno?\n"
    "7. Na kdy? (co nejdříve nebo konkrétní čas)\n"
    "8. Shrnutí + potvrzení (POUZE jednou, těsně před odesláním)\n\n"

    "KRITICKÉ — SBĚR ADRESY PO ČÁSTECH:\n"
    "Sbírej adresu postupně, ne najednou. Ptej se po malých kouscích:\n"
    "1. 'Jaká ulice, prosím?' — zákazník řekne ulici\n"
    "2. 'A ve kterém městě?' — zákazník řekne město\n"
    "3. 'Jaké je číslo popisné? Můžete ho říct nebo vyťukat na klávesnici a stisknout mřížku.'\n"
    "   — zákazník buď řekne, nebo vyťuká DTMF (klávesnice)\n"
    "Pokud dostaneš DTMF (jen číslice), ber to jako číslo popisné — neptej se znovu.\n"
    "Nikdy nezkoušej sbírat celou adresu jednou otázkou.\n\n"

    "ROZVOZOVÁ OBLAST:\n"
    "Rozvážíme do 15 km od Strakonic — Strakonice, Písek, Vodňany, Blatná, Horažďovice.\n"
    "Pokud město je dál (Praha, Brno, Plzeň...), řekni:\n"
    "'Omlouváme se, do Vašeho města bohužel nerozvážíme. Nabízíme osobní vyzvednutí.'\n\n"

    "SHRNUTÍ — POUZE JEDNOU:\n"
    "Formát: '[položky], rozvoz na [adresa], jméno [jméno], celkem [cena] korun — potvrzujete?'\n"
    "Po potvrzení okamžitě odešli OBJEDNAVKA_HOTOVA. Nic dalšího neříkej.\n\n"

    "ČÍSLO ZÁKAZNÍKA:\n"
    "Telefon známe automaticky — NEPTEJ SE na něj, pokud ho máme.\n"
    "Jen u anonymního hovoru se zeptej: 'Vaše číslo prosím? Můžete ho vyťukat na klávesnici.'\n\n"

    "VELIKOST PIZZY:\n"
    "malou / menší / třicet dva = 32cm\n"
    "velkou / větší / čtyřicet dva = 42cm\n\n"

    "ROZPOZNÁVÁNÍ PIZZ:\n"
    "Buď tolerantní ke zkomoleninám od STT.\n"
    "šunková = Šunkás, salámová / pepperoni = Pepperonis, sýrová / cheesy = Super Cheesys,\n"
    "slaninová = Slaninos, margarita / klasická = Margheritas, tuňáková = Tunas,\n"
    "havajská / hawaii = Hawais, chorizo = Chorizos, jalapeño / ostrá = Pepperoni Jalapeño,\n"
    "texas = Texas, kuřecí = Chicken, brusinkova = Brusinkys, borůvková = Borůvkys,\n"
    "farmářská = Farmaris, bbq / barbecue = Barbecues Chicken, mexická = Mexicanos,\n"
    "caprese = Caprisos, boom hot / pikantní = Boom Pizza Hot,\n"
    "boom / specialita = Boom Pizza, vegetářská = Vegetarians, pivo / pilsner = Pilsner Urquell.\n"
    "Pokud si nejsi jistý: 'Myslíte [název]?'\n\n"

    "PAMĚŤ OBJEDNÁVKY:\n"
    "Udržuj interní seznam všeho co zákazník objednal.\n"
    "Pokud zákazník řekne 'a ještě' — přidej a potvrď jednou větou.\n\n"

    "VRACEJÍCÍ SE ZÁKAZNÍK:\n"
    "Pokud má uloženou předchozí objednávku: 'Vítejte zpět, dáte si znovu to samé?'\n\n"

    "ČAS DORUČENÍ:\n"
    "Vyzvednutí: cca dvacet minut. Rozvoz: cca třicet minut.\n"
)


@app.route("/voice", methods=["POST"])
def voice():
    zakaznik = request.form.get("From", "")
    cislo = normalizuj_cislo(zakaznik)

    log("📞 PŘÍCHOZÍ HOVOR od " + cislo)

    voice_failures[cislo] = 0
    voice_silence[cislo] = 0

    posledni = posledni_objednavka.get(cislo, "") if not je_anonymni(zakaznik) else ""

    if je_anonymni(zakaznik):
        voice_conversations[cislo] = [
            {"role": "user", "content": "Telefonní číslo zákazníka není k dispozici. Až budeš sbírat kontakt, zeptej se na číslo (zákazník ho může vyťukat na klávesnici)."},
            {"role": "assistant", "content": "Rozumím."}
        ]
    elif posledni:
        voice_conversations[cislo] = [
            {"role": "user", "content": "Zákazník volá znovu. Poslední objednávka:\n" + posledni + "\nPozdrav ho jako vracejícího a zeptej se jestli chce to samé."},
            {"role": "assistant", "content": "Rozumím."}
        ]
    else:
        voice_conversations[cislo] = []

    resp = VoiceResponse()

    if not je_otevreno():
        resp.say(
            "Dobrý den, BOOM PIZZA. Momentálně jsme zavřeni. "
            "Otevíráme v deset hodin. Děkujeme.",
            voice=HLAS, language=JAZYK
        )
        return str(resp)

    gather = novy_gather()

    if posledni:
        gather.say(
            "Dobrý den, BOOM PIZZA. Vítejte zpět! Chcete objednat znovu to samé?",
            voice=HLAS, language=JAZYK
        )
    else:
        gather.say(
            "Dobrý den, BOOM PIZZA. Co si dáte?",
            voice=HLAS, language=JAZYK
        )

    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)


@app.route("/voice-no-input", methods=["POST"])
def voice_no_input():
    zakaznik = request.form.get("From", "")
    cislo = normalizuj_cislo(zakaznik)

    silence = voice_silence.get(cislo, 0) + 1
    voice_silence[cislo] = silence

    if silence >= 2:
        voice_silence[cislo] = 0
        return prepoj_na_obsluhu(zakaznik, "Zákazník neodpověděl")

    resp = VoiceResponse()
    gather = novy_gather()
    gather.say("Jste tam? Jak Vám mohu pomoci?", voice=HLAS, language=JAZYK)
    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)


@app.route("/voice-response", methods=["POST"])
def voice_response():
    zakaznik = request.form.get("From", "")
    cislo = normalizuj_cislo(zakaznik)

    # Zpracuj hlasový vstup
    speech_raw = request.form.get("SpeechResult", "").strip()
    # Zpracuj DTMF vstup (klávesnice) — používá se pro čísla popisné / telefon
    dtmf_raw = request.form.get("Digits", "").strip()

    # Priorita: pokud je DTMF, použij to jako text
    if dtmf_raw:
        zprava = "Číslo z klávesnice: " + dtmf_raw
        log("🔢 DTMF od " + cislo + ": " + dtmf_raw)
    else:
        zprava = normalizuj(speech_raw)
        log("🎤 ŘEČ od " + cislo + ": " + zprava[:100])

    voice_silence[cislo] = 0

    if detekuj_frustraci(zprava):
        posli_obsluze(
            "⚠️ NESPOKOJENÝ ZÁKAZNÍK — Telefon\n"
            "Tel: " + cislo + "\nŘekl: " + zprava
        )
        return prepoj_na_obsluhu(zakaznik, "Zákazník frustrovaný")

    if not zprava:
        failures = voice_failures.get(cislo, 0) + 1
        voice_failures[cislo] = failures

        if failures >= 2:
            voice_failures[cislo] = 0
            return prepoj_na_obsluhu(zakaznik, "Bot nerozuměl")

        resp = VoiceResponse()
        gather = novy_gather()
        gather.say("Nerozuměl jsem, zkuste znovu prosím.", voice=HLAS, language=JAZYK)
        resp.append(gather)
        resp.redirect("/voice-response")
        return str(resp)

    voice_failures[cislo] = 0

    history = voice_conversations.get(cislo, [])
    history.append({"role": "user", "content": zprava})

    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=VOICE_SYSTEM,
            messages=history
        )
        odpoved = response.content[0].text
        log("🤖 CLAUDE: " + odpoved[:150].replace("\n", " | "))
    except Exception as e:
        log("❌ Claude API SELHALO: " + str(e))
        resp = VoiceResponse()
        resp.say(
            "Omlouváme se, nastala technická chyba. Přepojuji Vás.",
            voice=HLAS, language=JAZYK
        )
        return prepoj_na_obsluhu(zakaznik, "Claude API selhalo")

    history.append({"role": "assistant", "content": odpoved})
    voice_conversations[cislo] = history[-30:]

    # ─── DOKONČENÁ OBJEDNÁVKA ───
    if "OBJEDNAVKA_HOTOVA" in odpoved:
        log("✅ OBJEDNÁVKA HOTOVA — posílám notifikaci")
        cast = odpoved.split("OBJEDNAVKA_HOTOVA")[-1].strip()
        if not je_anonymni(zakaznik):
            cast = cast.replace("AUTOMATICKY_Z_SYSTEMU", cislo)

        tel_pro_notifikaci = cislo if not je_anonymni(zakaznik) else "viz objednávka"

        # POSLI NOTIFIKACI — nezabije response ani když selže
        uspech = posli_obsluze(
            "🍕 NOVÁ OBJEDNÁVKA TELEFON — BOOM PIZZA\n"
            "Tel: " + tel_pro_notifikaci + "\n\n" + cast
        )

        if not uspech:
            log("⚠️ NOTIFIKACE NEPROŠLA — zkontroluj Twilio WhatsApp sandbox / kredit")

        posledni_objednavka[cislo] = cast
        odpoved_text = odpoved.split("OBJEDNAVKA_HOTOVA")[0].strip()

        resp = VoiceResponse()
        resp.say(odpoved_text, voice=HLAS, language=JAZYK)
        resp.pause(length=1)
        resp.hangup()  # explicitně ukonči hovor, aby Twilio vědělo
        return str(resp)

    elif "ZAKAZNIK_CHCE_ZAVOLAT" in odpoved:
        return prepoj_na_obsluhu(zakaznik, "Zákazník požádal o živého člověka")

    # ─── POKRAČUJ V KONVERZACI ───
    # Pokud se bot ptá na číslo popisné nebo telefonní číslo, povol DTMF
    odpoved_lower = odpoved.lower()
    potrebuje_dtmf = any(kw in odpoved_lower for kw in [
        "číslo popisné", "klávesnic", "vyťuk", "vaše číslo", "telefonní číslo"
    ])

    resp = VoiceResponse()
    gather = novy_gather(include_dtmf=potrebuje_dtmf)
    gather.say(odpoved, voice=HLAS, language=JAZYK)
    resp.append(gather)
    resp.redirect("/voice-no-input")
    return str(resp)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
