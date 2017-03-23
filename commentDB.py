
import sqlite3
import itertools


class DB():
    """Keep track of parent comments to reduce duplicates.
    Often when a user mentions cards multiple people send
    the same request for the bot to explain the cards.
    """

    def __init__(self, dbName = 'hscbot.db'):
        self.conn = sqlite3.connect(dbName)

        self.conn.execute("CREATE TABLE IF NOT EXISTS topcomment"
                            " (submission_id text, card text,"
                            " created integer(4) not null default (strftime('%s','now')))")
        self.conn.execute('CREATE INDEX IF NOT EXISTS sub_card_idx ON topcomment (submission_id, card)')

        self.conn.commit()

    def __str__(self):
        return repr(self.conn)

    def exists(self, submission_id, cards):
        """Test if request is a duplicate and inserts new
        :return: true if all cards are already posted for parent
        """
        query = ('SELECT card FROM topcomment '
                    ' WHERE submission_id = ?'
                    ' AND card IN (%s)' % ','.join('?' * len(cards)))
        params = list(itertools.chain((submission_id,), cards))

        foundCards = [row[0] for row in self.conn.execute(query, params)]
        inserted = False

        for card in cards:
            if card not in foundCards:
                inserted = True
                self.conn.execute("INSERT INTO topcomment (submission_id, card) VALUES (?, ?)",
                    (submission_id, card))

        self.conn.commit()

        return not inserted

    def close(self):
        self.conn.close()
