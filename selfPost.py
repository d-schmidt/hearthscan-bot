#!/usr/bin/env python3

import fileinput

import praw

import credentials

# block in praw.ini
r = praw.Reddit('bot')
# bot name
sub = r.subreddit('u_' + credentials.username)

title = ''
selftext = ''

# first text line is used for title
# following lines are use for text
for line in fileinput.input():
    line = line.rstrip()
    if not title and line:
        title = line
    else:
        if line or selftext:
            selftext += line
            selftext += '\n'

if title:
    print("title: '{}'\nselftext: '{}'".format(title, selftext))
    sub.submit(title, selftext=selftext)