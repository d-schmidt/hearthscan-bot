
import string
import itertools

"""
# distance 2
def known_edits2(word):
    print("known_edits2")
    return set(e2 for e1 in edits1(word) for e2 in edits1(e1) if e2 in NWORDS)
"""

class Checker():
    """
    based on Peter Norvig - http://norvig.com/spell-correct.html
    """
    def __init__(self, names):
        self.model = set(names)

    def _known(self, words):
        for w in words:
            if w in self.model:
                return w
        return None

    def _edits(self, word):
        splits     = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes    = (a + b[1:] for a, b in splits if b)
        transposes = (a + b[1] + b[0] + b[2:] for a, b in splits if len(b)>1)
        replaces   = (a + c + b[1:] for a, b in splits for c in string.ascii_lowercase if b)
        inserts    = (a + c + b     for a, b in splits for c in string.ascii_lowercase)
        return itertools.chain(deletes, transposes, replaces, inserts)

    def correct(self, word):
        """ returns input word or fixed version if found """
        return self._known([word]) or self._known(self._edits(word)) or word
