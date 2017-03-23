
import logging as log
import os
import sqlite3
import time

import praw
from praw.models import Message
import prawcore


def _now():
    return int(time.time())


class _SeenDB():
    """Bot caches seen things to not supply them twice to listeners."""

    def __init__(self, dbName = 'redditbot.db'):
        self.conn = sqlite3.connect(dbName)

        self.conn.execute("CREATE TABLE IF NOT EXISTS seen"
                            " (id TEXT NOT NULL,"
                            " created INTEGER(4) NOT NULL DEFAULT (strftime('%s','now')))")
        self.conn.execute('CREATE INDEX IF NOT EXISTS seen_idx ON seen (id)')
        self.conn.commit()

    def __str__(self):
        return repr(self.conn)

    def isSeen(self, thing):
        id = thing.fullname

        query = 'SELECT COUNT(1) FROM seen WHERE id = ?'
        cur = self.conn.execute(query, (id, ))
        count = cur.fetchone()[0]
        cur.close()

        seen = count >= 1

        if not seen:
            self.conn.execute("INSERT INTO seen (id) VALUES (?)", (id, ))
            self.conn.commit()

        return seen

    def cleanup(self, secondsOld = 24 * 60 * 60):
        timestamp = _now() - secondsOld
        self.conn.execute("DELETE FROM seen WHERE created <= ?", (timestamp, ))
        self.conn.commit()

    def close(self):
        self.conn.close()


class RedditBot:
    """Wrapper around a PRAW reddit instance.

    Create your own praw.ini
    [bot]
    client_id=see https://www.reddit.com/prefs/apps/
    client_secret=see https://www.reddit.com/prefs/apps/
    password=securepassword
    username=fakebot3
    user_agent=praw:hearthscanexample:1.0 (by /u/b0ne123)

    or if you want to use a proper refresh token
    [bot]
    client_id=https://www.reddit.com/prefs/apps/
    client_secret=https://www.reddit.com/prefs/apps/
    refresh_token=generatedrefreshtoken
    user_agent=praw:hearthscanexample:1.0 (by /u/b0ne123)
    """

    def __init__(self, subreddits, iniSite='bot',
            newLimit=25, sleep=30, connectAttempts=1,
            scopes=('submit', 'privatemessages', 'read', 'identity')):
        """Create an instance of Reddit. Does not yet connect.

        :param subreddits: list of subreddits to read
        :param iniSite: see PRAW config docs using praw.ini (default: bot)
        :param newLimit: number of entries to read (default: 25)
        :param sleep: read reddit every n seconds (default: 30)
        :param connectAttempts: attempt initial connection n times and
            sleep 2^n sec between attempts (default: 1)
        :param scopes: required scopes
        """
        self.__subreddits = '+'.join(subreddits)
        self.iniSite = iniSite
        self.newLimit = newLimit
        self.sleep = sleep
        self.connectAttempts = connectAttempts
        self.scopes = scopes

        self.rateSleep = 0
        self.roundStart = 0

        # use with() setter
        self.__commentListener = None
        self.__submissionListener = None
        self.__mentionListener = None
        self.__pmListener = None

    def withCommentListener(self, commentListener):
        """Set a commentListener function. Comments will not be repeated.
        http://praw.readthedocs.io/en/latest/code_overview/models/comment.html

        :param commentListener: function(redditInstance, comment)
        :return: self
        """
        self.__commentListener = commentListener
        return self

    def withSubmissionListener(self, submissionListener):
        """Set a submissionListener function. Submissions will not be repeated.
        http://praw.readthedocs.io/en/latest/code_overview/models/submission.html

        :param submissionListener: function(redditInstance, submission)
        :return: self
        """
        self.__submissionListener = submissionListener
        return self

    def withMentionListener(self, commentListener):
        """Set a mentionListener function. Comments will not be repeated.
        http://praw.readthedocs.io/en/latest/code_overview/models/comment.html

        :param commentListener: function(redditInstance, comment)
        :return: self
        """
        self.__mentionListener = commentListener
        return self

    def withPMListener(self, pmListener):
        """Set a pmListener function. PMs will not be repeated.
        http://praw.readthedocs.io/en/latest/code_overview/models/message.html

        :param pmListener: function(redditInstance, message)
        :return: self
        """
        self.__pmListener = pmListener
        return self

    def __sleep(self):
        try:
            if self.rateSleep > 0:
                time.sleep(self.rateSleep)
                self.rateSleep = 0
            else:
                secToSleep = _now() - self.roundStart
                time.sleep(self.sleep - min(self.sleep, secToSleep))
        except:
            # this is strange but not horrible
            log.exception('sleep() interrupted')


    def __connect(self):

        success = False
        connectTry = 1

        while not success:
            try:
                log.debug("connect() creating reddit adapter")
                self.r = praw.Reddit(self.iniSite)

                # connect and check if instance has required scopes
                for scope in self.scopes:
                    if scope not in self.r.auth.scopes():
                        raise Exception('reddit init missing scope', scope)

                self.me = self.r.user.me()
                log.debug('connect() logged into reddit as: %s', self.me)
                return

            except prawcore.exceptions.RequestException as e:
                log.exception('connect() failed to send request')

            if connectTry >= self.connectAttempts:
                log.error('connect() connection attempt %s failed', connectTry)
                raise Exception('failed to connect')

            log.warn('connect() connection attempt %s failed', connectTry)
            # sleep up to 2^try sec before failing (3 trys = 6s)
            time.sleep(2 ** connectTry)
            connectTry += 1



    def run(self, postRoundAction):
        """Run the bot forever (until 'lockfile.lock' is deleted).

        :param postRoundAction: function() to be called before sleep
        """
        log.basicConfig(format='%(asctime)s %(levelname)s %(name)s %(message)s',
                        level=log.DEBUG)

        # connect self to reddit
        self.__connect()

        # connecting to seen db
        self.__seenDB = _SeenDB()

        # wrap around doing stuff
        def do(things, listener):
            for thing in things:
                if self.__seenDB.isSeen(thing):
                    return
                if thing.author != self.me:
                    listener(self.r, thing)

        # create lockfile for simple, clean shutdown, delete the file to stop bot
        with open('lockfile.lock', 'w'): pass

        # main loop
        while os.path.isfile('lockfile.lock'):
            self.roundStart = _now()

            try:
                if self.__submissionListener:
                    subreddit = self.r.subreddit(self.__subreddits)
                    do(subreddit.new(limit=self.newLimit),
                            self.__submissionListener)

                if self.__commentListener:
                    subreddit = self.r.subreddit(self.__subreddits)
                    do(subreddit.comments(limit=self.newLimit),
                            self.__commentListener)

                if self.__mentionListener:
                    do(self.r.inbox.mentions(limit=self.newLimit),
                            self.__mentionListener)

                if self.__pmListener:
                    items = self.r.inbox.unread(mark_read=True,
                            limit=self.newLimit)

                    do((item for item in items if isinstance(item, Message)),
                            self.__commentListener)

            except praw.exceptions.APIException as e:
                # https://github.com/reddit/reddit/blob/master/r2/r2/lib/errors.py
                if 'RATELIMIT' in e.error_type:
                    reset = self.r.auth.limits.get('reset_timestamp')
                    if reset:
                        self.rateSleep = reset - _now() + 5

                    log.warn('run() rate exceeded, going to sleep %s',
                             self.rateSleep)
                else:
                    log.exception('run() reddit responded with error: %s', e)

            except prawcore.exceptions.PrawcoreException:
                # connection errors if bot or reddit is offline
                log.exception('run() error in core while redditing')

            # post round actions and sleep
            postRoundAction()
            self.__seenDB.cleanup()
            self.__sleep()

        # lock file is gone
        log.warning('run() leaving reddit-bot')
        self.__seenDB.close()
