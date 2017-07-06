
import itertools
import json
import os
import string

import formatter


class CardDB:
    """Wrapper around a PRAW reddit instance."""

    def __init__(self, *,
            constants,
            cardJSON='cards.json',
            tokenJSON='tokens.json',
            tempJSON='tempinfo.json'):
        """Initialize an instance of CardDB.

        :param cardJSON: file containing cards
        :param tokenJSON: file containing tokens
        :param tempJSON: optional file containing more cards
        """
        self.constants = constants
        self.cardJSON = cardJSON
        self.tokenJSON = tokenJSON
        self.tempJSON = tempJSON

        self.tokens = []

        self.__db = {}
        self.__tempDate = 0
        self.__load()


    def __load(self):

        # load cards
        with open(self.cardJSON, 'r') as file:
            cards = json.load(file)
        with open(self.tokenJSON, 'r') as file:
            tokens = json.load(file)

        # json to db full of text
        for name, card in itertools.chain(cards.items(), tokens.items()):
            clean = CardDB.cleanName(name)
            if clean in self.__db:
                log.error("load() duplicate name, already in the db: %s",
                        clean)
                raise Exception('duplicate card')

            self.__db[clean] = formatter.createCardText(card, self.constants)

        self.tokens = [CardDB.cleanName(name) for name in tokens.keys()]

        # finally load temp file
        self.refreshTemp()


    def refreshTemp(self):
        """Reload cards from tempJSON and overwrite existing."""
        if not os.path.isfile(self.tempJSON):
            return

        currentDate = os.path.getmtime(self.tempJSON)

        if currentDate == self.__tempDate:
            return

        self.__tempDate = currentDate

        try:
            with open(self.tempJSON, 'r') as file:
                for name, card in json.load(file).items():
                    clean = CardDB.cleanName(name)
                    self.__db[clean] = formatter.createCardText(card,
                            self.constants)
        except Exception as e:
            log.debug("refreshTemp() failed: %s", e)


    def cleanName(name):
        """ignore all special characters, numbers, whitespace, case"""
        return ''.join(c for c in name.lower() if c in string.ascii_lowercase)


    def cardNames(self):
        """all cards currently in db"""
        return list(self.__db.keys())


    def __contains__(self, item):
        return item in self.__db

    def __getitem__(self, key):
        return self.__db[key]
