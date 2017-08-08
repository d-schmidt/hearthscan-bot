
import json

from cardDB import CardDB


class Constants():
    """wraps all constant data"""
    CARD_LIMIT = 7

    def __init__(self, constantJSON='data/constants.json'):
        with open(constantJSON, 'r', encoding='utf8') as file:
            constants = json.load(file)

        # set informations
        self.sets = constants['sets']
        self.setIds = {}
        for id, setDetails in self.sets.items():
            self.setIds[setDetails['name']] = id

        # special keywords to replace
        self.__specials = {}
        for key, values in constants['specials'].items():
            cards = [CardDB.cleanName(card) for card in values]
            self.__specials[CardDB.cleanName(key)] = cards

        self.specialNames = self.__specials.keys()

        # alternative card names
        self.__translations = {}
        for key, alts in constants['alternative_names'].items():
            org = CardDB.cleanName(key)

            if isinstance(alts, list):
                for alt in alts:
                    self.__translations[CardDB.cleanName(alt)] = org
            else:
                self.__translations[CardDB.cleanName(alts)] = org

        self.alternativeNames = self.__translations.keys()


    def replaceSpecial(self, cards):
        """replace all special keyword cards in list"""
        result = []
        for card in cards:
            if card in self.__specials:
                result.extend(self.__specials[card])
            else:
                result.append(card)

        return result[:self.CARD_LIMIT]


    def translateAlt(self, card):
        """translate alternative card name or return card"""
        return self.__translations.get(card, card)