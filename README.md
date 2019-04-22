<p align="center"><img src="/logo/logotype-horizontal.png"></p>

# hearthscan-bot
Explaining cards in [reddit.com/r/hearthstone](https://www.reddit.com/r/hearthstone/).  
To see the bot in action send a PM containing `[[Ragnaros]]` to [/u/hearthscan-bot](https://www.reddit.com/message/compose/?to=hearthscan-bot)

## Requirements
- tested on Python 3.4+
- Python libraries: `requests`, `praw`, `lxml`
- [Reddit API](https://www.reddit.com/prefs/apps/) id, secret and refresh-token

## Tests
To run the offline unit tests; clone this repo and:
```
pip install -r requirements.txt

copy credentials.py.example credentials.py
copy praw.ini.example praw.ini
python3 test.py
```
To run the full tests, prepare your own `credentials.py` and `praw.ini` and start tests using `python3 test.py online`.  
The test creates a `test.log`.

## Running the bot
**Make sure the online test is successful!**  
I use the `start.sh` on my PI to run in background.  
If you want to start it without script, no parameters are required to start it (`python3 hearthscan-bot.py`).  
The script pipes startup errors to `std.txt` and `err.txt`. The bot logs to `bot.log` once it is running.

There are JSON files included in this repository. If you want current data you can always recreate them using `scrape.py`.  

While the bot is running, you can teach it new cards without stopping it. Create or edit `tempinfo.json` in the data-directory or edit it in this git repository.

Delete the `lockfile.lock` or `kill` it on Linux to stop the bot gracefully.

## Learning from this bot
A good starting point is `hearthscan-bot.py/main()`. I've tried to comment the code and use consistent, self explaining names.  
There are nice people out there answering questions ([/r/learnpython](https://www.reddit.com/r/learnpython), [/r/redditdev](https://www.reddit.com/r/redditdev)) and the [PRAW documentation](http://praw.readthedocs.io/en/latest/getting_started/quick_start.html) is decent.

## License
All code contained here is licensed by [MIT](https://github.com/d-schmidt/hearthscan-bot/blob/master/LICENSE).
