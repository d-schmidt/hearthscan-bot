#!/usr/bin/env python3

import json
import logging
import os
import os.path
import sys
import time
import unittest
from unittest.mock import MagicMock
from unittest.mock import call
import uuid

import praw
from praw.config import Config
import prawcore
import requests

import scrape
# I didn't know this before creating the test
hsbot = __import__("hearthscan-bot")

import commentDB
import credentials
import formatter
from cardDB import CardDB
from constants import Constants
from helper import HSHelper
from helper import SpellChecker
from praww import RedditBot
from praww import _SeenDB


# start with 'test.py online' to start slow tests requiring internet and working credentials
SKIP_INTERNET_TESTS = len(sys.argv) < 2 or sys.argv[1] != "online"


def removeFile(path):
    """error free file delete"""
    if os.path.isfile(path):
        os.remove(path)


class TempJson():
    """context aware, self deleting json file creator"""
    def __init__(self, obj):
        self.obj = obj
        self.file = str(uuid.uuid4()) + '.json'

    def __enter__(self):
        with open(self.file, "w", newline="\n") as f:
            json.dump(self.obj, f, sort_keys=True, indent=2, separators=(',', ':'))
        return self.file

    def __exit__(self, type, value, traceback):
        removeFile(self.file)

class TempFile():
    """context aware, self deleting file creator"""
    def __init__(self, suffix):
        self.file = str(uuid.uuid4()) + '.' + suffix

    def __enter__(self):
        return self.file

    def __exit__(self, type, value, traceback):
        removeFile(self.file)


class TestScrape(unittest.TestCase):
    """scrape.py"""

    # @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_hearthhead(self):
        with requests.Session() as s:
            self.assertEqual(scrape.getHearthHeadId('Quick Shot', 'Spell', s),
                'quick-shot')
            self.assertEqual(scrape.getHearthHeadId('Undercity Valiant',
                'Minion', s), 'undercity-valiant')
            self.assertEqual(scrape.getHearthHeadId('Gorehowl', 'Weapon', s),
                'gorehowl')
            self.assertEqual(scrape.getHearthHeadId('V-07-TR-0N',
                'Minion', s), 'v-07-tr-0n')
            self.assertEqual(scrape.getHearthHeadId("Al'Akir the Windlord",
                'Minion', s), 'alakir-the-windlord')

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_Hearthpwn(self):
        with requests.Session() as s:
            self.assertEqual(scrape.getHearthpwnIdAndUrl('Quick Shot',
                    'Blackrock Mountain', 'Spell', False, s),
                    (14459, 'http://media-Hearth.cursecdn.com/avatars/310/105/14459.png'))
            self.assertEqual(scrape.getHearthpwnIdAndUrl('Upgrade!',
                    'Classic', 'Spell', False, s),
                    (638, 'http://media-Hearth.cursecdn.com/avatars/285/274/635951439216665743.png'))

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_full(self):
        expected = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/avatars/310/105/14459.png',
                'desc': 'Deal 3 damage. If your hand is empty, draw a card.',
                'hp': None,
                'class': 'Hunter',
                'subType': None,
                'set': 'Blackrock Mountain',
                'rarity': 'Common',
                'atk': None,
                'head': 'quick-shot',
                'name': 'Quick Shot',
                'cost': 2
            }
        }
        # scrape just one card
        cards = {
            "ignoredId" : {
                'type': 'Spell',
                'desc': 'Deal 3 damage. If your hand is empty, draw a card.',
                'hp': None,
                'class': 'Hunter',
                'subType': None,
                'set': 'Blackrock Mountain',
                'rarity': 'Common',
                'atk': None,
                'name': 'Quick Shot',
                'cost': 2
            }
        }

        # this file is created to cache results
        removeFile('07 Blackrock Mountain.json')
        scraped = scrape.loadSets(cards, ['07'])
        removeFile('07 Blackrock Mountain.json')
        self.assertEqual(scraped, expected)

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_full_tokens(self):
        expected = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/avatars/310/105/14459.png',
                'desc': 'Deal 3 damage. If your hand is empty, draw a card.',
                'hp': None,
                'class': 'Hunter',
                'subType': None,
                'set': 'Blackrock Mountain',
                'rarity': 'Common',
                'atk': None,
                'head': 'quick-shot',
                'name': 'Quick Shot',
                'cost': 2
            }
        }
        # scrape just one card
        wantedtokens = {
            "Quick Shot": {
                "id" : "BRM_013",
                "hpwn": 14459
            }
        }
        tokens = {
            "BRM_013" : {
                'type': 'Spell',
                'desc': 'Deal 3 damage. If your hand is empty, draw a card.',
                'hp': None,
                'class': 'Hunter',
                'subType': None,
                'set': 'Blackrock Mountain',
                'rarity': 'Common',
                'atk': None,
                'name': 'Quick Shot',
                'cost': 2
            }
        }

        self.assertEqual(scrape.loadTokens(tokens, wantedtokens), expected)

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_JsonCards_loadFixer(self):
        cards, tokens = scrape.loadJsonCards()
        # description
        self.assertEqual(cards['LOE_079']['desc'],
                "Battlecry: Shuffle the 'Map to the Golden Monkey' into your deck.")
        self.assertEqual(cards['GVG_085']['desc'], "Taunt Divine Shield")
        self.assertEqual(cards['GVG_012']['desc'][:16], "Restore 3 Health")
        self.assertEqual(cards['EX1_279']['desc'], "Deal 10 damage.")
        self.assertEqual(cards['BRM_013']['desc'],
                "Deal 3 damage. If your hand is empty, draw a card.")
        self.assertEqual(cards['EX1_298']['desc'][:13], "Can't attack.")
        self.assertEqual(cards['CFM_902']['desc'],
                "Battlecry and Deathrattle: Summon a Jade Golem.")
        # multi class
        self.assertEqual(cards['CFM_902']['class'], "Lotus (DRS)")


class TestConst(unittest.TestCase):
    """constants.py constants.json"""

    def test_ScrapeConstSetLength(self):
        # easy to miss one when a new set is added
        c = Constants()
        self.assertEqual(len(scrape.jsonToCCSet), len(c.sets),
                'okay to fail during spoiler season')
        self.assertEqual(len(scrape.setids), len(c.sets))
        self.assertEqual(len(scrape.setNameIds), len(c.sets))

    def test_SpecialReplacements(self):

        constantJson = {
            'sets' : { },
            'specials' : {
                "dream cards" : ["dream", "emeralddrake", "laughingsister",
                        "nightmare", "ysera awakens"]
            },
            'alternative_names' : { }
        }

        with TempJson(constantJson) as json:
            c = Constants(json)
            # tests replace and maxlength
            replaced = c.replaceSpecial(["111", "dreamcards", "333", "444"])

            self.assertEqual(replaced, ["111",
                                         "dream",
                                         "emeralddrake",
                                         "laughingsister",
                                         "nightmare",
                                         "yseraawakens",
                                         "333"])

    def test_AlternativeReplacements(self):

        constantJson = {
            'sets' : { },
            'specials' : { },
            'alternative_names' : {
                'carda' : 'ca',
                'card b' : ['cb', 'cb b']
            }
        }

        with TempJson(constantJson) as json:
            c = Constants(json)
            self.assertEqual(c.translateAlt("ca"), "carda")
            self.assertEqual(c.translateAlt("cb"), "cardb")
            self.assertEqual(c.translateAlt("cc"), "cc")


class TestCommentDB(unittest.TestCase):
    """commentDB.py"""

    testDBName = "test.db"

    def test_CreateFindFailParent(self):
        removeFile(self.testDBName)

        db = commentDB.DB(self.testDBName)

        self.assertFalse(db.exists("abc", ["a card"]))
        # inserted on exists
        self.assertTrue(db.exists("abc", ["a card"]))

        self.assertFalse(db.exists("abc", ["b card"]))
        self.assertTrue(db.exists("abc", ["a card", "b card"]))

        self.assertFalse(db.exists("abc", ["a card", "b card", "c card"]))
        self.assertFalse(db.exists("123", ["a card"]))

        db.close()
        removeFile(self.testDBName)


class TestPRAWW(unittest.TestCase):
    """praww.py"""

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_RedditAuth(self):
        # will fail for missing/bad praw.ini
        with TempFile('db') as seenDB:
            RedditBot([], newLimit=1, sleep=0, connectAttempts=1,
                        dbName=seenDB) \
                    .run(lambda: removeFile(RedditBot.LOCK_FILE))

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_RedditAuthFail(self):

        def raiseError():
            raise Exception('unexpected')

        try:
            # backup existing praw ini, create our own
            if os.path.isfile('praw.ini'):
                os.rename('praw.ini', '_praw.ini')
            with open('praw.ini', 'w', newline="\n") as f:
                f.write('[testbot]\n')
                f.write('client_id=badid\n')
                f.write('client_secret=badsecret\n')
                f.write('refresh_token=badtoken\n')
                f.write('user_agent=praw:hearthscan-test:1.0 (by /u/b0ne123)')

            Config.CONFIG = None

            with self.assertRaises(prawcore.exceptions.ResponseException), \
                    TempFile('db') as seenDB:
                RedditBot([], newLimit=1, sleep=0, connectAttempts=1,
                            iniSite='testbot', dbName=seenDB) \
                        .run(raiseError)
        finally:
            removeFile('praw.ini')
            if os.path.isfile('_praw.ini'):
                os.rename('_praw.ini', 'praw.ini')


    def test_seenDB(self):
        with TempFile('db') as dbfile:
            db = _SeenDB(dbfile)

            class Thing():
                fullname = "t1_thingid"

            thing = Thing()
            self.assertFalse(db.isSeen(thing))
            self.assertTrue(db.isSeen(thing))
            db.cleanup(secondsOld = 0)
            self.assertFalse(db.isSeen(thing))
            self.assertTrue(db.isSeen(thing))
            db.close()


class TestCardDB(unittest.TestCase):
    """cardDB.py"""

    def test_CleanName(self):
        self.assertEqual(CardDB.cleanName('Ab: 1c'), 'abc')

    def test_CardDB(self):
        cardDict = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/14459.png',
                'desc': 'Deal 3 damage. Draw a card.',
                'hp': 1,
                'class': 'Hunter',
                'subType': 'Mech',
                'set': 'Basic',
                'rarity': 'Common',
                'atk': 3,
                'head': 'quick-shot',
                'name': 'Quick Shot',
                'cost': 2
            }
        }

        constantDict = {
            'sets' : { '01' : {'name' : 'Basic'} },
            'specials' : { },
            'alternative_names' : { }
        }

        with TempJson(constantDict) as constJson, \
                TempJson(cardDict) as cardJson, \
                TempJson({}) as emptyJson:

            c = Constants(constJson)
            db = CardDB(c, cardJson, emptyJson, emptyJson)

            self.assertEqual(db.cardNames(), ['quickshot'])
            self.assertEqual(db.tokens, [])
            self.assertTrue('quickshot' in db)
            self.assertFalse('slowshot' in db)
            self.assertTrue('Quick Shot' in db['quickshot'])

    def test_CardDBTokens(self):
        cardDict = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/14459.png',
                'desc': 'Deal 3 damage. Draw a card.',
                'hp': 1,
                'class': 'Hunter',
                'subType': 'Mech',
                'set': 'Basic',
                'rarity': 'Token',
                'atk': 3,
                'head': 'quick-shot',
                'name': 'Quick Shot',
                'cost': 2
            }
        }

        constantDict = {
            'sets' : { '01' : {'name' : 'Basic'} },
            'specials' : { },
            'alternative_names' : { }
        }

        with TempJson(constantDict) as constJson, \
                TempJson(cardDict) as cardJson, \
                TempJson({}) as emptyJson:

            c = Constants(constJson)
            db = CardDB(c, emptyJson, cardJson, emptyJson)

            self.assertEqual(db.cardNames(), ['quickshot'])
            self.assertEqual(db.tokens, ['quickshot'])
            self.assertTrue('quickshot' in db)
            self.assertTrue('Quick Shot' in db['quickshot'])

    def test_RefreshCardDB(self):
        cardDict = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/14459.png',
                'desc': 'Deal 3 damage. Draw a card.',
                'hp': 1,
                'class': 'Hunter',
                'subType': "Mech",
                'set': 'Basic',
                'rarity': 'Common',
                'atk': 3,
                'head': 'quick-shot',
                'name': 'Quick Shot',
                'cost': 2
            }
        }

        constantDict = {
            'sets' : { '01' : {'name' : 'Basic'} },
            'specials' : { },
            'alternative_names' : { }
        }

        with TempJson(constantDict) as constJson, \
                TempJson(cardDict) as cardJson, \
                TempJson({}) as emptyJson:

            c = Constants(constJson)
            db = CardDB(c, emptyJson, emptyJson, 'notexisting.json')

            self.assertEqual(db.cardNames(), [])
            self.assertFalse('quickshot' in db)

            db.tempJSON = cardJson
            db.refreshTemp()

            self.assertTrue('quickshot' in db)
            self.assertTrue('Quick Shot' in db['quickshot'])


class TestHelper(unittest.TestCase):
    """helper.py HSHelper"""

    def test_QuoteCleaner(self):
        self.assertEqual(HSHelper.removeQuotes("> b\na\n> b\nc"), "a c")
        self.assertEqual(HSHelper.removeQuotes("> abc"), "")

    def test_getCardsFromComment(self):

        cardDict = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/14459.png',
                'desc': 'Deal 3 damage. Draw a card.',
                'hp': 1,
                'class': 'Hunter',
                'subType': "Mech",
                'set': 'Basic',
                'rarity': 'Common',
                'atk': 3,
                'head': 'quick-shot',
                'name': 'Quick Shot',
                'cost': 2
            }
        }

        constantDict = {
            'sets' : { '01' : {'name' : 'Basic'} },
            'specials' : { },
            'alternative_names' : { "quickshot" : "qs" }
        }

        with TempJson(constantDict) as constJson, \
                TempJson(cardDict) as cardJson, \
                TempJson({}) as emptyJson:

            c = Constants(constJson)
            db = CardDB(c, cardJson, emptyJson, emptyJson)
            helper = HSHelper(db, c)

            # simple find
            text = '[[test]]'
            cards, text = helper.parseText(text)
            self.assertEqual(cards, ['test'], 'simple card')
            self.assertEqual(len(text), 0, 'unknown card')
            # two cards, cleanName
            text = ' [[hello]] world [[Ab 123c]] '
            cards, text = helper.parseText(text)
            self.assertEqual(cards, ['hello', 'abc'], 'multi cards, clean')
            self.assertEqual(len(text), 0, 'unknown cards')
            # spell check
            text = '[[Quic Shot]]'
            cards, text = helper.parseText(text)
            self.assertEqual(cards, ['quickshot'], 'simple card')
            self.assertTrue('Quick Shot' in text)
            # alternative name
            text = '[[QS]]'
            cards, text = helper.parseText(text)
            self.assertEqual(cards, ['quickshot'], 'alternative name')
            self.assertTrue('Quick Shot' in text)
            # test card limit
            cardsNames = [chr(97 + i) * 2 for i in range(c.CARD_LIMIT + 1)]
            text = '[[' + ']][['.join(cardsNames) +']]'
            cards, text = helper.parseText(text)
            self.assertEqual(cards, cardsNames[:-1],
                    'card limit')
            self.assertEqual(len(text), 0, 'unknown cards')
            # test short text
            text = '[[a]]'
            cards, text = helper.parseText(text)
            self.assertEqual(len(cards), 0, 'no cards')
            self.assertEqual(len(text), 0, 'no cards')
            # test no valid text
            text = '[[123]] [abc]'
            cards, text = helper.parseText(text)
            self.assertEqual(len(cards), 0, 'no valid text')
            self.assertEqual(len(text), 0, 'no valid text')
            # card too long
            text = '[[123456789012345678901234567890abc]]'
            cards, text = helper.parseText(text)
            self.assertEqual(len(cards), 0, 'card too long')
            self.assertEqual(len(text), 0, 'card too long')


    def test_loadInfoTempl_simple(self):

        constantDict = {
            'sets' : { },
            'specials' : { 'dream' : ['no'] },
            'alternative_names' : { 'quickshot' : 'qs' }
        }

        with TempJson(constantDict) as constJson, \
                TempJson({}) as emptyJson, \
                TempFile('template') as templateFile:

            with open(templateFile, 'w', newline="\n") as f:
                f.write('{user}-{alts}-{tokens}-{special}')

            formatter.INFO_MSG_TMPL = templateFile

            c = Constants(constJson)
            db = CardDB(c, emptyJson, emptyJson, emptyJson)
            helper = HSHelper(db, c)

            info = helper.getInfoText('user')
            self.assertEqual(info, 'user-qs--dream')


    def test_JsonFiles(self):
        if os.path.isfile('tempinfo.json'):
            with open('tempinfo.json', 'r') as infofile:
                json.load(infofile)
        if os.path.isfile("tokens.json"):
            with open('tokens.json', 'r') as infofile:
                json.load(infofile)
        if os.path.isfile("cards.json"):
            with open('cards.json', 'r') as infofile:
                json.load(infofile)


class TestSpelling(unittest.TestCase):
    """helper.py SpellChecker"""

    def test_Spellchecker(self):
        checker = SpellChecker(["abcdef"])
        self.assertEqual(checker.correct("abcdef"), "abcdef")
        self.assertEqual(checker.correct("abcde"), "abcdef")
        self.assertEqual(checker.correct("bcdef"), "abcdef")
        self.assertEqual(checker.correct("acdef"), "abcdef")
        self.assertEqual(checker.correct("bacdef"), "abcdef")
        self.assertEqual(checker.correct("abcdeg"), "abcdef")
        self.assertEqual(checker.correct("aabcdef"), "abcdef")
        # only distance 1 errors are fixed
        self.assertEqual(checker.correct("abcd"), "abcd")


class TestBot(unittest.TestCase):
    """hearthscan-bot.py"""

    def test_AnswerMail_UserOnSpam(self):
        r = MagicMock()
        msg = MagicMock()
        msg.subreddit = None
        msg.author.name = 'user'
        msg.id = 'msgid'
        msg.distinguished = None
        pmUserCache = {'user' : 1234}

        helper = MagicMock()

        # test
        hsbot.answerPM(r, msg, pmUserCache, helper)

        self.assertEqual(r.method_calls, [], 'no reddit calls')
        self.assertEqual(helper.method_calls, [], 'no helper calls')

    def test_AnswerMail_Success(self):
        r = MagicMock()

        msg = MagicMock()
        msg.subreddit = None
        msg.author.name = 'user'
        msg.id = 'msgid'
        msg.distinguished = None
        msg.subject = 'sub'
        msg.body = 'body'
        pmUserCache = { }

        helper = MagicMock()
        helper.parseText = MagicMock(return_value=(['card'], 'text'))

        # test
        hsbot.answerPM(r, msg, pmUserCache, helper)

        self.assertTrue('user' in pmUserCache, 'user added to cache')

        self.assertEqual(r.method_calls, [], 'no reddit calls')
        expected = [call.parseText('sub body')]
        self.assertEqual(helper.method_calls, expected, 'parseText')
        expected = [call.reply('text')]
        self.assertEqual(msg.method_calls, expected, 'reply')

    def test_Forward_PM(self):
        r = MagicMock()
        msg = MagicMock()
        msg.subreddit = None
        msg.author.name = 'user'
        msg.id = 'msgid'
        msg.distinguished = None
        msg.subject = 'sub'
        msg.body = 'body'
        pmUserCache = { }

        helper = MagicMock()
        helper.parseText = MagicMock(return_value=([], 'text'))

        redMsg = MagicMock()
        r.redditor = MagicMock(return_value=redMsg)

        # test
        hsbot.answerPM(r, msg, pmUserCache, helper)

        self.assertTrue('user' in pmUserCache, 'user added to cache')

        expected = [call.redditor(credentials.admin_username)]
        self.assertEqual(r.method_calls, expected, 'get reditor')

        expected = [call.message('#msgid /u/user: "sub"', msg.body)]
        self.assertEqual(redMsg.method_calls, expected, 'set message')

        expected = [call.parseText('sub body')]
        self.assertEqual(helper.method_calls, expected, 'parseText')
        self.assertEqual(msg.method_calls, [], 'no reply')

    def test_Forward_PM_Answer(self):
        r = MagicMock()
        msg = MagicMock()
        msg.subreddit = None
        msg.author.name = credentials.admin_username
        msg.id = 'msgid2'
        msg.distinguished = None
        msg.subject = 're: #msgid1 /u/user: "sub"'
        msg.body = 'body'
        pmUserCache = { }

        helper = MagicMock()
        helper.parseText = MagicMock(return_value=([], 'text'))

        oldMsg = MagicMock()
        r.inbox.message = MagicMock(return_value=oldMsg)

        # test
        hsbot.answerPM(r, msg, pmUserCache, helper)

        self.assertTrue(msg.author.name not in pmUserCache, "don't admin")

        expected = [call.inbox.message('msgid1')]
        self.assertEqual(r.method_calls, expected, 'reddit call')

        expected = [call.message('msgid1')]
        self.assertEqual(r.inbox.method_calls, expected, 'get old msg')

        expected = [call.reply('body')]
        self.assertEqual(oldMsg.method_calls, expected, 'reply old')

        expected = [call.reply('answer forwarded')]
        self.assertEqual(msg.method_calls, expected, 'reply new')

        self.assertEqual(helper.method_calls, [], 'no helper calls')

    def test_CleamPMUserCache(self):
        future = int(time.time()) + 60
        cache = {"aaa": 123, "bbb": future}
        hsbot.cleanPMUserCache(cache)
        self.assertIsNone(cache.get("aaa"))
        self.assertEqual(cache["bbb"], future)


if __name__ == '__main__':
    removeFile("test.log")
    logging.basicConfig(filename="test.log",
            format='%(asctime)s %(levelname)s %(name)s %(message)s',
            level=logging.DEBUG)

    print("run 'test.py online' to test online scraping functionality")
    # lazy argv fix
    unittest.main(warnings='ignore', argv=[sys.argv[0]])
