
import sqlite3
import itertools
import time


class DB():

    def __init__(self, dbName = 'hscbot.db'):
        self.conn = sqlite3.connect(dbName)

        self.conn.execute("CREATE TABLE IF NOT EXISTS topcomment"
                            " (submission_id text, card text,"
                            " created integer(4) not null default (strftime('%s','now')))")
        self.conn.execute('CREATE INDEX IF NOT EXISTS sub_card_idx ON topcomment (submission_id, card)')

        self.conn.execute("CREATE TABLE IF NOT EXISTS seen_comment"
                            " (comment_id text,"
                            " created integer(4) not null default (strftime('%s','now')))")
        self.conn.execute('CREATE INDEX IF NOT EXISTS comment_idx ON seen_comment (comment_id)')

        self.conn.execute("CREATE TABLE IF NOT EXISTS seen_submission"
                            " (submission_id text,"
                            " created integer(4) not null default (strftime('%s','now')))")
        self.conn.execute('CREATE INDEX IF NOT EXISTS submission_idx ON seen_submission (submission_id)')
        self.conn.commit()


    def __str__(self):
        return repr(self.conn)


    def exists(self, submission_id, cards):
        # true if all cards are already posted for parent
        query = ('SELECT COUNT(1) FROM topcomment WHERE submission_id = ?'
                                ' AND card IN (%s)' % ','.join('?' * len(cards)))
        params = list(itertools.chain((submission_id,), cards))

        cur = self.conn.execute(query, params)
        count = cur.fetchone()[0]
        cur.close()
        return count >= len(cards)


    def insert(self, submission_id, card):
        self.conn.execute("INSERT INTO topcomment (submission_id, card) VALUES (?, ?)", (submission_id, card))
        self.conn.commit()


    def addSeenComment(self, comment_id):
        self.conn.execute("INSERT INTO seen_comment (comment_id) VALUES (?)", (comment_id, ))
        self.conn.commit()

    def isSeenComment(self, comment_id):
        query = 'SELECT COUNT(1) FROM seen_comment WHERE comment_id = ?'
        cur = self.conn.execute(query, [comment_id])
        count = cur.fetchone()[0]
        cur.close()
        return count >= 1

    def cleanupSeenComment(self, seconds_old = 24 * 60 * 60):
        timestamp = int(time.time()) - seconds_old
        self.conn.execute("DELETE FROM seen_comment WHERE created <= ?", (timestamp, ))
        self.conn.commit()


    def addSeenSubmission(self, submission_id):
        self.conn.execute("INSERT INTO seen_submission (submission_id) VALUES (?)", (submission_id, ))
        self.conn.commit()

    def isSeenSubmission(self, submission_id):
        query = 'SELECT COUNT(1) FROM seen_submission WHERE submission_id = ?'
        cur = self.conn.execute(query, [submission_id])
        count = cur.fetchone()[0]
        cur.close()
        return count >= 1

    def cleanupSeenSubmission(self, seconds_old = 24 * 60 * 60):
        timestamp = int(time.time()) - seconds_old
        self.conn.execute("DELETE FROM seen_submission WHERE created <= ?", (timestamp, ))
        self.conn.commit()


    def close(self):
        self.conn.close()
