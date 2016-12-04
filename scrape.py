#!/usr/bin/python

import json
import logging as log
import os
import os.path
import re

from lxml.html import fromstring
import requests

import card_constants as cc

"""
Please note:
Scraping somebodies html website without asking is not nice.
Please be a nice user and ask before scraping when if it is not an api.
This is especially true when using images.
"""


# scrape main url
setUrlTempl = ('http://www.hearthpwn.com/cards?'
               'filter-name={}&filter-premium={}&filter-type={}&filter-set={}'
               '&filter-unreleased=1&display=2')
# hearthstonejson set id to card_constant set id
jsonToCCSet = {
    'CORE'    : '01',
    'EXPERT1' : '02',
    'REWARD' : '03',
    'PROMO' : '04',
    'NAXX' : '05',
    'GVG' : '06',
    'BRM' : '07',
    'TGT' : '08',
    'LOE' : '09',
    'OG' : '10',
    'KARA' : '11',
    'GANGS' : '12'
}
# card_constant set ids to hs internal set ids
setids = {
    '01' : 2  ,
    '02' : 3  ,
    '03' : 4  ,
    '04' : 11 ,
    '05' : 100,
    '06' : 101,
    '07' : 102,
    '08' : 103,
    '09' : 104,
    '10' : 105,
    '11' : 106,
    '12' : 107
}
# set names to hs internal set ids
setNameIds = dict((cc.setdata[ccid]['name'], hsid) for ccid, hsid in setids.items())
# hs internal cardtype ids
hsTypeId = {
    'Minion' : '4',
    'Spell' : '5',
    'Weapon' : '7'
}
# fix bad subtype names
subtypeFix = {
    'Mechanical' : 'Mech'
}
# multi class card group names
multiClassGroups = {
    'GRIMY_GOONS' : 'Goons',
    'KABAL' : 'Kabal',
    'JADE_LOTUS' : 'Lotus'
}


hearthHeadClean = re.compile(r"[^\-a-z0-9 ]")

def getHearthHeadId(name, type, session):
    log.debug("getHearthHeadId() getting %s from hearthhead", name)
    # HearthHead does now work without id
    return hearthHeadClean.sub('', name.lower()).replace(' ', '-')


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

    for i in range(len(images)):
        title = descs[i].text

        if title == name:
            image = images[i].get('src')
            if not image:
                image = 'http://media-hearth.cursecdn.com/avatars/148/738/687.png'
            # /cards/31128-annoy-o-tron-fanclub
            hpid = hpIdRegex.match(images[i].get('data-href')).group(1)
            return int(hpid), image

    log.debug("getHearthpwnIdAndUrl() card not found at herathpwn %s", name)
    raise Exception("getHearthpwnIdAndUrl() card " + name + " not found at hearthpwn")


def loadJsonCards():
    log.debug("loadJsonCards() loading latest card texts from hearthstonejson.com")
    # https://github.com/HearthSim/hearthstonejson
    r = requests.get('https://api.hearthstonejson.com/v1/latest/enUS/cards.json')
    r.raise_for_status()
    cardtextjson = r.json()

    spaceRegex = re.compile(r"[ ]{2,}")
    tagRegex = re.compile(r"</?\w+>")
    camelCase = lambda s: s[:1] + s[1:].lower() if s else None

    cards = {}
    tokens = {}
    for card in cardtextjson:
        if card.get('set') not in jsonToCCSet:
            # helper can't handle this yet
            continue
        if card.get('type') not in ['MINION', 'SPELL', 'WEAPON']:
            # hero power, hero and buffs are irrelevant for us
            continue


        text = card.get('text')
        # jade golem cards have two texts
        text = card.get('collectionText', text)

        if text:
            text = tagRegex.sub('', text)
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
            text = spaceRegex.sub(' ', text)
            text = text.strip()

        rarity = card.get('rarity', 'Token')
        rarity = 'Basic' if rarity == 'FREE' else camelCase(rarity)
        subtype = camelCase(card.get('race'))
        clazz = camelCase(card.get('playerClass', 'Neutral'))

        if 'multiClassGroup' in card and 'classes' in card:
            multiClass = multiClassGroups[card['multiClassGroup']]
            classes = ''.join(c[:1] for c in card['classes'])
            clazz = '{} ({})'.format(multiClass, classes)

        cardData = {
            'id': card['id'],
            'name': card['name'],
            'rarity': rarity,
            'class': clazz,
            'set': cc.setdata[jsonToCCSet[card['set']]]['name'],
            'type': camelCase(card['type']),
            'subType': subtypeFix.get(subtype, subtype),
            'cost': card.get('cost', 0),
            'desc': text,
            'atk': card.get('attack'),
            'hp': card.get('health', card.get('durability'))
        }

        if card.get('collectible'):
            cards[card['id']] = cardData
        else:
            cardData['rarity'] = 'Token'
            tokens[card['id']] = cardData

    return cards, tokens


def saveCardsAsJson(filename, cards):
    log.debug("saveCardsAsJson() saving %s cards to %s", len(cards), filename)
    with open(filename, "w", newline="\n") as f:
        json.dump(cards, f, sort_keys=True, indent=2, separators=(',', ': '))


# default loop all ['02','06','08', ...]
def loadSets(allcards = {}, sets = cc.setdata.keys()):
    # grp by set
    setcarddata = {}

    for id, card in allcards.items():
        if card['set'] not in setcarddata:
            setcarddata[card['set']] = []
        setcarddata[card['set']].append(card)

    resultCards = {}

    with requests.Session() as session:
        with requests.Session() as hhSession:
            for setid in sets:
                setname = cc.setdata[setid]['name']
                filename = "{} {}.json".format(setid, setname)

                if os.path.isfile(filename):
                    log.debug("loadSets() using found '%s' file instead of internet", filename)
                    with open(filename, "r") as f:
                        resultCards.update(json.load(f))
                else:
                    currentSet = {}

                    for card in setcarddata.get(setname, []):
                        hpid, image = getHearthpwnIdAndUrl(card['name'],
                                                            setname,
                                                            card['type'],
                                                            False,
                                                            session)

                        hhid = getHearthHeadId(card['name'], card['type'], hhSession)

                        card['cdn'] = image
                        card['hpwn'] = hpid
                        card['head'] = hhid
                        currentSet[card['name']] = card

                    saveCardsAsJson(filename, currentSet)
                    resultCards.update(currentSet)

    return resultCards


def loadTokens(tokens = {}, wantedTokens = {}):
    resultCards = {}
    with requests.Session() as session:
        for name, ids in wantedTokens.items():
            if name != tokens[ids['id']]['name']:
                log.warning('loadTokens() names do not match: %s - %s', name, tokens[ids['id']]['name'])

            r = session.get('http://www.hearthpwn.com/cards/{}'.format(ids['hpwn']))
            r.raise_for_status()
            image = fromstring(r.text).xpath('//img[@class="hscard-static"]')[0].get('src')
            if not image:
                image = 'http://media-hearth.cursecdn.com/avatars/148/738/687.png'

            card = tokens[ids['id']]
            card['cdn'] = image
            card['hpwn'] = ids['hpwn']
            card['head'] = getHearthHeadId(card['name'], "ignored", "ignored")

            # since jade golem: overwrite scraped stats with prepared ones
            card['atk'] = ids.get('atk', card['atk'])
            card['cost'] = ids.get('cost', card['cost'])
            card['hp'] = ids.get('hp', card['hp'])

            resultCards[card['name']] = card

    return resultCards


def main():
    print("see log scrape.log")
    if os.path.isfile("scrape.log"):
        os.remove("scrape.log")
    log.basicConfig(filename="scrape.log",
            format='%(asctime)s %(levelname)s %(message)s',
            level=log.DEBUG)

    try:
        log.debug("main() full scrape will take 5-10 minutes")
        cards, tokens = loadJsonCards()

        saveCardsAsJson("cards.json", loadSets(cards))

        # a lot of token names are not unique
        # a static, handmade list of ids is more reliable
        if os.path.isfile('tokenlist.json'):
            with open('tokenlist.json', 'r') as f:
                saveCardsAsJson("tokens.json", loadTokens(tokens, json.load(f)))
    except Exception as e:
        log.exception("main() error %s", e)


if __name__ == "__main__":
    main()
