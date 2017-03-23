
import json


class Constants():
    """wraps all constant data"""
    CARD_LIMIT = 7

    def __init__(self, constantJSON='constants.json'):
        with open(constantJSON, 'r') as file:
            constants = json.load(file)

        # set informations
        self.sets = constants['sets']
        self.setIds = {}
        for id, setDetails in self.sets.items():
            self.setIds[setDetails['name']] = id

        # special keywords to replace
        self.__specials = constants['specials']
        self.specialNames = self.__specials.keys()

        # alternative card names
        self.__translations = {}
        for org, alts in constants['alternative_names'].items():
            if isinstance(alts, list):
                for alt in alts:
                    self.__translations[alt] = org
            else:
                self.__translations[alts] = org

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