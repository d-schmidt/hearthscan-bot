#!/usr/bin/env python3

import logging as log
import time

from cardDB import CardDB
from constants import Constants
from helper import HSHelper
from praww import RedditBot
import commentDB
import credentials
import formatter


# answer pms of the same user only every x seconds
PM_RATE_LIMIT = 60


def answerComment(r, comment, answeredDB, helper):
    """read and answer a comment"""

    cards, answer = helper.parseText(comment.body)

    if cards and answer:
        if answeredDB.exists(comment.parent_id, cards):
            # send pm instead of comment reply
            sub = comment.submission

            log.info("sending duplicate msg: %s with %s",
                    comment.author, cards)
            header = formatter.createDuplicateMsg(sub.title, sub.permalink)
            message = header + answer

            r.redditor(comment.author.name) \
                    .message('You requested cards in a comment', message)
        else:
            # reply to comment
            log.info("replying to comment: %s %s with %s",
                    comment.id, comment.author.name, cards)
            comment.reply(answer)


def answerMention(r, comment, answeredDB, helper):
    """read and answer a comment"""

    cards, answer = helper.parseText(comment.body)

    if cards and answer:
        if not answeredDB.exists(comment.parent_id, cards):
            # reply to comment
            log.info("replying to comment: %s %s with %s",
                    comment.id, comment.author.name, cards)
            comment.reply(answer)
    else:
        log.debug("forwarded mention with id: %s", comment.id)
        # forward mentions without cards to admin
        subject = '${} /u/{} in /r/{}/ "{}"'.format(comment.id, comment.author,
                comment.subreddit, comment.submission.title)
        r.redditor(credentials.admin_username).message(subject, comment.body)


def answerSubmission(submission, helper):
    """read and answer a submission"""

    text = submission.title

    if submission.is_self:
        text += ' ' + submission.selftext

    cards, answer = helper.parseText(submission.selftext)

    if cards and answer:
        log.info("replying to submission: %s %s with %s",
                submission.id, submission.author.name, cards)
        submission.reply(answer)


def answerPM(r, msg, pmUserCache, helper):
    """ read and answer a pm """

    subject_author = ""

    # subreddit mod pm
    if msg.subreddit:
        author = msg.subreddit.display_name
        subject_author += " /r/" + author

    if msg.author:
        author = msg.author.name
        subject_author += " /u/" + author

    log.debug("found message with id: %s from %s", msg.id, author)

    if msg.author and not msg.distinguished and author in pmUserCache:
        log.debug("user %s is in recent msg list", author)
        return

    if author == credentials.admin_username and msg.subject[:5] == 're: #':
        forwardPMAnswer(r, msg)
        return

    if author == credentials.admin_username and msg.subject[:5] == 're: $':
        forwardMentionAnswer(r, msg)
        return

    pmUserCache[author] = int(time.time()) + PM_RATE_LIMIT

    text = msg.subject + ' ' + msg.body
    cards, answer = helper.parseText(text)

    if cards:
        if 'info' in cards:
            answer = helper.getInfoText(author) + answer

        if answer:
            log.info("sending msg: %s with %s", author, cards)
            msg.reply(answer)
    else:
        # vip tags (mod, admin usw)
        if msg.distinguished:
            subject_author += " [" + msg.distinguished + "]"

        log.debug("forwarded message with id: %s", msg.id)
        # forward messages without cards to admin
        subject = '#{}{}: "{}"'.format(msg.id, subject_author, msg.subject)
        r.redditor(credentials.admin_username).message(subject, msg.body)


def forwardPMAnswer(r, answer_msg):
    """handle messages from bot admin which are answers to
    forwarded messages
    """
    first_space = answer_msg.subject.find(' ', 6)
    slice_to = first_space if first_space > 1 else len(answer_msg.subject)

    if slice_to > 5:
        old_message = r.inbox.message(answer_msg.subject[5:slice_to])

        if old_message:
            log.debug("forwarded answer to message id: %s", old_message.id)
            old_message.reply(answer_msg.body)
            answer_msg.reply("answer forwarded")


def forwardMentionAnswer(r, answer_msg):
    """handle messages from bot admin which are answers to
    forwarded mentions
    """
    first_space = answer_msg.subject.find(' ', 6)
    slice_to = first_space if first_space > 1 else len(answer_msg.subject)

    if slice_to > 5:
        src_comment = r.comment(answer_msg.subject[5:slice_to])

        if src_comment:
            log.debug("forwarded answer to comment id: %s", src_comment.id)
            src_comment.reply(answer_msg.body)
            answer_msg.reply("answer forwarded")


def cleanPMUserCache(cache):
    """ clean recent user msg cache """

    removeUser = []
    now = int(time.time())

    for user, utime in cache.items():
        if now > utime:
            log.debug("removing author %s from recent list", user)
            removeUser.append(user)

    for ku in removeUser:
        del cache[ku]


def main():
    log.debug('main() hearthscan-bot starting')

    # load constant values
    constants = Constants()
    # init answered comments sqlite DB
    answeredDB = commentDB.DB()
    # load card DB
    url = 'https://raw.githubusercontent.com/d-schmidt/hearthscan-bot/master/data/tempinfo.json'
    cardDB = CardDB(constants=constants, tempJSONUrl=url)
    # init hs helper for hearthstone stuff
    helper = HSHelper(cardDB, constants)
    # pm spam filter cache
    pmUserCache = {}

    def submissionListener(r, submission):
        answerSubmission(submission, helper)

    def commentListener(r, comment):
        answerComment(r, comment, answeredDB, helper)

    def mentionListener(r, comment):
        answerMention(r, comment, answeredDB, helper)

    def pmListener(r, message):
        answerPM(r, message, pmUserCache, helper)

    def postAction():
        cleanPMUserCache(pmUserCache)
        cardDB.refreshTemp()

    try:
        RedditBot(subreddits=credentials.subreddits, newLimit=250, connectAttempts=5) \
                .withSubmissionListener(submissionListener) \
                .withCommentListener(commentListener) \
                .withMentionListener(mentionListener) \
                .withPMListener(pmListener) \
                .run(postAction)
    except:
        log.exception('main() RedditBot failed unexpectedly')
    finally:
        log.warning('main() leaving hearthscan-bot')
        answeredDB.close()


if __name__ == "__main__":
    log.basicConfig(filename="bot.log",
                    format='%(asctime)s %(levelname)s %(module)s:%(name)s %(message)s',
                    level=log.DEBUG)

    log.getLogger('prawcore').setLevel(log.INFO)

    # start
    try:
        main()
    except:
        log.exception('main() failed unexpectedly')
        exit(1)