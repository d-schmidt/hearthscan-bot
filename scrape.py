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
    'CORE': '01',
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
    'HOF': '14',
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
    'SCHOLOMANCE': '26'
}
# card_constant set ids to hs internal set ids
setids = {
    '01' : 2,
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
    '14' : 4,
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
    '26': 1443
}
# set names to hs internal set ids
cc = Constants()
setNameIds = dict((cc.sets[ccid]['name'], hsid) for ccid, hsid in setids.items())
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


def getHearthHeadId(name, *ignored):
    log.debug("getHearthHeadId() getting %s id for hearthhead", name)
    # HearthHead does now work without id

    name = re.sub(r"['!.]", '', name).lower()
    name = re.sub(r"[ñ]", 'n', name)
    return re.sub(r"[^\w]+", "-", name)


hpIdRegex = re.compile(r"/cards/(\d+)-.*")

def getHearthpwnIdAndUrl(name, set, type, isToken, session):
    log.debug("getHearthpwnIdAndUrl() getting for %s", name)
    # hearthpwn is also weird
    hpname_hacked = name.replace('-', ' ').replace('!', '')
    premium = 0 if isToken else 1

    # filter-name={}&filter-premium={}&filter-type={}&filter-set={}
    r = session.get(setUrlTempl.format(hpname_hacked, premium, hsTypeId[type], setNameIds[set]))
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
            # /cards/31128-annoy-o-tron-fanclub
            hpid = hpIdRegex.match(images[i].get('data-href')).group(1)
            return int(hpid), image.replace('http://', 'https://')

    log.debug("getHearthpwnIdAndUrl() card not found at hearthpwn '%s' '%s'", set, name)
    raise Exception("getHearthpwnIdAndUrl() card " + name + " not found at hearthpwn")


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

    for card in cardtextjson:
        if card.get('set') not in jsonToCCSet:
            # uncollectible cards and unknown set
            continue
        if card.get('set') in ['HERO_SKINS']:
            # not a real card set
            continue
        if card.get('type') not in ['MINION', 'SPELL', 'WEAPON', 'HERO', 'HERO_POWER']:
            # buffs are irrelevant for us
            continue
        if  card.get('set') == 'CORE' and card.get('type') in ['HERO', 'HERO_POWER']:
            # skip default heroes
            continue

        text = card.get('text')
        # jade golem cards have two texts
        if "Galakrond, the " == card['name'][:15] and card.get('collectionText'):
            text = fixText(text + "Invoke twice to upgrade." + card.get('collectionText'))
        else:
            text = fixText(card.get('collectionText', text))

        rarity = card.get('rarity', 'Token')
        rarity = 'Basic' if rarity == 'FREE' else camelCase(rarity)

        subtype = camelCase(card.get('race'))
        if not subtype and "QUEST" in card.get("mechanics", []):
            subtype = 'Quest'

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
            'hp': card.get('armor', card.get('health', card.get('durability')))
        }

        if card.get('collectible'):
            cards[card['id']] = cardData
        else:
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

    return cards, tokens


def saveCardsAsJson(filename, cards):
    log.debug("saveCardsAsJson() saving %s cards to %s", len(cards), filename)
    with open(filename, "w", newline="\n", encoding='utf8') as f:
        json.dump(cards, f, sort_keys=True, indent=2, separators=(',', ': '))


# default loop all ['02','06','08', ...]
def loadSets(allcards={}, sets=setids.keys()):
    # grp by set
    setcarddata = {}

    for id, card in allcards.items():
        if card['set'] not in setcarddata:
            setcarddata[card['set']] = []
        setcarddata[card['set']].append(card)

    resultCards = {}

    def doSet(setid):
        with requests.Session() as session:
            setname = cc.sets[setid]['name']
            filename = "data/{} {}.json".format(setid, setname)

            if os.path.isfile(filename):
                log.debug("loadSets() using found '%s' file instead of internet", filename)
                with open(filename, 'r', encoding='utf8') as f:
                    resultCards.update(json.load(f))
            else:
                log.debug("loadSets() getting set from internet %s", setname)
                currentSet = {}

                for card in setcarddata.get(setname, []):
                    name = 'Travelling Healer' if card['name'] == 'Traveling Healer' else card['name']
                    try:
                        hpid, image = getHearthpwnIdAndUrl(name,
                                                            setname,
                                                            card['type'],
                                                            False,
                                                            session)

                        card['cdn'] = image
                        card['hpwn'] = hpid
                    except Exception as e:
                        urlName = getHearthHeadId(name)
                        url = 'https://www.hearthstonetopdecks.com/cards/{}/'.format(urlName)
                        _, cardHTD = parseHTD(url, session)
                        card['cdn'] = cardHTD['cdn']
                        card['hpwn'] = 12288

                    card['head'] = getHearthHeadId(name)
                    currentSet[card['name']] = card
                    print('.', end='')

                saveCardsAsJson(filename, currentSet)
                resultCards.update(currentSet)

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
                log.warning('loadTokens() could not find: %s', name)
                exit()

            if 'hpwn' in ids:
                r = session.get('https://www.hearthpwn.com/cards/{}'.format(ids['hpwn']))
                r.raise_for_status()
                image = fromstring(r.text).xpath('//img[@class="hscard-static"]')[0].get('src')
                if not image:
                    image = 'https://media-hearth.cursecdn.com/avatars/148/738/687.png'

                card['cdn'] = image.replace('http://', 'https://')
                card['hpwn'] = ids['hpwn']
                card['head'] = getHearthHeadId(card['name'])

                # since jade golem: overwrite scraped stats with prepared ones
                card['atk'] = ids.get('atk', card['atk'])
                card['cost'] = ids.get('cost', card['cost'])
                card['hp'] = ids.get('hp', card['hp'])
            else:
                urlName = getHearthHeadId(card['name'])
                url = 'https://www.hearthstonetopdecks.com/cards/{}/'.format(urlName)
                _, cardHTD = parseHTD(url, session)
                if not cardHTD.get("desc") and card.get('desc'):
                    cardHTD["desc"] = card.get('desc')
                cardHTD["id"] = card["id"]
                card = cardHTD

            resultCards[card['name']] = card
            print('.', end='')

    return resultCards


def main():
    try:
        log.debug("main() full scrape will take 5-10 minutes")
        cards, tokens = loadJsonCards()

        saveCardsAsJson("data/cards.json", loadSets(allcards=cards))

        # a lot of token names are not unique
        # a static, handmade list of ids is more reliable
        if os.path.isfile('data/tokenlist.json'):
            with open('data/tokenlist.json', 'r', encoding='utf8') as f:
                saveCardsAsJson("data/tokens.json", loadTokens(tokens, json.load(f)))
        print("success")
    except Exception as e:
        log.exception("main() error %s", e)
        print("error", e)


def parseSingle(hpid):
    try:
        return parseSingleThrowing(hpid)
    except Exception as e:
        print(hpid, e)
        import traceback
        traceback.print_exc()
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
    r.raise_for_status()
    root = fromstring(r.text).xpath('//div[@class="details card-details"]')

    name = getFirst(root[0].xpath('./header[1]/h2/text()'))
    head = getHearthHeadId(name)
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
    r.raise_for_status()
    html = fromstring(r.text)
    path = "/cards/{}-{}".format(hpid, head)
    row = getFirst(html.xpath('//div[@class="listing-body"]/table/tbody/tr[td/a/@href="{}"]'.format(path)))

    atk = row.xpath('./td[@class="col-attack"]/text()')[0]
    atk = int(atk) if atk and cardtype in ['Weapon', 'Minion'] else None
    cost = int(row.xpath('./td[@class="col-cost"]')[0].text)
    hp = row.xpath('./td[@class="col-health"]')[0].text
    hp = int(hp) if hp and cardtype in ['Weapon', 'Minion'] else None
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

    if 'Type:' not in data:
        print('type missing on page:', name)
    cardtype = data.get('Type:', 'Minion')
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
        "head": getHearthHeadId(name),
        "hp": int(hp) if hp and cardtype in ['Weapon', 'Minion'] else None,
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
    return html.xpath('//article//header[@class="entry-header"]/h2/a/@href')

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

    if len(sys.argv) > 1:
        result = ""
        if 'hearthstonetopdecks' in sys.argv[1]:
            with requests.Session() as session:
                if 'cards' in sys.argv[1]:
                    urls = [sys.argv[1]]
                else:
                    urls = parseHTDPage(sys.argv[1], session)
                result = "".join(formatSingle(*parseHTD(url, session)) for url in urls)
        elif 'hdt' in sys.argv[1]:
            with requests.Session() as session:
                pages = sys.argv[2].split('-')
                if len(pages) == 1:
                    urls = parseHTDPageNumber(pages[0], session)
                else:
                    urls = (card for page in range(int(pages[0]), int(pages[1]) + 1)
                            for card in parseHTDPageNumber(page, session))
                result = "".join(formatSingle(*parseHTD(url, session)) for url in urls)
        else:
            result = parseMultiple(sys.argv[1:])

        if result:
            print(result)
            resultFile = "result-{}.log".format(int(time.time()))
            with open(resultFile, "w", newline="\n", encoding='utf8') as f:
                f.write(result)
        else:
            print("nothing found: ", sys.argv[1])

    else:
        main()
