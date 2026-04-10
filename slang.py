import re

# ─────────────────────────────────────────────
# OPRAVY STT — časté zkomoleniny speech-to-text
# ─────────────────────────────────────────────
STT_OPRAVY = {
    # Boom Pizza
    "bum pica": "Boom Pizza",
    "bum pizza": "Boom Pizza",
    "bompica": "Boom Pizza",
    "bum picks": "Boom Pizza",
    "boom picks": "Boom Pizza",
    "boom pica": "Boom Pizza",
    "bum hot": "Boom Pizza Hot",
    "boom hat": "Boom Pizza Hot",

    # Šunkás
    "šunkáš": "Šunkás",
    "šunkaš": "Šunkás",
    "šunkách": "Šunkás",
    "šunkas": "Šunkás",
    "sunkova": "Šunkás",
    "šunkovou": "Šunkás",

    # Margheritas
    "margarita": "Margheritas",
    "margherita": "Margheritas",
    "margerita": "Margheritas",
    "margareta": "Margheritas",

    # Pepperoni Jalapeño
    "pepperoni jalapeno": "Pepperoni Jalapeño",
    "pepperoni jalapeňo": "Pepperoni Jalapeño",
    "pepperoni chilli": "Pepperoni Jalapeño",

    # Brusinkys/Borůvkys
    "brusinkova": "Brusinkys",
    "borůvková": "Borůvkys",
    "boruvkova": "Borůvkys",

    # Ostatní časté STT chyby
    "farmáři": "Farmaris",
    "farmárs": "Farmaris",
    "meksiko": "Mexicanos",
    "mexická": "Mexicanos",
    "kaprese": "Caprisos",
    "kapréso": "Caprisos",
    "barbikju": "Barbecues Chicken",
    "barbeque": "Barbecues Chicken",
}

# ─────────────────────────────────────────────
# SLANG — hovorové výrazy zákazníků
# ─────────────────────────────────────────────
SLANG_PIZZY = {
    # Šunkás
    r"\bšunkovou?\b": "Šunkás",
    r"\bse šunkou\b": "Šunkás",
    r"\bšunkový\b": "Šunkás",

    # Pepperonis
    r"\bsalámovou?\b": "Pepperonis",
    r"\bse salámem\b": "Pepperonis",
    r"\bpepperoni\b": "Pepperonis",
    r"\bpeperoni\b": "Pepperonis",

    # Super Cheesys
    r"\bsýrovou?\b": "Super Cheesys",
    r"\bčtyři sýry\b": "Super Cheesys",
    r"\bčtyřsýrovou?\b": "Super Cheesys",
    r"\bcheesy\b": "Super Cheesys",

    # Slaninos
    r"\bslaninovou?\b": "Slaninos",
    r"\bse slaninou\b": "Slaninos",

    # Margheritas
    r"\bklasickou?\b": "Margheritas",
    r"\bmargaritu\b": "Margheritas",
    r"\bmargarita\b": "Margheritas",

    # Tunas
    r"\btuňákovou?\b": "Tunas",
    r"\bs tuňákem\b": "Tunas",
    r"\btuňáka\b": "Tunas",

    # Hawais
    r"\bhavajskou?\b": "Hawais",
    r"\bs ananasem\b": "Hawais",
    r"\bhawajskou?\b": "Hawais",

    # Chicken
    r"\bkuřecí\b": "Chicken",
    r"\bkuřecou\b": "Chicken",
    r"\bs kuřecím\b": "Chicken",

    # Texas
    r"\btexaskou?\b": "Texas",

    # Farmaris
    r"\bfarmářskou?\b": "Farmaris",
    r"\bsedláckou?\b": "Farmaris",

    # Barbecues Chicken
    r"\bbbq\b": "Barbecues Chicken",
    r"\bbarbecue\b": "Barbecues Chicken",
    r"\bgrilovanou?\b": "Barbecues Chicken",

    # Mexicanos
    r"\bmexickou?\b": "Mexicanos",
    r"\bz mexika\b": "Mexicanos",

    # Caprisos
    r"\bcaprese\b": "Caprisos",

    # Boom Pizza Hot
    r"\bostrá pizza\b": "Boom Pizza Hot",
    r"\bpikantní\b": "Boom Pizza Hot",
    r"\bostra\b": "Boom Pizza Hot",

    # Vegetarians
    r"\bvegetářskou?\b": "Vegetarians",
    r"\bbez masa\b": "Vegetarians",
    r"\bzeleninovou?\b": "Vegetarians",
}

SLANG_VELIKOST = {
    r"\bvelkou\b": "42cm",
    r"\bvelká\b": "42cm",
    r"\bvětší\b": "42cm",
    r"\bčtyřicet dva\b": "42cm",
    r"\bčtyřicetidva\b": "42cm",
    r"\bvelkou\b": "42cm",
    r"\bmalou\b": "32cm",
    r"\bmalá\b": "32cm",
    r"\bmenší\b": "32cm",
    r"\btřicet dva\b": "32cm",
    r"\btřicetidva\b": "32cm",
}

SLANG_MNOZSTVI = {
    r"\bjeden kus\b": "1x",
    r"\bjednu\b": "1x",
    r"\bjeden\b": "1x",
    r"\bdva kusy\b": "2x",
    r"\bdvě\b": "2x",
    r"\bdva\b": "2x",
    r"\btři kusy\b": "3x",
    r"\btři\b": "3x",
    r"\bčtyři kusy\b": "4x",
    r"\bčtyři\b": "4x",
    r"\bpět kusů\b": "5x",
    r"\bpět\b": "5x",
}

SLANG_AKCE = {
    r"\bdej mi\b": "chci",
    r"\bhoďte mi\b": "chci",
    r"\bhoď mi\b": "chci",
    r"\bdejte mi\b": "chci",
    r"\bpřineťe\b": "chci",
    r"\bpošlete\b": "chci",
    r"\bchci si dát\b": "chci",
    r"\bdam si\b": "chci",
    r"\bdám si\b": "chci",
    r"\bobjednám si\b": "chci",
    r"\bobjednávám\b": "chci",
}

SLANG_DOPRAVA = {
    r"\bpřivezte\b": "rozvoz",
    r"\bpřivézt\b": "rozvoz",
    r"\bdomů\b": "rozvoz",
    r"\bna adresu\b": "rozvoz",
    r"\brozvezte\b": "rozvoz",
    r"\bvyzvednu\b": "osobní vyzvednutí",
    r"\bpřijdu si\b": "osobní vyzvednutí",
    r"\bu vás\b": "osobní vyzvednutí",
    r"\bna místě\b": "osobní vyzvednutí",
    r"\bs sebou\b": "osobní vyzvednutí",
}


def normalizuj(text: str) -> str:
    """
    Hlavní funkce — normalizuje vstup od zákazníka před odesláním do Claude.
    Volej ji na SpeechResult (voice) i Body (WhatsApp).
    """
    if not text:
        return text

    t = text.lower()

    # 1. Opravy STT zkomolenin
    for chyba, oprava in STT_OPRAVY.items():
        t = t.replace(chyba.lower(), oprava.lower())

    # 2. Slang → standardní výrazy
    for vzor, nahrada in {
        **SLANG_AKCE,
        **SLANG_DOPRAVA,
        **SLANG_MNOZSTVI,
        **SLANG_VELIKOST,
        **SLANG_PIZZY,
    }.items():
        t = re.sub(vzor, nahrada, t, flags=re.IGNORECASE)

    # 3. Zachovej původní velikost písmen pro první písmeno věty
    if text and text[0].isupper() and t:
        t = t[0].upper() + t[1:]

    return t
