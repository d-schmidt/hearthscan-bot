# hearthscan-bot
Explaining cards in [reddit.com/r/hearthstone](https://www.reddit.com/r/hearthstone/).  
To see the bot in action send a PM containing `[[Ragnaros]]` to [/u/hearthscan-bot](https://www.reddit.com/message/compose/?to=hearthscan-bot)

## Requirements
- tested with Python 3.4+
- libraries used: `requests`, `praw`, `lxml`
- [Reddit API](https://www.reddit.com/prefs/apps/) id, secret and refresh token

## Tests
To run the offline unit tests; clone this repo and:
```
pip install requests
pip install praw
pip install lxml

copy credentials.py.example credentials.py
python3 test.py
```
To run the full tests, prepare out your `credentials.py` and start tests with `python3 test.py online`.  
The test creates a `test.log`.

## Running the bot
**Make sure the online test is successful!**  
I use the `start.sh` on my PI to run in background.  
If you want to start it without, no parameters are required (`python3 hearthscan-bot.py`).  
The script pipes startup errors to `std.txt` and `err.txt`. The bot logs to `bot.log` once it is running.

You will require json-data for the bot to work. Start the `scrape.py` and wait or create the two data files yourself.
Create a `cards.json` and a `tokens.json` and add a card in the format:
```
{
  "Abomination": {
    "atk": 4,
    "cdn": "http://media-Hearth.cursecdn.com/avatars/147/945/597.png",
    "class": "Neutral",
    "cost": 5,
    "desc": "Taunt. Deathrattle: Deal 2 damage to ALL characters.",
    "head": 440,
    "hp": 4,
    "hpwn": 597,
    "name": "Abomination",
    "rarity": "Rare",
    "set": "Classic",
    "subType": null,
    "type": "Minion"
  },
  ...
}
```
Cards are not required in the files, but both files have to exists and contain valid json: `{}`.  
While the bot is running, you can teach it new cards without stopping. Create or edit `tempinfo.json` following the same format.

Delete the `lockfile.lock` to stop the bot gracefully.

## Learning from this bot
A good starting point is `hearthscan-bot.py/main()`. I've tried to comment the code and use self explaining names. I know the naming format is inconsistent, sorry about that.  
There are nice people out there answering questions ([/r/learnpython](https://www.reddit.com/r/learnpython), [/r/redditdev](https://www.reddit.com/r/redditdev)) and the [PRAW documentation](https://praw.readthedocs.org/en/stable/pages/writing_a_bot.html) is decent.

## License
All code contained here is licensed by [MIT](https://github.com/d-schmidt/hearthscan-bot/blob/master/LICENSE).
