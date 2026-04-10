import re

# =============================================================
# SLANG.PY — Kompletní normalizace vstupu pro BOOM PIZZA bot
# Pokrývá: STT chyby, slang, přezdívky, adresy, množství,
#          velikosti, frustrace, způsob dopravy
# =============================================================


# ─────────────────────────────────────────────────────────────
# 1. STT ZKOMOLENINY — co Twilio špatně přepíše
# ─────────────────────────────────────────────────────────────
STT_OPRAVY = {
    # Boom Pizza
    "bum pica": "Boom Pizza",
    "bum pizza": "Boom Pizza",
    "bum picks": "Boom Pizza",
    "boom picks": "Boom Pizza",
    "boom pica": "Boom Pizza",
    "bompica": "Boom Pizza",
    "bom pizza": "Boom Pizza",
    "bum hot": "Boom Pizza Hot",
    "boom hat": "Boom Pizza Hot",
    "boom hot pizza": "Boom Pizza Hot",
    "bumhot": "Boom Pizza Hot",

    # Šunkás
    "šunkáš": "Šunkás",
    "šunkaš": "Šunkás",
    "šunkách": "Šunkás",
    "šunkas": "Šunkás",
    "sunkova": "Šunkás",
    "šunkovou": "Šunkás",
    "šunkavou": "Šunkás",
    "šunkov": "Šunkás",
    "sunkovu": "Šunkás",

    # Margheritas
    "margarita": "Margheritas",
    "margherita": "Margheritas",
    "margerita": "Margheritas",
    "margareta": "Margheritas",
    "marghérita": "Margheritas",
    "margarity": "Margheritas",

    # Pepperoni Jalapeño
    "pepperoni jalapeno": "Pepperoni Jalapeño",
    "pepperoni jalapeňo": "Pepperoni Jalapeño",
    "pepperoni chilli": "Pepperoni Jalapeño",
    "peperoni jalapeno": "Pepperoni Jalapeño",
    "jalapeňo pizza": "Pepperoni Jalapeño",

    # Brusinkys / Borůvkys
    "brusinkova": "Brusinkys",
    "borůvková": "Borůvkys",
    "boruvkova": "Borůvkys",
    "borůvka pizza": "Borůvkys",
    "brusinka pizza": "Brusinkys",

    # Farmaris
    "farmáři": "Farmaris",
    "farmárs": "Farmaris",

    # Mexicanos
    "meksiko": "Mexicanos",
    "mexicka": "Mexicanos",

    # Caprisos
    "kaprese": "Caprisos",
    "kapréso": "Caprisos",
    "capriso": "Caprisos",

    # Barbecues Chicken
    "barbikju": "Barbecues Chicken",
    "barbeque": "Barbecues Chicken",
    "bbq chicken": "Barbecues Chicken",
    "grilovanej kure": "Barbecues Chicken",

    # Hawais
    "hawaii pizza": "Hawais",
    "havajska": "Hawais",

    # Super Cheesys
    "super cizy": "Super Cheesys",
    "super cheesy": "Super Cheesys",
    "supercheesy": "Super Cheesys",

    # Chorizos
    "choriso": "Chorizos",
    "corizos": "Chorizos",

    # Ulice — STT chyby
    "nadrazni": "Čelakovského",
    "celakovskeho": "Čelakovského",
    "chelakovskeho": "Čelakovského",
    "machackova": "Máchackova",
    "palackeho": "Palackého",
    "nabrezi": "Nábřeží",
    "namesti": "Náměstí",
    "dlouha ulice": "Dlouhá",
    "kratka ulice": "Krátká",
}


# ─────────────────────────────────────────────────────────────
# 2. NÁZVY PIZZ — všechny možné přezdívky a variace
# ─────────────────────────────────────────────────────────────
SLANG_PIZZY = {
    # Šunkás
    r"\bšunkovou?\b": "Šunkás",
    r"\bse šunkou\b": "Šunkás",
    r"\bšunkový\b": "Šunkás",
    r"\bšunková\b": "Šunkás",
    r"\bse šunkem\b": "Šunkás",
    r"\bšunky\b": "Šunkás",

    # Pepperonis
    r"\bsalámovou?\b": "Pepperonis",
    r"\bse salámem\b": "Pepperonis",
    r"\bpepperoni\b": "Pepperonis",
    r"\bpeperoni\b": "Pepperonis",
    r"\bsalámová\b": "Pepperonis",
    r"\bsalami\b": "Pepperonis",

    # Super Cheesys
    r"\bsýrovou?\b": "Super Cheesys",
    r"\bčtyři sýry\b": "Super Cheesys",
    r"\bčtyřsýrovou?\b": "Super Cheesys",
    r"\bcheesy\b": "Super Cheesys",
    r"\bsýrová\b": "Super Cheesys",
    r"\bse čtyřmi sýry\b": "Super Cheesys",
    r"\bmix sýrů\b": "Super Cheesys",

    # Slaninos
    r"\bslaninovou?\b": "Slaninos",
    r"\bse slaninou\b": "Slaninos",
    r"\bslaninová\b": "Slaninos",

    # Margheritas
    r"\bklasickou?\b": "Margheritas",
    r"\bmargaritu\b": "Margheritas",
    r"\bmargarita\b": "Margheritas",
    r"\bklasická\b": "Margheritas",
    r"\bzákladní\b": "Margheritas",

    # Tunas
    r"\btuňákovou?\b": "Tunas",
    r"\bs tuňákem\b": "Tunas",
    r"\btuňáka\b": "Tunas",
    r"\btuňáková\b": "Tunas",
    r"\btunak\b": "Tunas",

    # Hawais
    r"\bhavajskou?\b": "Hawais",
    r"\bs ananasem\b": "Hawais",
    r"\bhawajskou?\b": "Hawais",
    r"\bhavajská\b": "Hawais",
    r"\bhawaii\b": "Hawais",
    r"\bananasová\b": "Hawais",

    # Chicken
    r"\bkuřecí\b": "Chicken",
    r"\bkuřecou\b": "Chicken",
    r"\bs kuřecím\b": "Chicken",
    r"\bkurecí\b": "Chicken",

    # Texas
    r"\btexaskou?\b": "Texas",
    r"\btexaská\b": "Texas",
    r"\btexas\b": "Texas",

    # Farmaris
    r"\bfarmářskou?\b": "Farmaris",
    r"\bsedláckou?\b": "Farmaris",
    r"\bfarmářská\b": "Farmaris",
    r"\bsedlácká\b": "Farmaris",

    # Barbecues Chicken
    r"\bbbq\b": "Barbecues Chicken",
    r"\bbarbecue\b": "Barbecues Chicken",
    r"\bgrilovanou?\b": "Barbecues Chicken",
    r"\bgrilovaná\b": "Barbecues Chicken",

    # Mexicanos
    r"\bmexickou?\b": "Mexicanos",
    r"\bz mexika\b": "Mexicanos",
    r"\bmexická\b": "Mexicanos",
    r"\bmexiko\b": "Mexicanos",

    # Caprisos
    r"\bcaprese\b": "Caprisos",
    r"\bkaprese\b": "Caprisos",

    # Chorizos
    r"\bchorizo\b": "Chorizos",
    r"\bchoriza\b": "Chorizos",
    r"\bs chorizem\b": "Chorizos",

    # Boom Pizza Hot
    r"\bostrá pizza\b": "Boom Pizza Hot",
    r"\bpikantní pizza\b": "Boom Pizza Hot",
    r"\bpálivá\b": "Boom Pizza Hot",
    r"\bchilli pizza\b": "Boom Pizza Hot",

    # Boom Pizza (klasická)
    r"\bspecialitu\b": "Boom Pizza",
    r"\bspeciální pizza\b": "Boom Pizza",

    # Vegetarians
    r"\bvegetářskou?\b": "Vegetarians",
    r"\bbez masa\b": "Vegetarians",
    r"\bzeleninovou?\b": "Vegetarians",
    r"\bvegetariánskou?\b": "Vegetarians",

    # Pepperoni Jalapeño
    r"\bjalapeño\b": "Pepperoni Jalapeño",
    r"\bjalapeno\b": "Pepperoni Jalapeño",
    r"\bostrá salami\b": "Pepperoni Jalapeño",

    # Brusinkys / Borůvkys
    r"\bbrusinkovou?\b": "Brusinkys",
    r"\bborůvkovou?\b": "Borůvkys",
    r"\bs brusinkami\b": "Brusinkys",
    r"\bs borůvkami\b": "Borůvkys",

    # Pilsner Urquell
    r"\bpivo\b": "Pilsner Urquell",
    r"\bpilsner\b": "Pilsner Urquell",
    r"\burquell\b": "Pilsner Urquell",
    r"\bplzeňské\b": "Pilsner Urquell",
    r"\bplzeňák\b": "Pilsner Urquell",
}


# ─────────────────────────────────────────────────────────────
# 3. VELIKOSTI
# ─────────────────────────────────────────────────────────────
SLANG_VELIKOST = {
    r"\bvelkou\b": "42cm",
    r"\bvelká\b": "42cm",
    r"\bvětší\b": "42cm",
    r"\bčtyřicet dva\b": "42cm",
    r"\bčtyřicítku\b": "42cm",
    r"\btu větší\b": "42cm",
    r"\btu velkou\b": "42cm",
    r"\bfamily\b": "42cm",
    r"\bmalou\b": "32cm",
    r"\bmalá\b": "32cm",
    r"\bmenší\b": "32cm",
    r"\btřicet dva\b": "32cm",
    r"\btu menší\b": "32cm",
    r"\btu malou\b": "32cm",
    r"\bstandard\b": "32cm",
}


# ─────────────────────────────────────────────────────────────
# 4. MNOŽSTVÍ
# ─────────────────────────────────────────────────────────────
SLANG_MNOZSTVI = {
    r"\bjeden kus\b": "1x",
    r"\bjednu\b": "1x",
    r"\bjeden\b": "1x",
    r"\bjedna\b": "1x",
    r"\bdva kusy\b": "2x",
    r"\bdvě\b": "2x",
    r"\bdva\b": "2x",
    r"\bdvojku\b": "2x",
    r"\bpárek\b": "2x",
    r"\bdvakrát\b": "2x",
    r"\btři kusy\b": "3x",
    r"\btři\b": "3x",
    r"\btřikrát\b": "3x",
    r"\bčtyři kusy\b": "4x",
    r"\bčtyři\b": "4x",
    r"\bpět kusů\b": "5x",
    r"\bpět\b": "5x",
    r"\bšest kusů\b": "6x",
    r"\bšest\b": "6x",
}


# ─────────────────────────────────────────────────────────────
# 5. AKCE — hovorové výrazy pro objednávku
# ─────────────────────────────────────────────────────────────
SLANG_AKCE = {
    r"\bdej mi\b": "chci",
    r"\bhoďte mi\b": "chci",
    r"\bhoď mi\b": "chci",
    r"\bdejte mi\b": "chci",
    r"\bpřineste\b": "chci",
    r"\bpošlete\b": "chci",
    r"\bchci si dát\b": "chci",
    r"\bdam si\b": "chci",
    r"\bdám si\b": "chci",
    r"\bobjednám si\b": "chci",
    r"\bobjednávám\b": "chci",
    r"\bchtěl bych\b": "chci",
    r"\bchtěla bych\b": "chci",
    r"\bráda bych\b": "chci",
    r"\brád bych\b": "chci",
    r"\bdáme si\b": "chceme",
    r"\bobjednáváme\b": "chceme",
}


# ─────────────────────────────────────────────────────────────
# 6. DOPRAVA
# ─────────────────────────────────────────────────────────────
SLANG_DOPRAVA = {
    r"\bpřivezte\b": "rozvoz",
    r"\bdomů\b": "rozvoz",
    r"\bna adresu\b": "rozvoz",
    r"\bdoneste\b": "rozvoz",
    r"\bdoručte\b": "rozvoz",
    r"\bk nám\b": "rozvoz",
    r"\bvyzvednu\b": "osobní vyzvednutí",
    r"\bpřijdu si\b": "osobní vyzvednutí",
    r"\bu vás\b": "osobní vyzvednutí",
    r"\bna místě\b": "osobní vyzvednutí",
    r"\bs sebou\b": "osobní vyzvednutí",
    r"\bsám si\b": "osobní vyzvednutí",
    r"\bpřijdu\b": "osobní vyzvednutí",
    r"\bzajdu\b": "osobní vyzvednutí",
}


# ─────────────────────────────────────────────────────────────
# 7. OKRAJE
# ─────────────────────────────────────────────────────────────
SLANG_OKRAJE = {
    r"\bsýrový okraj\b": "mozzarellový okraj",
    r"\bchedar okraj\b": "čedarový okraj",
    r"\bcheddar okraj\b": "čedarový okraj",
    r"\bbez okraje\b": "bez okraje",
    r"\bbez okrajů\b": "bez okraje",
    r"\bnechci okraj\b": "bez okraje",
}


# ─────────────────────────────────────────────────────────────
# 8. ČAS
# ─────────────────────────────────────────────────────────────
SLANG_CAS = {
    r"\bco nejdřív\b": "co nejdříve",
    r"\bco nejrychleji\b": "co nejdříve",
    r"\bhned\b": "co nejdříve",
    r"\bteď\b": "co nejdříve",
    r"\bihned\b": "co nejdříve",
    r"\bco nejdrive\b": "co nejdříve",
    r"\brychlé\b": "co nejdříve",
}


# ─────────────────────────────────────────────────────────────
# 9. FRUSTRACE
# ─────────────────────────────────────────────────────────────
FRUSTRACE_SLOVA = [
    "do prdele", "do háje", "kurva", "hovno", "blbost", "idiot", "idioti",
    "debil", "debilní", "pitomý", "pitomec", "blbý", "blbej", "hloupý",
    "nefunguje", "nerozumíš", "nechápeš", "blbý bot", "hrozný", "k ničemu",
    "špatně", "neschopný", "hluchý",
    "živého", "živýho", "člověka", "operátora", "obsluhu", "šéfa",
    "někoho živého", "normálního člověka",
    "přepoj", "přepojte", "přepojit",
    "znovu", "ještě jednou", "opět", "pořád", "stále", "furt",
    "zase", "podruhé", "potřetí", "opakuji",
    "říkal jsem", "říkala jsem", "už jsem říkal",
    "zavěsím", "zavěšuji", "končím",
    "půjdu jinam", "zavolám jinam", "objednám jinde",
    "nechci", "nechte mě",
]


def detekuj_frustraci(text: str) -> bool:
    """Vrátí True pokud zákazník vykazuje frustraci."""
    t = text.lower()
    return any(slovo in t for slovo in FRUSTRACE_SLOVA)


# ─────────────────────────────────────────────────────────────
# HLAVNÍ FUNKCE
# ─────────────────────────────────────────────────────────────
def normalizuj(text: str) -> str:
    """
    Normalizuje vstup od zákazníka před odesláním do Claude.
    Volej na SpeechResult (voice) i Body (WhatsApp).
    """
    if not text:
        return text

    t = text.lower()

    # 1. STT zkomoleniny — pevné náhrady
    for chyba, oprava in STT_OPRAVY.items():
        t = t.replace(chyba.lower(), oprava.lower())

    # 2. Regex nahrazení
    for vzor, nahrada in {
        **SLANG_AKCE,
        **SLANG_DOPRAVA,
        **SLANG_CAS,
        **SLANG_MNOZSTVI,
        **SLANG_VELIKOST,
        **SLANG_OKRAJE,
        **SLANG_PIZZY,
    }.items():
        t = re.sub(vzor, nahrada, t, flags=re.IGNORECASE)

    # 3. Zachovej velké písmeno na začátku
    if text and text[0].isupper() and t:
        t = t[0].upper() + t[1:]

    return t    "šunkovou": "Šunkás",

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

    # 1. Opravy ulic
    for chyba, oprava in STT_ULICE.items():
        t = t.replace(chyba.lower(), oprava.lower())

    # 2. Opravy STT zkomolenin
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
