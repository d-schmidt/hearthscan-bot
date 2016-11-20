#!/usr/bin/python

import itertools
import json
import logging as log
import os
import os.path
import time

import praw

import alt_cards as ac
import commentDB
import credentials
import helper
import special_cards as specials
import spelling

info_body_templ = None
duplicate_header_templ = ("You've posted a comment reply in [{title}]({url}) "
                            "with cards I already explained there. "
                            "Here are the cards just for you:\n\n")
forward_subject_templ = '#{}{}: "{}"'

# start all actions once every x seconds
# praw GET has a 20 sec cache, always sleep more seconds
SLEEP_SECS = 30
# answer pms of the same user only every x seconds
# r.get_unread response might be cached, you might get the same message twice
# this is why pm_rate_limit has to be > 1 cycle (30 sec)
pm_rate_limit = 60

SUBS_STRING = '+'.join(credentials.subreddits)


def answerComments(r, db, card_db, spell_check):
    """ read and answer comments """

    comments = r.get_subreddit(SUBS_STRING).get_comments(limit=250)
    # testing
    #comments = r.get_subreddit('sandboxtest').get_comments(limit=10)
    #comments = r.get_submission(submission_id='12345').comments
    #comments = r.get_submission('https://www.reddit.com/r/hearthstone/comments/12345/_/1234').comments

    for comment in comments:
        if db.isSeenComment(comment.id):
            break
        db.addSeenComment(comment.id)

        if comment.author.name == credentials.username:
            continue

        body = helper.removeQuotes(comment.body)
        cards = helper.getCardsFromComment(body, spell_check)
        if cards:
            log.debug("found cards: %s", cards)
            cards = specials.replace(cards)
            comment_text = helper.getTextForCards(card_db, cards)

            if comment_text:
                if db.exists(comment.parent_id, cards):
                    #send pm instead of comment reply
                    sub = comment.submission
                    log.info("sending duplicate msg: %s with %s", comment.author, cards)
                    header = duplicate_header_templ.format(title=sub.title, url=sub.permalink)
                    msg_text = header + comment_text
                    r.send_message(comment.author, 'You requested cards in a comment', msg_text)
                else:
                    # reply to comment
                    for card in cards:
                        db.insert(comment.parent_id, card)
                    log.info("replying to comment: %s %s with %s", comment.id, comment.author.name, cards)
                    comment.reply(comment_text)


def answerSubmissions(r, db, card_db, spell_check):
    """ read and answer submissions """

    submissions = r.get_subreddit(SUBS_STRING).get_new(limit=20)

    for submission in submissions:
        if db.isSeenSubmission(submission.id):
            break
        db.addSeenSubmission(submission.id)

        if submission.author.name == credentials.username:
            continue
        if not submission.is_self:
            continue

        cards = helper.getCardsFromComment(submission.selftext, spell_check)
        if cards:
            log.debug("found cards: %s", cards)
            cards = specials.replace(cards)
            comment_text = helper.getTextForCards(card_db, cards)

            if comment_text:
                # reply to submission
                log.info("replying to submission: %s %s with %s", submission.id, submission.author.name, cards)
                submission.add_comment(comment_text)


def forwardAnswer(r, answer_msg):
    """ handle messages from admin which are answers to forwarded messages """
    first_space = answer_msg.subject.find(' ', 6)
    slice_to = first_space if first_space > 1 else len(answer_msg.subject)

    if slice_to > 5:
        old_message = r.get_message(answer_msg.subject[5:slice_to])

        if old_message:
            log.debug("forwarded answer to id: %s", old_message.id)
            old_message.reply(answer_msg.body)
            answer_msg.reply("answer forwarded")


def answerPMs(r, pm_user_cache, card_db, spell_check):
    """ read and answer pms """

    for msg in r.get_unread(unset_has_mail=True, update_user=True):

        msg.mark_as_read()

        if msg.was_comment:
            # ignore replies to our own comments
            continue

        subject_author = ""

        if msg.subreddit:
            author = msg.subreddit.display_name
            subject_author += " /r/" + author

        if msg.author:
            author = msg.author.name
            subject_author += " /u/" + author

        if msg.distinguished:
            subject_author += " [" + msg.distinguished + "]"

        log.debug("found message with id: %s from %s", msg.id, author)

        if msg.author and not msg.distinguished and author in pm_user_cache:
            log.debug("user %s is in recent msg list", author)
            continue

        pm_user_cache[author] = int(time.time()) + pm_rate_limit

        if author == credentials.admin_username and msg.subject[:5] == 're: #':
            forwardAnswer(r, msg)
            continue

        cards = helper.getCardsFromComment(msg.body, spell_check)
        for card in helper.getCardsFromComment(msg.subject, spell_check):
            if card not in cards:
                cards.append(card)

        if cards:
            log.debug("found cards: %s", cards)
            cards = specials.replace(cards)

            msg_text = helper.getTextForCards(card_db, cards)
            if 'info' in cards and info_body_templ:
                msg_text = info_body_templ.format(user=author) + msg_text

            if msg_text:
                log.info("sending msg: %s with %s", author, cards)
                msg.reply(msg_text)
        else:
            log.debug("forwarded message with id: %s", msg.id)
            # forward messages without cards to admin
            subject = forward_subject_templ.format(msg.id, subject_author, msg.subject)
            r.send_message(credentials.admin_username,
                           subject,
                           msg.body)


def cleanPMUserCache(cache):
    """ clean recent user msg cache """

    now = int(time.time())
    kill_user = []

    for user, utime in cache.items():
        if now > utime:
            log.debug("removing author %s from recent list", user)
            kill_user.append(user)

    for ku in kill_user:
        del cache[ku]


def sleep(round_start, rate_sleep):
    try:
        if rate_sleep > 0:
            time.sleep(rate_sleep)
        else:
            time.sleep(SLEEP_SECS - min(SLEEP_SECS, int(time.time()) - round_start))
    except:
        # this is strange but not horrible, page is cached so nothing really happens
        log.exception('sleep interrupted')


def main():
    log.debug("reddit bot reader starting")

    # init reddit
    r, next_auth_time = helper.initReddit()
    # init sqlite db
    db = commentDB.DB()
    # load card db
    card_db = helper.loadCardDB()
    # init spellchecker with all card names and alternatives
    spell_check = spelling.Checker(itertools.chain(card_db.keys(),
                                                   ac.translations.keys(),
                                                   specials.CMDS))
    # load info message template
    global info_body_templ
    info_body_templ = helper.loadInfoTempl(specials.CMDS)
    # pm spam filter cache
    pm_user_cache = {}
    # create lockfile for simple, clean shutdown, delete the file to stop bot
    with open('lockfile.lock', 'w'): pass

    # actual main loop
    while os.path.isfile('lockfile.lock'):
        rate_sleep = 0
        round_start = int(time.time())
        try:
            # do we need to refresh token?
            if round_start > next_auth_time:
                r, next_auth_time = helper.refreshReddit(r)

            answerComments(r, db, card_db, spell_check)
            answerSubmissions(r, db, card_db, spell_check)
            answerPMs(r, pm_user_cache, card_db, spell_check)

        except praw.errors.RateLimitExceeded as rle:
            # happens a lot for accounts without email, <10 days old and few points
            log.warn("rate exceeded, going to sleep for a long time %s", rle.sleep_time)
            rate_sleep = rle.sleep_time
        except:
            # it's bad practice to catch all but we want to keep running 4ever
            # this will catch all the connection (reddit maintainance) errors
            log.exception('something went wrong while redditing')

        cleanPMUserCache(pm_user_cache)
        db.cleanupSeenComment()
        db.cleanupSeenSubmission()
        card_db = helper.updateCardDB(card_db)
        sleep(round_start, rate_sleep)

    log.warning('leaving hearthscan-bot')
    db.close()


if __name__ == "__main__":
    log.basicConfig(filename="bot.log",
                    format='%(asctime)s %(levelname)s %(message)s',
                    level=log.DEBUG)
    main()