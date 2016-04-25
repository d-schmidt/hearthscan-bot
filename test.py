#!/usr/bin/python

import json
import logging
import os
import os.path
import sys
import time
import unittest
from unittest.mock import MagicMock

import praw
import requests

import scrape
import card_constants as cc
import commentDB
# I didn't know this before creating the test
hearthscan_bot = __import__("hearthscan-bot")
import helper
import special_cards as specials
import spelling


# start with 'test.py online' to start slow tests requiring internet and working credentials
SKIP_INTERNET_TESTS = len(sys.argv) < 2 or sys.argv[1] != "online"


def removeFile(path):
    """ error free file delete """
    if os.path.isfile(path):
        os.remove(path)


class TestScrape(unittest.TestCase):

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_hearthhead(self):
        with requests.Session() as s:
            self.assertEqual(scrape.getHearthHeadId('Quick Shot', 'Spell', s), 2260)
            self.assertEqual(scrape.getHearthHeadId('Undercity Valiant', 'Minion', s), 2767)
            self.assertEqual(scrape.getHearthHeadId('Gorehowl', 'Weapon', s), 810)

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_Hearthpwn(self):
        with requests.Session() as s:
            self.assertEqual(scrape.getHearthpwnIdAndUrl('Quick Shot', 'Blackrock Mountain', 'Spell', False, s),
                    (14459, 'http://media-Hearth.cursecdn.com/avatars/197/981/14459.png'))
            self.assertEqual(scrape.getHearthpwnIdAndUrl('Upgrade!', 'Classic', 'Spell', False, s),
                    (638, 'http://media-Hearth.cursecdn.com/avatars/285/274/635951439216665743.png'))

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_full(self):
        expected = {
            'Quick Shot': {
                'type': 'Spell',
                'hpwn': 14459,
                'cdn': 'http://media-Hearth.cursecdn.com/avatars/197/981/14459.png',
                'desc': 'Deal 3 damage. If your hand is empty, draw a card.',
                'hp': None,
                'class': 'Hunter',
                'subType': None,
                'set': 'Blackrock Mountain',
                'rarity': 'Common',
                'atk': None,
                'head': 2260,
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
                'cdn': 'http://media-Hearth.cursecdn.com/avatars/197/981/14459.png',
                'desc': 'Deal 3 damage. If your hand is empty, draw a card.',
                'hp': None,
                'class': 'Hunter',
                'subType': None,
                'set': 'Blackrock Mountain',
                'rarity': 'Common',
                'atk': None,
                'head': 2260,
                'name': 'Quick Shot',
                'cost': 2
            }
        }
        # scrape just one card
        wantedtokens = {
            "Quick Shot": {
                "id" : "BRM_013",
                "head": 2260,
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
    def test_JsonCards_textFormatFixer(self):
        cards, tokens = scrape.loadJsonCards()
        self.assertEqual(cards['LOE_079']['desc'],
                "Battlecry: Shuffle the 'Map to the Golden Monkey' into your deck.")
        self.assertEqual(cards['GVG_085']['desc'], "Taunt Divine Shield")
        self.assertEqual(cards['GVG_012']['desc'][:16], "Restore 3 Health")
        self.assertEqual(cards['EX1_279']['desc'], "Deal 10 damage.")
        self.assertEqual(cards['BRM_013']['desc'],
                "Deal 3 damage. If your hand is empty, draw a card.")
        self.assertEqual(cards['EX1_298']['desc'][:13], "Can't attack.")


class TestConst(unittest.TestCase):

    def test_ScrapeConstSetLength(self):
        # easy to miss one when a new set is added
        self.assertEqual(len(scrape.jsonToCCSet), len(cc.setdata))
        self.assertEqual(len(scrape.setids), len(cc.setdata))
        self.assertEqual(len(scrape.setNameIds), len(cc.setdata))
        self.assertEqual(len(cc.setorder), len(cc.setdata))


class TestCommentDB(unittest.TestCase):

    testDBName = "test.db"

    def test_CreateFindFailParent(self):
        removeFile(self.testDBName)

        db = commentDB.DB(self.testDBName)
        db.insert("abc", "a card")

        self.assertTrue(db.exists("abc", ["a card"]))
        self.assertFalse(db.exists("abc", ["b card"]))
        self.assertFalse(db.exists("123", ["a card"]))
        self.assertFalse(db.exists("abc", ["a card", "b card"]))

        db.close()
        removeFile(self.testDBName)

    def test_CreateFindFailSeenComment(self):
        removeFile(self.testDBName)

        db = commentDB.DB(self.testDBName)
        db.addSeenComment("aaa")

        self.assertTrue(db.isSeenComment("aaa"))
        self.assertFalse(db.isSeenComment("bbb"))
        db.cleanupSeenComment(0)
        self.assertFalse(db.isSeenComment("aaa"))

        db.close()
        removeFile(self.testDBName)

    def test_CreateFindFailSeenSubmission(self):
        removeFile(self.testDBName)

        db = commentDB.DB(self.testDBName)
        db.addSeenSubmission("aaa")

        self.assertTrue(db.isSeenSubmission("aaa"))
        self.assertFalse(db.isSeenSubmission("bbb"))
        db.cleanupSeenSubmission(0)
        self.assertFalse(db.isSeenSubmission("aaa"))

        db.close()
        removeFile(self.testDBName)


class TestHelper(unittest.TestCase):

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_Reddit(self):
        # will fail for missing/bad reddit auth
        r, next = helper.initReddit()
        helper.refreshReddit(r)

    @unittest.skipIf(SKIP_INTERNET_TESTS, "requires internet (and is slow)")
    def test_RedditFail(self):
        self.assertRaises(praw.errors.HTTPException, helper.initReddit,
                            "41234563-GFkHJ2bujhdVB265wST56bCCYTH")


    def test_RefreshFail(self):
        newReddit = praw.Reddit(user_agent="python/unittest/new_dummy")
        newReddit.send_message = MagicMock()
        helper.initReddit = MagicMock(return_value=(newReddit, 10))

        refresh = praw.Reddit(user_agent="python/unittest/old_dummy")
        refresh.refresh_access_information = MagicMock(side_effect=praw.errors.Forbidden(None))

        result, next = helper.refreshReddit(refresh)
        self.assertEqual(next, 10)
        self.assertIs(result, newReddit)


    def test_Cleaner(self):
        self.assertEqual(helper.cleanName("Ab: 1c"), "abc")

    def test_QuoteCleaner(self):
        self.assertEqual(helper.removeQuotes("> b\na\n> b\nc"), "a c")
        self.assertEqual(helper.removeQuotes("> abc"), "")

    def test_UpdateCardDB(self):
        info = {'Quick Shot': {
                        'type': 'Spell',
                        'hpwn': 14459,
                        'cdn': 'http://media-Hearth.cursecdn.com/14459.png',
                        'desc': 'Deal 3 damage. Draw a card.',
                        'hp': 1,
                        'class': 'Hunter',
                        'subType': "Mech",
                        'set': 'Blackrock Mountain',
                        'rarity': 'Common',
                        'atk': 3,
                        'head': 2260,
                        'name': 'Quick Shot',
                        'cost': 2
                        }
                    }

        helper.TEMP_FILE_NAME = 'dummytmp.json'
        with open(helper.TEMP_FILE_NAME, "w", newline="\n") as f:
            json.dump(info, f, sort_keys=True, indent=2, separators=(',', ':'))
        # this is tested
        db = helper.updateCardDB({})

        removeFile(helper.TEMP_FILE_NAME)
        self.assertEqual(len(db), 1)


    def test_createCardDB(self):
        info = {'Quick Shot': {
                    'type': 'Spell',
                    'hpwn': 14459,
                    'cdn': 'http://media-Hearth.cursecdn.com/14459.png',
                    'desc': 'Deal 3 damage. Draw a card.',
                    'hp': 1,
                    'class': 'Hunter',
                    'subType': "Mech",
                    'set': 'Blackrock Mountain',
                    'rarity': 'Common',
                    'atk': 3,
                    'head': 2260,
                    'name': 'Quick Shot',
                    'cost': 2
                    }
                }

        cleanName = helper.cleanName("Quick Shot")
        expected = ('* **[Quick Shot](http://media-Hearth.cursecdn.com/14459.png)**'
                        ' Spell Hunter Common BRM \U0001f419'
                        ' | [HP](http://www.hearthpwn.com/cards/14459),'
                        ' [HH](http://www.hearthhead.com/card=2260),'
                        ' [Wiki](http://hearthstone.gamepedia.com/Quick_Shot)  \n'
                    '2 Mana 3/1 Mech - Deal 3 damage. Draw a card.  \n')
        self.assertEqual(helper._createCardDB(info.items())[cleanName], expected)

    def test_getCardsFromComment_success(self):
        text = "[[test]] [[Ab 123c]]"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, ["test", "abc"])
        text = "[[ABC]]"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, ["abc"])
        text = "[[rag]]"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, ["ragnarosthefirelord"])

    def test_getCardsFromComment_success_spellcheck(self):
        checker = spelling.Checker(["ragnaros"])
        text = "[[ragnaro]]"
        result = helper.getCardsFromComment(text, checker)
        self.assertEqual(result, ["ragnarosthefirelord"])
        text = "[[raknaros]]"
        result = helper.getCardsFromComment(text, checker)
        self.assertEqual(result, ["ragnarosthefirelord"])
        text = "[[rangaros]]"
        result = helper.getCardsFromComment(text, checker)
        self.assertEqual(result, ["ragnarosthefirelord"])
        text = "[[ragnar]]"
        result = helper.getCardsFromComment(text, checker)
        self.assertEqual(result, ["ragnar"])

    def test_getCardsFromComment_textTooShort(self):
        text = "[[a]]"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, [])

    def test_getCardsFromComment_nameUseless(self):
        text = "[[123 456]]"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, [])

    def test_getCardsFromComment_notDoubleBracket(self):
        text = "[abc] test text"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, [])

    def test_getCardsFromComment_nameTooLong(self):
        text = "[[123456789012345678901234567890abc]] test text"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, [])

    def test_getCardsFromComment_limitIsSeven(self):
        text = "[[aaa]] [[bbb]] [[ccc]] [[ddd]] [[eee]] [[fff]] [[ggg]] [[hhh]]"
        result = helper.getCardsFromComment(text, spelling.Checker([]))
        self.assertEqual(result, ["aaa", "bbb", "ccc", "ddd", "eee", "fff", "ggg"])

    def test_loadInfoTempl_simple(self):
        helper.INFO_MSG_TMPL = 'dummytmpl.json'
        with open(helper.INFO_MSG_TMPL, "w", newline="\n") as f:
            f.write('{user} {alts} {tokens} {special}')

        loadedTempl = helper.loadInfoTempl(['sb', 'sa'], ['aa', 'ab'], ['ta', 'tb'])
        removeFile(helper.INFO_MSG_TMPL)
        self.assertEqual(loadedTempl, '{user} aa, ab ta, tb sa, sb')


class TestBot(unittest.TestCase):

    def test_AnswerMail_UserOnSpam(self):
        r = praw.Reddit(user_agent="python/unittest/dummy")

        raw2 = '{ "author": "Mr_X", "replies": "", "id": "abc", "was_comment": false }'
        msg = praw.objects.Message.from_api_response(r, json.loads(raw2))
        msg.mark_as_read = MagicMock()
        msg.reply = MagicMock()
        r.get_unread = MagicMock(return_value = [msg])

        # fails on msg.body if skip for user on spam is broken
        hearthscan_bot.answerPMs(r, {"Mr_X" : 1234}, {}, spelling.Checker([]))
        msg.mark_as_read.assert_any_call()
        msg.reply.assert_not_called()

    def test_AnswerMail_WasCommentNotMsg(self):
        r = praw.Reddit(user_agent="python/unittest/dummy")

        raw2 = '{ "replies": "", "id": "abc", "was_comment": true }'
        msg = praw.objects.Message.from_api_response(r, json.loads(raw2))
        msg.mark_as_read = MagicMock()
        msg.reply = MagicMock()
        r.get_unread = MagicMock(return_value = [msg])

        # fails on msg.author is accessed if skip for user on spam is broken
        hearthscan_bot.answerPMs(r, {}, {}, spelling.Checker([]))
        msg.mark_as_read.assert_any_call()
        msg.reply.assert_not_called()

    def test_AnswerMail_Success(self):
        r = praw.Reddit(user_agent="python/unittest/dummy")

        raw = '{ "body": "[[quick shot]]", "author": "Mr_X", "replies": "", "id": "abc", "subject": "test", "was_comment": false }'
        msg = praw.objects.Message.from_api_response(r, json.loads(raw))
        msg.mark_as_read = MagicMock()
        msg.reply = MagicMock()
        r.get_unread = MagicMock(return_value = [msg])

        db = {"quickshot": "dummy"}
        expected = "dummy" + helper.signature

        hearthscan_bot.answerPMs(r, {}, db, spelling.Checker([]))
        msg.mark_as_read.assert_any_call()
        msg.reply.assert_called_with(expected)

    def test_CleamPMUserCache(self):
        future = int(time.time()) + 60
        cache = {"aaa": 123, "bbb": future}
        hearthscan_bot.cleanPMUserCache(cache)
        self.assertIsNone(cache.get("aaa"))
        self.assertEqual(cache["bbb"], future)


class TestSpelling(unittest.TestCase):

    def test_Spellchecker(self):
        checker = spelling.Checker(["abcdef"])
        self.assertEqual(checker.correct("abcdef"), "abcdef")
        self.assertEqual(checker.correct("abcde"), "abcdef")
        self.assertEqual(checker.correct("bcdef"), "abcdef")
        self.assertEqual(checker.correct("acdef"), "abcdef")
        self.assertEqual(checker.correct("bacdef"), "abcdef")
        self.assertEqual(checker.correct("abcdeg"), "abcdef")
        self.assertEqual(checker.correct("aabcdef"), "abcdef")
        # only distance 1 errors are fixed
        self.assertEqual(checker.correct("abcd"), "abcd")


class TestSpecials(unittest.TestCase):

    def test_Replacements(self):
        replaced = specials.replace(["abc", "dreamcards", "def", "ghi"])
        # tests replace and maxlength
        self.assertEqual(replaced, ["abc",
                                     "dream",
                                     "emeralddrake",
                                     "laughingsister",
                                     "nightmare",
                                     "yseraawakens",
                                     "def"])


if __name__ == '__main__':
    removeFile("test.log")
    logging.basicConfig(filename="test.log",
            format='%(asctime)s %(levelname)s %(message)s',
            level=logging.DEBUG)

    # lazy argv fix
    unittest.main(warnings='ignore', argv=[sys.argv[0]])
