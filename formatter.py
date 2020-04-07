
import logging as log
import os
import urllib

import credentials


atk_dur_template = "{atk}/{dur}"
subtype_template = " {subType}"
desc_template = " | {desc}"
extDesc_template = "[{text}]  \n"
card_template = ("* **[{name}]({cdn})** {class} {type} {rarity} {set} {std}"
                    "^[HP](https://www.hearthpwn.com/cards/{hpwn}), "
                    "^[TD](https://www.hearthstonetopdecks.com/cards/{head}/), "
                    "^[W](https://hearthstone.gamepedia.com/{wiki})  \n"
                "{cost}/{atk_dur}{subtype}{desc}  \n{extDesc}")
signature = ("\n^(Call/)^[PM](https://www.reddit.com/message/compose/?to={bot})"
            " ^( me with up to 7 [[cardname]]. )"
            "^[About.](https://www.reddit.com/message/compose/"
            "?to={bot}&message=Tell%20me%20more%20[[info]]&subject=hi)") \
            .format(bot=credentials.username)

duplicate_header_templ = ("You've posted a comment reply in [{title}]({url}) "
                            "containing cards I already explained. "
                            "To reduce duplicates, your cards are here:\n\n")

# Standard legal icon
# 2020 fire because phoenix
STD_ICON = '\U0001F525 '
# unreleased sleep
NEXT_STD_ICON = '\U0001F4A4 '


def createCardText(card, constants):
    """ formats a single card to text """
    cardSet = card['set']
    cardSetData = constants.sets[constants.setIds[cardSet]]
    cardSetCode = cardSetData.get('code')

    cost = card['cost']
    atk = card['atk']
    dur = card['hp']
    if cost is None: cost = '-'
    if atk is None: atk = '-'
    if dur is None: dur = '-'
    atk_dur = atk_dur_template.format(atk=atk, dur=dur)

    cardDesc = card['desc']
    extDesc = card.get('extDesc', '')
    if extDesc:
        extDesc = ''.join(extDesc_template.format(text=desc) for desc in extDesc)

    local_card = {
        'name' : card['name'],
        'type' : card['type'],
        'class' : card['class'],
        'rarity' : card['rarity'],
        'set' : cardSetCode or cardSet,
        'cost' : cost,
        'desc' : desc_template.format(desc=cardDesc) if cardDesc else '',
        'extDesc': extDesc,
        'hpwn' : card['hpwn'],
        'head' : card['head'],
        'wiki' : urllib.parse.quote(card['name'].replace(' ', '_')),
        'cdn' : card['cdn'],
        'atk_dur' : atk_dur,

        'subtype' : subtype_template.format(subType=card['subType']) \
                if card['subType'] else '',

        'std' : STD_ICON if cardSetData.get('std') else \
                NEXT_STD_ICON if cardSetData.get('unreleased') else ' '
    }

    return card_template.format(**local_card)


def createAnswer(cardDB, cards):
    """gets card formatted card text and signature and joins them"""
    comment_text = ''

    for card in cards:
        log.debug('adding card to text: %s', card)
        comment_text += cardDB[card]

    if comment_text:
        comment_text += signature

    return comment_text


def createDuplicateMsg(title, url):
    """message header for duplicate comment requests"""
    return duplicate_header_templ.format(title=title, url=url)


def loadInfoTempl(specials=[], alts=[], tokens=[], *, infoMsgTmpl='data/info_msg.templ'):
    """ reads and prepares [[info]] template,
    {user} will remain for later formatting
    """

    if not os.path.isfile(infoMsgTmpl):
        return ''

    rawTemplate = ''
    with open(infoMsgTmpl, 'r', encoding="utf8") as file:
        rawTemplate = file.read()

    # sets to list and sort them all
    specials = list(specials)
    specials.sort()
    alts = list(alts)
    alts.sort()
    tokens = list(tokens)
    tokens.sort()
    # join lists together
    comma = ', '
    specialText = comma.join(specials)
    altsText = comma.join(alts)
    tokensText = comma.join(tokens)

    return rawTemplate.format(user='{user}',
                                alts=altsText,
                                tokens=tokensText,
                                special=specialText)