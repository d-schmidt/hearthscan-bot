
import io
import itertools
import json
import logging as log
import re
import string
import time
import urllib.parse
import os

import praw

import alt_cards as ac
import card_constants as cc
import credentials


reauth_sec = 60*20 # 20 min
# templates
atk_dur_template = " {atk}/{dur}"
subtype_template = " {subType}"
desc_template = " - {desc}"
card_template = ("* **[{name}]({cdn})** {type} {class} {rarity} {set} {std}| "
                    "[HP](http://www.hearthpwn.com/cards/{hpwn}), "
                    "[HH](http://www.hearthhead.com/cards/{head}), "
                    "[Wiki](http://hearthstone.gamepedia.com/{wiki})  \n"
                "{cost} Mana{atk_dur}{subtype}{desc}  \n")
signature = ("\n^(Call/)^[PM](https://www.reddit.com/message/compose/?to={})"
            " ^( me with up to 7 [[cardname]]. For source/help PM [[info]])").format(credentials.username)

# files
TEMP_FILE_NAME = 'tempinfo.json'
TOKENS_JSON = 'tokens.json'
CARDS_JSON = 'cards.json'
INFO_MSG_TMPL = 'info_msg.templ'

# global used to detect temp file changes
start_filetime = 0


def initReddit(refresh_token = credentials.refresh_token):
    """ get the reddit api token, see credentials.py for more info """

    log.debug("initReddit() creating reddit adapter")
    r = praw.Reddit(user_agent=credentials.user_agent)

    log.debug("initReddit() preparing reddit adapter")
    r.set_oauth_app_info(client_id=credentials.client_id,
                         client_secret=credentials.client_secret,
                         redirect_uri=credentials.redirect_uri)

    log.debug("initReddit() trying to authenticate with refresh token: %s", refresh_token)
    r.refresh_token = refresh_token
    r.refresh_access_information()

    if r.user.name != credentials.username:
        raise Exception('credentials and session usernames do not match')

    log.debug("initReddit() login success: %s", r.user.name)
    next_auth_time = int(time.time()) + reauth_sec
    return r, next_auth_time


def refreshReddit(r):
    """ keep the reddit api token alive """
    try:
        log.debug("refreshReddit() going to refresh with token %s", r.refresh_token)
        r.refresh_access_information()
        next_auth_time = int(time.time()) + reauth_sec
    except praw.errors.Forbidden as fe:
        # refreshing sometimes fails, our token got lost somewhere in the clouds
        log.error("refreshReddit() got forbidden, creating new connection with backup token")
        r, next_auth_time = initReddit(credentials.backup_refresh_token)
        log.info("refreshReddit() new connection seems to work")
        try:
            # this is just information, there is no need to act
            # the tokens are reusable multiple times and for months
            r.send_message(credentials.admin_username,
                            'backup token used',
                            'new init after failed refresh')
        except:
            pass
    return r, next_auth_time


def cleanName(name):
    """ we ignore all special characters, numbers, whitespace, case """
    return ''.join(char for char in name.lower() if char in string.ascii_lowercase)


def removeQuotes(text):
    """ removes quote blocks, the cards in them are already answered """
    lines = []
    for l in io.StringIO(text):
        l = l.strip()
        if l and l[0] != '>':
            lines.append(l)
    return ' '.join(lines)


def getTextForCards(card_db, cards):
    """ gets card formatted card text and signature and joins them """
    comment_text = ''
    for card in cards:
        if card in card_db:
            log.debug('adding card to text: %s', card)
            comment_text += card_db[card]

    if comment_text:
        comment_text += signature
    return comment_text


def getCardsFromComment(text, spell_check):
    """ look for [[cardname]] in text and collect them securely """
    cards = []
    if len(text) < 6:
        return cards
    open_bracket = False
    card = ''

    # could be regex, but I rather not parse everything evil users are sending
    for i in range(1, len(text)):
        c = text[i]
        if open_bracket and c != ']':
            card += c
        if c == '[' and text[i-1] == '[':
            open_bracket = True
        if c == ']' and open_bracket:
            if len(card) > 0:
                log.debug("adding a card: %s", card)
                cleanCard = cleanName(card)
                if cleanCard:
                    log.debug("cleaned card name: %s", cleanCard)
                    # slight spelling error?
                    checkedCard = spell_check.correct(cleanCard)
                    if cleanCard != checkedCard:
                        log.info("spelling fixed: %s -> %s", cleanCard, checkedCard)
                    # is alternative name?
                    checkedCard = ac.translations.get(checkedCard, checkedCard)
                    # add cardname
                    if checkedCard not in cards:
                        cards.append(checkedCard)
                    else:
                        log.info("duplicate card: %s", card)

            card = ''
            open_bracket = False
            if len(cards) >= 7:
                break

        if len(card) > 30:
            card = ''
            open_bracket = False

    return cards


def loadCardDB():
    """ load and format cards from json files into dict """
    with open(CARDS_JSON, 'r') as infofile:
        info = json.load(infofile)
    with open(TOKENS_JSON, 'r') as infofile:
        tokens = json.load(infofile)

    # this third file allows to add new cards without restarting the bot
    # just add them to the tempfile.json
    temporary = {}
    if os.path.isfile(TEMP_FILE_NAME):
        # TODO move to db object instance
        global start_filetime
        start_filetime = os.path.getmtime(TEMP_FILE_NAME)

        with open(TEMP_FILE_NAME, 'r') as infofile:
            temporary = json.load(infofile)

    return _createCardDB(itertools.chain(info.items(), tokens.items(), temporary.items()))


def _createCardDB(cards):
    """ formats all the cards to text """
    # TODO cardDB should be an object by now instead of a dict
    card_db = {}
    # fill templates
    for name, card in cards:
        clean_name = cleanName(name)
        if clean_name in card_db:
            log.error("duplicate name, it's already in the db: %s", clean_name)
            raise Exception("duplicate card name")

        card_db[clean_name] = _createTextForCard(card)

    return card_db


def _createTextForCard(card):
    """ formats a single card to text """
    cardSet = card['set']
    cardSetData = cc.setdata[cc.setids[cardSet]]
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
        'subtype' : subtype_template.format(subType=card['subType']) if card['subType'] else '',
        'std' : '\U0001F419 ' if cardSetData.get('std') else ''
    }

    return card_template.format(**local_card)


def updateCardDB(card_db):
    """ check if tempfile modify date has changed and reload cards from it """
    # TODO cardDB should be an object by now instead of a dict

    if os.path.isfile(TEMP_FILE_NAME):
        current_filetime = os.path.getmtime(TEMP_FILE_NAME)
        # TODO move to db object instance
        global start_filetime

        if current_filetime != start_filetime:
            log.debug("updateCardDB() reloading temporary cards")
            start_filetime = current_filetime
            try:
                with open(TEMP_FILE_NAME, 'r') as infofile:
                    for name, card in json.load(infofile).items():
                        card_db[cleanName(name)] = _createTextForCard(card)
            except Exception as e:
                log.debug("updateCardDB() couldn't parse file: %s", e)
    return card_db


def loadInfoTempl(specials=[], alts=[], tokens=[]):
    """ reads and prepares [[info]] template, {user} will remain for later formatting"""

    if not os.path.isfile(INFO_MSG_TMPL):
        return ''

    if not tokens:
        # redundant file load but everything else if meh
        with open(TOKENS_JSON, 'r') as infofile:
            tokens = [cleanName(token) for token in json.load(infofile).keys()]

    rawTemplate = ''
    with open(INFO_MSG_TMPL, 'r', encoding="utf8") as infofile:
        rawTemplate = infofile.read()

    # key sets to list and sort them all
    alts = alts if alts else list(ac.translations.keys())
    alts.sort()
    tokens.sort()
    specials = list(specials)
    specials.sort()
    # join lists together
    joinString = ', '
    altsText = joinString.join(alts)
    tokensText = joinString.join(tokens)
    specialText = joinString.join(specials)

    return rawTemplate.format(user='{user}',
                                alts=altsText,
                                tokens=tokensText,
                                special=specialText)
