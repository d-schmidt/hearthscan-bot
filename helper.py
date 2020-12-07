
import io
import itertools
import json
import logging as log
import re
import string

import credentials
import formatter
from cardDB import CardDB


class SpellChecker():
    """Find and fix simple spelling errors.
    based on Peter Norvig
    https://norvig.com/spell-correct.html
    """
    def __init__(self, names):
        self.model = set(name.lower() for name in names)

    def __known(self, words):
        for w in words:
            if w in self.model:
                return w
        return None

    def __edits(self, word):
        splits     = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes    = (a + b[1:] for a, b in splits if b)
        transposes = (a + b[1] + b[0] + b[2:] for a, b in splits if len(b)>1)
        replaces   = (a + c + b[1:] for a, b in splits for c in string.ascii_lowercase if b)
        inserts    = (a + c + b     for a, b in splits for c in string.ascii_lowercase)
        return itertools.chain(deletes, transposes, replaces, inserts)

    def __edits2(self, word):
        # distance 2 errors
        # insert: or self.__known(self.__edits2(lword))
        return set(e2 for e1 in self.__edits(word) for e2 in self.__edits(e1))

    def correct(self, word):
        """returns input word or fixed version if found"""
        lword = word.lower()
        return self.__known([lword]) or self.__known(self.__edits(lword)) or word


class HSHelper:
    """some convenience methods and wraps cardDB"""

    def __init__(self, cardDB, constants):
        self.cardDB = cardDB
        self.constants = constants

        allNames = itertools.chain(cardDB.cardNames(),
                self.constants.specialNames,
                self.constants.alternativeNames)
        self.spellChecker = SpellChecker(allNames)

        self.infoTempl = formatter.loadInfoTempl(self.constants.specialNames,
            self.constants.alternativeNames,
            cardDB.tokens,
            cardDB.DUELS_CMD)

    def getInfoText(self, author):
        """fill info request answer template"""
        return self.infoTempl.format(user=author)

    def parseText(self, text):
        """returns found cards and answer text"""
        text = HSHelper.removeQuotes(text)
        cards = self.__getCards(text)
        answer = ''

        if cards:
            log.debug("found cards: %s", cards)
            cards = self.constants.replaceSpecial(cards) #expand
            cards = [card for card in cards if card in self.cardDB]
            cards = cards[:self.constants.CARD_LIMIT]
            answer = formatter.createAnswer(self.cardDB, cards)

        return cards, answer

    def removeQuotes(text):
        """removes quote blocks"""
        lines = []
        for line in io.StringIO(text):
            line = line.strip()
            if line and line[0] != '>':
                lines.append(line)

        return ' '.join(lines)

    def __getCards(self, text):
        """look for [[cardname]]s in text and collect them"""
        cards = []
        if len(text) < 6:
            return cards

        # regex for escaped (new reddit and some apps) and unescaped brackets
        for card in re.finditer(r'\\?\[\\?\[([^\]\\]{1,32})\\?\]\\?\]', text):
            card = card.group(1)
            log.debug("adding a card: %s", card)
            duelsRequested = card.startswith(self.cardDB.DUELS_CMD)
            if duelsRequested:
                card = card[len(self.cardDB.DUELS_CMD):]
            cleanCard = CardDB.cleanName(card)

            if cleanCard:
                log.debug("cleaned card name: %s", cleanCard)
                # slight spelling error?
                checkedCard = self.spellChecker.correct(cleanCard)
                if cleanCard != checkedCard:
                    log.info("spelling fixed: %s -> %s",
                        cleanCard, checkedCard)

                # is alternative name?
                checkedCard = self.constants.translateAlt(checkedCard)

                # add cardname
                if checkedCard not in cards:
                    if duelsRequested:
                        checkedCard = self.cardDB.DUELS_CMD + checkedCard
                    cards.append(checkedCard)
                else:
                    log.info("duplicate card: %s", card)

            # sometimes cards are removed, get more to fill limit
            if len(cards) >= self.constants.CARD_LIMIT * 2:
                break

        return cards
