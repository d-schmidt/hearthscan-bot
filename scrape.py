#!/usr/bin/env python3

import json
import logging as log
import os
import os.path
import re
import sys
import time
from multiprocessing.dummy import Pool

from lxml.html import fromstring
import requests

from constants import Constants


"""
Please note:
Scraping somebodies html website without asking is not nice.
Please be a nice user and ask before scraping when if it is not an api.
This is especially true when using images.
"""


# scrape main url
setUrlTempl = ('https://www.hearthpwn.com/cards?'
               'filter-name={}&filter-premium={}&filter-type={}&filter-set={}'
               '&filter-unreleased=1&display=2')
# hearthstonejson set id to card_constant set id
jsonToCCSet = {
    'EXPERT1': '02',
    'NAXX': '05',
    'GVG': '06',
    'BRM': '07',
    'TGT': '08',
    'LOE': '09',
    'OG': '10',
    'KARA': '11',
    'GANGS': '12',
    'UNGORO': '13',
    'ICECROWN': '15',
    'LOOTAPALOOZA': '16',
    'GILNEAS': '17',
    'BOOMSDAY': '18',
    'TROLL': '19',
    'DALARAN': '20',
    'ULDUM': '21',
    'DRAGONS': '22',
    'YEAR_OF_THE_DRAGON': '23',
    'DEMON_HUNTER_INITIATE': '24',
    'BLACK_TEMPLE': '25',
    'SCHOLOMANCE': '26',
    'DARKMOON_FAIRE': '27',
    'TB': '28',
    'CORE': '29',
    'THE_BARRENS': '30',
    'VANILLA': '31',
    'TAVERNS_OF_TIME': '32', # arena event tokens
    'LEGACY': '33',
    #'BATTLEGROUNDS': '34'
    'STORMWIND': '35',
    'ALTERAC_VALLEY': '36',
    'THE_SUNKEN_CITY': '37',
    'REVENDRETH': '38',
    'RETURN_OF_THE_LICH_KING': '39',
    'BATTLE_OF_THE_BANDS': '40',
    'PATH_OF_ARTHAS': '41'
}
# card_constant set ids to hs internal set ids
setids = {
    '02' : 3,
    '05' : 100,
    '06' : 101,
    '07' : 102,
    '08' : 103,
    '09' : 104,
    '10' : 105,
    '11' : 106,
    '12' : 107,
    '13' : 108,
    '15' : 109,
    '16' : 110,
    '17' : 111,
    '18' : 113,
    '19' : 114,
    '20' : 115,
    '21' : 116,
    '22' : 1200,
    '23' : 1300,
    '24' : 1500,
    '25' : 1400,
    '26': 1443,
    '27': 1600,
    '28': 1601,
    '29': 1800,
    '30': 1700,
    '31': 2000,
    '32': 112,
    '33': 1900,
    #'34': 1117,
    '35': 2100,
    '36': 1626,
    '37': 2300,
    '38': 2500,
    '39': 2600,
    '40': 2700,
    '41': 2550
}
# set names to hs internal set ids
cc = Constants()
setNameIds = dict((cc.sets[ccid]['name'], hsid) for ccid, hsid in setids.items())
# duel cards
duelSetIds = [ ccid for ccid in setids if cc.sets[ccid].get("duels") ]
duelSets = [ name for name, ccid in jsonToCCSet.items() if cc.sets[ccid].get("duels") ]
# vanilla cards
vanillaSetIds = [ ccid for ccid in setids if cc.sets[ccid].get("vanilla") ]
vanillaSets = [ name for name, ccid in jsonToCCSet.items() if cc.sets[ccid].get("vanilla") ]
# hs internal cardtype ids
hsTypeId = {
    'Hero': '11',
    'Minion': '4',
    'Spell': '5',
    'Weapon': '7',
    'Hero Power': '10'
}
# fix bad subtype names
subtypeFix = {
    'Mechanical': 'Mech'
}
# multi class card group names
multiClassGroups = {
    'GRIMY_GOONS': 'Goons',
    'KABAL': 'Kabal',
    'JADE_LOTUS': 'Lotus'
}
# cards I can't filter out
bad_cards = [
    "PVPDR_BAR_Passive12",
    "PVPDR_BAR_Passive13",
]


def getHTDId(name, *ignored):
    log.debug("getHTDId() getting %s id for hearthhead", name)
    # Hearthstone Top Decks uses name string ids
    name = re.sub(r"['!.:]", '', name).lower()
    name = re.sub(r"[ñ]", 'n', name)
    name = re.sub(r"[é]", 'e', name)
    name = re.sub(r"[à]", 'a', name)
    return re.sub(r"[^\w]+", "-", name)


hpIdRegex = re.compile(r"/cards/(\d+)-.*")

def getHearthpwnIdAndUrl(name, cardset, cardtype, isToken, session):
    log.debug("getHearthpwnIdAndUrl() getting for %s", name)
    # hearthpwn is also weird
    hpname_hacked = name.replace('-', ' ').replace('!', '')
    premium = 0 if isToken else 1

    # filter-name={}&filter-premium={}&filter-type={}&filter-set={}
    url = setUrlTempl.format(hpname_hacked, premium, hsTypeId[cardtype], setNameIds[cardset])
    r = session.get(url)
    r.raise_for_status()
    html = fromstring(r.text)

    images = html.xpath('//td[@class="visual-image-cell"]/a/img')
    descs = html.xpath('//td[@class="visual-details-cell"]/h3/a')

    lowerName = name.lower()

    for i in range(len(images)):
        title = descs[i].text

        if title.lower() == lowerName:
            image = images[i].get('src')
            if not image:
                image = 'https://media-hearth.cursecdn.com/avatars/148/738/687.png'
            image = image.split("?")[0]
            # /cards/31128-annoy-o-tron-fanclub
            hpid = hpIdRegex.match(images[i].get('data-href')).group(1)
            return int(hpid), image.replace('http://', 'https://')

    log.debug("getHearthpwnIdAndUrl() card not found at hearthpwn '%s' '%s': got %s at %s",
        cardset, name, list(desc.text for desc in descs), url)
    raise Exception("getHearthpwnIdAndUrl() card " + name + " in " + cardset + " not found at hearthpwn")


def camelCase(s):
    parts = re.split(r"[^a-zA-Z]+", s) if s else None
    return " ".join(part[:1].upper() + part[1:].lower() for part in parts) if parts else None


def fixText(text):
    if text:
        # replace xml tags
        text = re.sub(r"</?\w+>", '', text)
        # copy bold/italic to reddit?
        # text = re.sub(r"</?b+>", '**', text)
        # text = re.sub(r"</?i+>", '*', text)
        # remove unwanted symbols and chars from card text
        text = text.replace('\n', ' ') \
                    .replace('\u2019', "'") \
                    .replace('$', '') \
                    .replace('[x]', '') \
                    .replace('\u00A0', ' ') \
                    .replace('#', '')
        # replace multiple spaces
        text = re.sub(r"[ ]{2,}", ' ', text)
        text = text.strip()

    return text


def getCardJson():
    rawJson = 'raw-cards.json'
    if not os.path.isfile(rawJson) or os.path.getmtime(rawJson) < (time.time() - 24*60*60):
        with open(rawJson, 'wb') as f:
            f.write(requests.get('https://api.hearthstonejson.com/v1/latest/enUS/cards.json').content)

    with open(rawJson, encoding='utf8') as f:
        return json.load(f)


def loadJsonCards():
    log.debug("loadJsonCards() loading latest card texts from hearthstonejson.com")
    # https://github.com/HearthSim/hearthstonejson
    cardtextjson = getCardJson()

    cards = {}
    tokens = {}
    duels = {}
    vanilla = {}

    for card in cardtextjson:
        if card.get('set') not in jsonToCCSet:
            # uncollectible cards and unknown set
            continue
        if card.get('set') in ['HERO_SKINS']:
            # not a real card set
            continue
        if card.get('type') not in ['MINION', 'SPELL', 'WEAPON', 'HERO', 'HERO_POWER', 'LOCATION']:
            # buffs are irrelevant for us
            continue
        if  card.get('set') in ['BASIC', 'CORE', 'VANILLA'] + duelSets and card.get('type') in ['HERO', 'HERO_POWER']:
            # skip default and duels heroes
            continue
        if card.get('set') in duelSets and not card['id'].startswith('PVPDR'):
            # skip tavern brawl cards not used in duels
            continue
        if 'DFX' in card['id']:
            # skip dummy fx
            continue
        if card.get('set') == 'BATTLEGROUNDS' and not card.get('techLevel'):
            # skip upgraded battleground cards
            continue

        duels_blacklist = ['PVPDR_TEST', 'PVPDR_Duels_Buckets', 'PVPDR_SCH_ComingSoon', 'PVPDR_Empty']
        blacklistedId = next((word for word in duels_blacklist if card['id'].startswith(word)), False)
        if card.get('set') in duelSets and blacklistedId:
            # skip duels buckets
            continue

        text = card.get('text')
        # jade golem and galakrond cards have two texts
        if card['name'].startswith("Galakrond, the ") and card.get('collectionText'):
            text = fixText(text + "Invoke twice to upgrade." + card.get('collectionText'))
        else:
            text = fixText(card.get('collectionText', text))

        rarity = card.get('rarity', 'Token')
        rarity = 'Basic' if rarity == 'FREE' else camelCase(rarity)

        subtype = camelCase(card.get('race'))
        mechanics = card.get('mechanics', [])
        if not subtype and ('QUEST' in mechanics or 'SIDEQUEST' in mechanics):
            subtype = 'Quest'
        if not subtype:
            subtype = camelCase(card.get('spellSchool'))

        clazz = camelCase(card.get('cardClass', 'Neutral'))
        clazz = cc.classes.get(clazz, clazz)

        if 'multiClassGroup' in card and 'classes' in card and card['multiClassGroup'] in multiClassGroups:
            multiClass = multiClassGroups[card['multiClassGroup']]
            classes = ''.join(c[:1] for c in card['classes'])
            clazz = '{} ({})'.format(multiClass, classes)
        elif 'classes' in card:
            clazz = '+'.join(cc.classes.get(camelCase(c), camelCase(c)) for c in card['classes'])

        cardSet = card.get('set')
        if not cardSet:
            log.debug("loadJsonCards() collectible without set. HOF? %s", card)
            cardSet = 'HOF'

        cost = card.get('cost')
        if cost is None and card.get('collectible'):
            log.debug("loadJsonCards() collectible without cost: %s", card)
            cost = 0
        if cardSet == 'BATTLEGROUNDS':
            cost = card.get('techLevel')
        if text and text.startswith('Passive') and cost == 0:
            cost = None

        if 'name' not in card:
            print(card)

        cardData = {
            'id': card['id'],
            'name': card['name'],
            'rarity': rarity,
            'class': clazz,
            'set': cc.sets[jsonToCCSet[cardSet]]['name'],
            'type': camelCase(card['type']),
            'subType': subtypeFix.get(subtype, subtype),
            'cost': cost,
            'desc': text,
            'atk': card.get('attack'),
            'hp': card.get('armor', card.get('health', card.get('durability'))),
            'collectible': card.get('collectible', False)
        }

        if cardSet in duelSets:
            duels[card['id']] = cardData
        elif card.get('collectible'):
            if cardSet in vanillaSets:
                vanilla[card['id']] = cardData
            else:
                # if card['id'] not in cards:
                cards[card['id']] = cardData
        else:
            if cardSet not in vanillaSets:
                cardData['rarity'] = 'Token'
                tokens[card['id']] = cardData


    with open("data/extend_desc.json", "r", encoding='utf8') as f:
        for id, extends in json.load(f).items():
            card = cards.get(id, tokens.get(id))
            if card:
                for ext in extends:
                    extendCard = cards.get(ext, tokens.get(ext))
                    if extendCard:
                        card['extDesc'] = card.get('extDesc', [])
                        card['extDesc'].append("{} ({}): {}".format(extendCard['name'],
                                extendCard.get('cost', 0),
                                extendCard['desc']))

    return cards, tokens, duels, vanilla


def saveCardsAsJson(filename, cards):
    log.debug("saveCardsAsJson() saving %s cards to %s", len(cards), filename)
    with open(filename, "w", newline="\n", encoding='utf8') as f:
        json.dump(cards, f, sort_keys=True, indent=2, separators=(',', ': '))


# default loop all ['02','06','08', ...]
def loadSets(allcards={}, sets=setids.keys()):
    log.debug("loadSets() %s cards %s sets", len(allcards), len(sets))
    # grp by set
    setcarddata = {}

    for _, card in allcards.items():
        if card['id'] not in bad_cards:
            if card['set'] not in setcarddata:
                setcarddata[card['set']] = []
            setcarddata[card['set']].append(card)

    resultCards = {}
    if not sets:
        return resultCards

    def getsetid(name):
        for id, set in cc.sets.items():
            if set["name"] == name:
                return id
        return "00"

    def update(data):
        for name, card in data.items():
            if name not in resultCards or getsetid(card["set"]) > getsetid(resultCards[name]["set"]):
                resultCards[name] = card

    def doSet(setid):
        with requests.Session() as session:
            setname = cc.sets[setid]['name']
            filename = "data/{} {}.json".format(setid, setname)

            if os.path.isfile(filename):
                log.debug("loadSets() using found '%s' file instead of internet", filename)
                with open(filename, 'r', encoding='utf8') as f:
                    update(json.load(f))
            else:
                log.debug("loadSets() getting set from internet %s", setname)
                currentSet = {}

                for card in setcarddata.get(setname, []):
                    name = 'Travelling Healer' if card['name'] == 'Traveling Healer' else card['name']
                    try:
                        hpid, image = getHearthpwnIdAndUrl(name,
                                                            setname,
                                                            card['type'],
                                                            cc.sets[setid].get('duels'),
                                                            session)

                        card['cdn'] = image
                        card['hpwn'] = hpid
                    except Exception as e:
                        try:
                            urlName = getHTDId(name)
                            url = 'https://www.hearthstonetopdecks.com/cards/{}/'.format(urlName)
                            _, cardHTD = parseHTD(url, session)
                            card['cdn'] = cardHTD['cdn']
                            card['hpwn'] = 12288
                        except Exception as e2:
                            log.exception("doSet() card %s also not at htd %s", card, e)
                            if card['collectible']:
                                raise e2
                            log.exception("doSet() skipping card for error %s", e)
                            continue

                    card['head'] = getHTDId(name)
                    if card['name'] in currentSet:
                        log.debug("loadSets() found '%s' again", card['name'])
                    else:
                        currentSet[card['name']] = card
                    print('.', end='')

                saveCardsAsJson(filename, currentSet)
                resultCards.update(currentSet)
                update(currentSet)

    with Pool(4) as p:
        p.map(doSet, sets)

    return resultCards


def loadTokens(tokens = {}, wantedTokens = {}):
    resultCards = {}
    with requests.Session() as session:
        for name, ids in wantedTokens.items():
            card = None

            if 'id' in ids:
                card = tokens[ids['id']]
                if name != card['name']:
                    log.warning('loadTokens() names do not match: %s - %s', name, tokens[ids['id']]['name'])

            if 'id' not in ids:
                for token in tokens.values():
                    if name == token['name']:
                        if card:
                            log.warning('loadTokens() found token again: %s', name)
                        card = token

            if not card:
                log.error('loadTokens() could not find: %s', name)
                print('token not found:', name)
                exit()

            if 'hpwn' in ids:
                r = session.get('https://www.hearthpwn.com/cards/{}'.format(ids['hpwn']))
                r.raise_for_status()
                image = fromstring(r.text).xpath('//img[@class="hscard-static"]')[0].get('src')
                if not image:
                    image = 'https://media-hearth.cursecdn.com/avatars/148/738/687.png'

                card['cdn'] = image.replace('http://', 'https://')
                card['hpwn'] = ids['hpwn']
                card['head'] = getHTDId(card['name'])

                # since jade golem: overwrite scraped stats with prepared ones
                card['atk'] = ids.get('atk', card['atk'])
                card['cost'] = ids.get('cost', card['cost'])
                card['hp'] = ids.get('hp', card['hp'])
            else:
                urlName = getHTDId(card['name'])
                url = 'https://www.hearthstonetopdecks.com/cards/{}/'.format(urlName)
                _, cardHTD = parseHTD(url, session)
                if not cardHTD.get("desc") and card.get('desc'):
                    cardHTD["desc"] = card.get('desc')
                cardHTD["id"] = card["id"]
                card = cardHTD
                if card["set"] == 'Arena Exclusives':
                    card["set"] = 'Taverns of Time'

            resultCards[card['name']] = card
            print('.', end='')

    print('loaded tokens:', len(resultCards))
    return resultCards


def loadAndSaveTokens(allTokens, *, force=False):
    # a lot of token names are not unique
    # a static, handmade list of ids is more reliable
    if os.path.isfile('data/tokenlist.json'):
        if not os.path.isfile("data/tokens.json") \
                or os.path.getmtime("data/tokens.json") < os.path.getmtime('data/tokenlist.json') \
                or force:

            with open('data/tokenlist.json', 'r', encoding='utf8') as f:
                tokenlist = json.load(f)

            # we always want all tavern of time tokens
            for cardid, card in allTokens.items():
                if card.get('set') == "Taverns of Time" and card.get('name') not in tokenlist:
                    tokenlist[card.get('name')] = {}

            saveCardsAsJson("data/tokens.json", loadTokens(allTokens, tokenlist))


def main(setId=None):
    try:
        log.debug("main() full scrape will take 5+ minutes")
        cards, tokens, duels, vanilla = loadJsonCards()

        if setId:
            if setId == 'tokens':
                loadAndSaveTokens(tokens, force=True)
                return
            if setId not in setids:
                print('unkown setId:', setId, 'known sets:', setids)
                return
            loadSets(allcards=cards, sets=[setId])
            return

        cardSetIds = setids.keys() - duelSetIds - set(vanillaSetIds)
        saveCardsAsJson("data/cards.json", loadSets(allcards=cards, sets=cardSetIds))
        saveCardsAsJson("data/duels.json", loadSets(allcards=duels, sets=duelSetIds))
        if not os.path.isfile('data/vanilla.json'):
            saveCardsAsJson("data/vanilla.json", loadSets(allcards=vanilla, sets=vanillaSetIds))

        loadAndSaveTokens(tokens)
        print("success")
    except Exception as e:
        log.exception("main() error %s", e)
        print("error", e)


def parseSingle(hpid):
    try:
        return parseSingleThrowing(hpid)
    except Exception as e:
        log.exception("parseSingle() card %s error %s", hpid, e)
        return "", {}

def parseSingleThrowing(hpid):
    def getFirst(list):
        try:
            return list[0]
        except IndexError:
            return None

    cardTypes = {
        "Playable Hero": "Hero",
        "Ability": "Spell"
    }

    r = requests.get("https://www.hearthpwn.com/cards/{}".format(hpid))
    log.debug("parseSingleThrowing() hpwn url requested: %s", r.url)
    r.raise_for_status()
    root = fromstring(r.text).xpath('//div[@class="details card-details"]')

    name = getFirst(root[0].xpath('./header[1]/h2/text()'))
    head = getHTDId(name)
    cdn = getFirst(root[0].xpath('./section/img[@class="hscard-static"]/@src')).lower()
    descs = root[0].xpath('./div[h3 = "Card Text"]/p//text()')
    desc = ''.join(descs)

    cardset = None
    rarity = None
    cardtype = None
    subType = None
    texts = iter(root[0].xpath('.//aside/ul/li//text()'))
    for text in texts:
        if text == 'Set: ': cardset = next(texts)
        if text == 'Rarity: ': rarity = next(texts)
        if text == 'Type: ':
            cardtype = next(texts)
            cardtype = cardTypes.get(cardtype, cardtype)
        if text == 'Race: ':
            subType = next(texts)
            subType = subtypeFix.get(subType, subType)

    # search
    payload = {'filter-name': re.sub(r"[^\w']+", " ", name).strip(), 'display': 1, 'filter-unreleased': 1}
    r = requests.get("https://www.hearthpwn.com/cards", params=payload)
    log.debug("parseSingleThrowing() hpwn url requested: %s", r.url)
    r.raise_for_status()
    html = fromstring(r.text)
    path = "/cards/{}-{}".format(hpid, head)
    row = getFirst(html.xpath('//div[@class="listing-body"]/table/tbody/tr[td/a/@href="{}"]'.format(path)))

    atk = row.xpath('./td[@class="col-attack"]/text()')[0]
    atk = int(atk) if atk and cardtype in ['Weapon', 'Minion'] else None
    cost = int(row.xpath('./td[@class="col-cost"]')[0].text)
    hp = row.xpath('./td[@class="col-health"]')[0].text
    hp = int(hp) if hp and cardtype in ['Weapon', 'Minion', 'Location'] else None
    clazz = getFirst(row.xpath('./td[@class="col-class"]//text()'))
    clazz = clazz.strip() if clazz else 'Neutral'
    clazz = cc.classes.get(clazz, clazz) # TODO multi classes

    return name, {
        "atk": atk,
        "cdn": cdn.replace('http://', 'https://'),
        "class": clazz,
        "cost": cost,
        "desc": desc,
        "head": head,
        "hp": hp,
        "hpwn": hpid,
        "name": name,
        "rarity": rarity,
        "set": cardset,
        "subType": subType,
        "type": cardtype
    }


def formatSingle(name, card):
    if name and card:
        card = json.dumps(card, indent=4, separators=(',', ': '))
        return ',\n"{}": {}'.format(name, card)
    else:
        return ""

def expandId(id):
    matched = re.match(r'(\d+)(?:-(\d+))?', id)
    if matched:
        a, b = matched.group(1,2)
        if b:
            if int(a) >= int(b):
                raise ValueError('invalid range: {}-{}'.format(a, b))
            yield from range(int(a), int(b) + 1)
        else:
            yield a


def expandIds(ids):
    for id in ids:
        yield from expandId(id)



def parseMultiple(ids):
    return "".join(formatSingle(*parseSingle(id)) for id in expandIds(ids))


def parseHTD(url, requests=requests):
    log.debug("parseHTD() get %s", url)
    r = requests.get(url)
    r.raise_for_status()
    html = fromstring(r.text)

    name = html.xpath('//article//div[@class="card-content"]/p/strong')[0].text
    name = fixText(name)
    desc = ''
    descTags = html.xpath('//article//div[@class="card-content"]/h3')
    if descTags and descTags[0].text == 'Card Text':
        desc = ' '.join((s.strip() for s in html.xpath('//article//div[@class="card-content"]/p')[1].itertext()))

    data = {}
    for li in html.xpath('//article//ul/li'):
        st = tuple(li.itertext())
        data[st[0].strip()] = ''.join(s.strip() for s in st[1:])

    if 'Card Type:' not in data:
        log.debug('type field missing on page: %s', url)
    cardtype = data.get('Card Type:', 'Minion')
    atk = data.get('Attack:')
    hp = data.get('Health:', data.get('Durability:'))
    cardset = data.get('Set:')
    rarity = data.get('Rarity:')
    if rarity == 'Free':
        if cardset == 'Basic':
            rarity = 'Basic'
        else:
            rarity = 'Token'

    clazz = cc.classes.get(data.get('Class:'), data.get('Class:'))
    if not clazz:
        clazz = '+'.join(cc.classes.get(c, c) for c in data.get('Classes:').split(','))

    return name, {
        "atk": int(atk) if atk and cardtype in ['Weapon', 'Minion'] else None,
        "cdn": html.xpath('//article//img/@src')[0],
        "class": clazz,
        "cost": int(data['Mana Cost:']),
        "desc": desc,
        "head": getHTDId(name),
        "hp": int(hp) if hp and cardtype in ['Weapon', 'Minion', 'Location'] else None,
        "hpwn": 12288,
        "name": name,
        "rarity": rarity,
        "set": cardset,
        "subType": data.get('Race:'),
        "type": cardtype
    }


def parseHTDPage(url, requests=requests):
    r = requests.get(url)
    r.raise_for_status()
    html = fromstring(r.text)

    # main page
    urls = html.xpath('//article//header[@class="entry-header"]/h2/a/@href')
    if urls:
        return urls
    # galery url
    return html.xpath('//div[contains(@class, "card-gallery")]/main/article//div[contains(@class, "card-item")]/a/@href')


def parseHTDPageNumber(number, requests=requests):
    return parseHTDPage(f'https://www.hearthstonetopdecks.com/page/{number}/', requests)


if __name__ == "__main__":
    print("see log scrape.log")
    logfile = "scrape-{}.log".format(int(time.time()))
    if os.path.isfile(logfile):
        os.remove(logfile)
    log.basicConfig(filename=logfile,
            format='%(asctime)s %(levelname)s %(message)s',
            level=log.DEBUG)

    log.debug("scrape started with parameters: %s", sys.argv)
    if len(sys.argv) > 1:
        result = ""
        if 'hearthstonetopdecks' in sys.argv[1]:
            log.debug("loading single htd url: %s", sys.argv)
            with requests.Session() as session:
                for url in sys.argv[1:]:
                    if 'cards' in url:
                        urls = [url]
                    else:
                        urls = parseHTDPage(url, session)
                    result += "".join(formatSingle(*parseHTD(url, session)) for url in urls)
        elif 'htd' in sys.argv[1]:
            log.debug("loading htd pages: %s", sys.argv)
            with requests.Session() as session:
                urls = []
                for u in list(parseHTDPageNumber(page, session) for page in expandIds(sys.argv[2:])):
                    urls += u

                result = "".join(formatSingle(*parseHTD(url, session)) for url in urls)
        elif 'set' in sys.argv[1]:
            main(sys.argv[2])
        else:
            log.debug("loading multiple cards from hpwn: %s", sys.argv)
            result = parseMultiple(sys.argv[1:])

        if result:
            print('cards loaded:', result.count('"name":'))
            resultFile = "result-{}.log".format(int(time.time()))
            with open(resultFile, "w", newline="\n", encoding='utf8') as f:
                f.write(result)
            print('cards saved to:', resultFile)
        elif sys.argv[1] != 'set':
            print("nothing found: ", sys.argv[1])

    else:
        log.debug("default scraping")
        main()
