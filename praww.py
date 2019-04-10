
import logging as log
import os
import signal
import sqlite3
import sys
import time

import praw
from praw.models import Message, Comment
import prawcore


def _now():
    return int(time.time())


class _SeenDB():
    """Bot caches seen things to not supply them twice to listeners."""

    def __init__(self, dbName = 'praww.db'):
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
    LOCK_FILE = 'lockfile.lock'


    def __init__(self, *, subreddits, iniSite='bot',
            newLimit=25, sleep=30, connectAttempts=1,
            scopes=('submit', 'privatemessages', 'read', 'identity'),
            dbName='praww.db',
            userBlacklist=[]):
        """Create an instance of Reddit. Does not yet connect.

        :param subreddits: list of subreddits to read
        :param iniSite: see PRAW config docs using praw.ini (default: bot)
        :param newLimit: number of entries to read (default: 25)
        :param sleep: read reddit every n seconds (default: 30)
        :param connectAttempts: attempt initial connection n times and
            sleep 2^n sec between attempts (default: 1)
        :param scopes: required scopes
        :param dbName: name of file of seen-things db
        :param userBlacklist: users to ignore
        """
        self.killed = False
        signal.signal(signal.SIGTERM, self.__catchKill)

        self.__subreddits = '+'.join(subreddits)
        self.iniSite = iniSite
        self.newLimit = newLimit
        self.sleep = sleep
        self.connectAttempts = connectAttempts
        self.scopes = scopes
        self.dbName = dbName
        self.userBlacklist = userBlacklist

        self.rateSleep = 0
        self.roundStart = 0

        # restart after 15 min of consecutive fails
        self.__failLimit = 15*60 // max(sleep, 1)
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


    def __catchKill(self, signum, frame):
        log.debug("catchKill() triggered")
        self.killed = True


    def __sleep(self):
        if self.rateSleep > 0:
            seconds = self.rateSleep
            self.rateSleep = 0
        else:
            roundSecs = _now() - self.roundStart
            seconds = self.sleep - min(self.sleep, roundSecs)

        for i in range(int(seconds)):
            if self.killed:
                return
            time.sleep(1)


    def __connect(self):

        connectTry = 1

        while True:
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
            for s in range(2 ** connectTry):
                if self.killed:
                    raise Exception('killed')
                time.sleep(1)

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
        self.__seenDB = _SeenDB(self.dbName)

        # wrap around doing stuff
        def do(things, listener):
            for thing in things:
                if self.killed or self.__seenDB.isSeen(thing):
                    return
                if (isinstance(thing, praw.models.Submission) or thing.author != self.me) \
                        and thing.author not in self.userBlacklist:
                    listener(self.r, thing)

        # create lockfile for clean shutdown, delete the file to stop bot
        with open(self.LOCK_FILE, 'w'): pass

        # count consecutive fails
        failCount = 0

        # main loop
        while os.path.isfile(self.LOCK_FILE) and not self.killed:
            self.roundStart = _now()

            try:
                if self.__submissionListener:
                    subreddit = self.r.subreddit(self.__subreddits)
                    do(subreddit.new(limit=self.newLimit),
                            self.__submissionListener)

                if self.__commentListener and not self.killed:
                    subreddit = self.r.subreddit(self.__subreddits)
                    do(subreddit.comments(limit=self.newLimit),
                            self.__commentListener)

                if (self.__pmListener or self.__mentionListener) and not self.killed:
                    items = list(self.r.inbox.unread(mark_read=True,
                            limit=self.newLimit))

                    for someitems in _partition(items, 100):
                        self.r.inbox.mark_read(someitems)

                    # pm
                    if self.__pmListener:
                        do((item for item in items if isinstance(item, Message)),
                                self.__pmListener)
                    # mention
                    if self.__mentionListener:
                        for item in items:
                            if isinstance(item, Comment):
                                if item.subject == "username mention":
                                    do([item], self.__mentionListener)

                # post round actions
                if not self.killed:
                    postRoundAction()
                    self.__seenDB.cleanup()

                # success, reset fails
                failCount = 0

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
                failCount += 1

                if failCount >= self.__failLimit:
                    # some error/python version/praw version combinations never recover
                    log.error('run() consecutive fails reached limit, leaving to restart')
                    self.killed = True

            except KeyboardInterrupt:
                log.warn('run() interrupt, leaving')
                self.killed = True

            # sleep before next round/attempt
            if not self.killed:
                self.__sleep()
            # while end

        # lock file is gone or killed
        log.warning('run() leaving reddit-bot')
        self.__seenDB.close()


def _partition(sequence, chunksize):
    """break a long iterable down into smaller lists"""
    result = []
    another = None
    second = False

    for item in sequence:
        if second:
            result.append(another)
            if len(result) >= chunksize:
                yield result
                result = []
        another = item
        second = True

    if second:
        result.append(another)

    yield result
