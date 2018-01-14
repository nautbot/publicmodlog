# publicmodlog
Python script that will scrape Reddit moderation log entries and Automoderator configuration revisions, and post to a specified subreddit.

# Prerequisites
* Python 3.5
* PRAW (Python Reddit API Wrapper)
* Google Diff-Match-Patch

# Configuration
config_praw.json:
* "scanuser" - moderator credentials used to scrape the moderation log and wiki revisions;
* "loguser" - account that will be used to post the public log.

config_bot.json:
* "scansubreddit" - subreddit that will be scraped for moderation action entries;
* "logsubreddit" - subreddit where entries will be posted as a public moderation log.
