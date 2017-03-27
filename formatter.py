
import logging as log
import os
import urllib

import credentials


atk_dur_template = " {atk}/{dur}"
subtype_template = " {subType}"
desc_template = " - {desc}"
card_template = ("* **[{name}]({cdn})** {class} {type} {rarity} {set} {std}"
                    "^[HP](http://www.hearthpwn.com/cards/{hpwn}), "
                    "^[HH](http://www.hearthhead.com/cards/{head}), "
                    "^[Wiki](http://hearthstone.gamepedia.com/{wiki})  \n"
                "{cost} Mana{atk_dur}{subtype}{desc}  \n")
signature = ("\n^(Call/)^[PM](https://www.reddit.com/message/compose/?to={})"
            " ^( me with up to 7 [[cardname]]. For more PM [[info]])") \
            .format(credentials.username)

duplicate_header_templ = ("You've posted a comment reply in [{title}]({url}) "
                            "containing cards I already explained. "
                            "To reduce duplicated comments, :\n\n")


INFO_MSG_TMPL = 'info_msg.templ'

# Standard legal icon
# 2017 elephant because mammoth
STD_ICON = '\U0001F418 '
NEXT_STD_ICON = STD_ICON


def createCardText(card, constants):
    """ formats a single card to text """
    cardSet = card['set']
    cardSetData = constants.sets[constants.setIds[cardSet]]
    cardSetCode = cardSetData.get('code')
    atk_dur = ''
    if card['atk'] is not None and card['hp'] is not None:
        atk_dur = atk_dur_template.format(atk=card['atk'], dur=card['hp'])

    cardDesc = card['desc']

    local_card = {
        'name' : card['name'],
        'type' : card['type'],
        'class' : card['class'],
        'rarity' : card['rarity'],
        'set' : cardSetCode if cardSetCode else cardSet,
        'cost' : card['cost'],
        'desc' : desc_template.format(desc=cardDesc) if cardDesc else '',
        'hpwn' : card['hpwn'],
        'head' : card['head'],
        'wiki' : urllib.parse.quote(card['name'].replace(' ', '_')),
        'cdn' : card['cdn'],
        'atk_dur' : atk_dur,

        'subtype' : subtype_template.format(subType=card['subType']) \
                if card['subType'] else '',

        'std' : STD_ICON if cardSetData.get('std') else \
                NEXT_STD_ICON if cardSetData.get('unreleased') else '| '
    }

    return card_template.format(**local_card)


def createAnswer(cardDB, cards):
    """gets card formatted card text and signature and joins them"""
    comment_text = ''

    for card in cards:
        if card in cardDB:
            log.debug('adding card to text: %s', card)
            comment_text += cardDB[card]

    if comment_text:
        comment_text += signature
    return comment_text


def createDuplicateMsg(title, url):
    """message header for duplicate comment requests"""
    return duplicate_header_templ.format(title=title, url=url)


def loadInfoTempl(specials=[], alts=[], tokens=[]):
    """ reads and prepares [[info]] template,
    {user} will remain for later formatting
    """

    if not os.path.isfile(INFO_MSG_TMPL):
        return ''

    rawTemplate = ''
    with open(INFO_MSG_TMPL, 'r', encoding="utf8") as file:
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