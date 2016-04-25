
"""
    helper, allows to replace a single bracketed 'card' with multiple cards
"""
replacements = {
    "dreamcards" : ["dream", "emeralddrake", "laughingsister", "nightmare", "yseraawakens"],
    "beastcompanions" : ["huffer", "leokk", "misha"],
    "powerfulartifacts" : ["lanternofpower", "mirrorofdoom", "timepieceofhorror"],
    "powerchords" : ["iammurloc", "powerofthehorde", "roguesdoit"],
    "spareparts" : ["armorplating", "emergencycoolant", "finickycloakfield", "reversingswitch", "rustyhorn", "timerewinder", "whirlingblades"],
    "toxins" : ["bloodthistletoxin", "briarthorntoxin", "fadeleaftoxin", "firebloomtoxin", "kingsbloodtoxin"]
}

CMDS = replacements.keys()


def _replaceSingle(cards, cmd):
    for i, card in enumerate(cards):
        if card == cmd:
            cards[i:i+1] = replacements[cmd]
            return

def replace(cards):
    for key in replacements:
        _replaceSingle(cards, key)
    if len(cards) > 7:
        return cards[:7]
    return cards