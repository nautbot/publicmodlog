import datetime, time, json
import praw, praw.exceptions, prawcore, prawcore.exceptions
import diff_match_patch
import sqlite3

# Load PRAW settings
with open('config_praw.json') as settings_praw_file:
    settings_praw = json.load(settings_praw_file)

# Load bot settings
with open('config_bot.json') as settings_bot_file:
    settings_bot = json.load(settings_bot_file)

# Console reporting commands
def log_appevent(message):
    print('{} - {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message))

# Application info
bot_version = settings_praw['loguser']['version']
username = settings_praw['loguser']['username']
log_appevent('{} - version {}'.format(username, bot_version))

# Configure SQL tables
sql = sqlite3.connect('sql.db')
log_appevent('Loaded SQL Database')
cur = sql.cursor()
cur.execute('PRAGMA journal_mode=WAL;')
cur.execute('CREATE TABLE IF NOT EXISTS processed(id TEXT)')
log_appevent('Loaded Actions')
sql.commit()

# Log in to reddit
rs = praw.Reddit(
    client_id=settings_praw['scanuser']['client_id'],
    client_secret=settings_praw['scanuser']['client_secret'],
    redirect=settings_praw['scanuser']['redirect'],
    username=settings_praw['scanuser']['username'],
    password=settings_praw['scanuser']['password'],
    user_agent='python:com.nauticalmile.{0}.{1}:v{2} (by /u/{3})'.format(settings_praw['scanuser']['username'], 'PublicModerationLog', bot_version, settings_praw['scanuser']['username'])
)
log_appevent('Logged in to reddit as: python:com.nauticalmile.{0}.{1}:v{2} (by /u/{3})'.format(settings_praw['scanuser']['username'], 'PublicModerationLog', bot_version, settings_praw['scanuser']['username']))
rl = praw.Reddit(
    client_id=settings_praw['loguser']['client_id'],
    client_secret=settings_praw['loguser']['client_secret'],
    redirect=settings_praw['loguser']['redirect'],
    username=settings_praw['loguser']['username'],
    password=settings_praw['loguser']['password'],
    user_agent='python:com.nauticalmile.{0}.{1}:v{2} (by /u/{3})'.format(settings_praw['loguser']['username'], 'PublicModerationLog', bot_version, settings_praw['scanuser']['username'])
)
log_appevent('Logged in to reddit as: python:com.nauticalmile.{0}.{1}:v{2} (by /u/{3})'.format(settings_praw['loguser']['username'], 'PublicModerationLog', bot_version, settings_praw['scanuser']['username']))

# Misc variables
firstRun = True
dmp = diff_match_patch.diff_match_patch()
processed_modlogitems = []
processed_wikichanges = []

# Post title and body formats
modlog_title_format = 'New Moderation Action - {0} - {1} UTC'
modlog_body_format = 'moderator : {0}\n\n\
action : {1}\n\n\
redditor: {2}\n\n\
target title: {3}\n\n\
target body: {4}\n\n\
target permalink: {5}'
automod_title_format = 'New Automoderator Revision - {0} UTC'

class ModerationItem():
    Type = 0
    Moderator = ''
    Action = ''
    Reason = ''
    TargetUser = ''
    TargetTitle = ''
    TargetBody = ''
    TargetPermalink = ''
    Timestamp = 0
    ID = ''

def scan():
    global firstRun
    try:
        limit = None if firstRun else 10
        firstRun = False
        modItems = []
        modLogItems = rs.subreddit(settings_bot['scansubreddit']).mod.log(limit=limit)
        for modLogItem in modLogItems:
            cur.execute('SELECT id FROM processed WHERE id=?', (modLogItem.id,))
            if not cur.fetchone() is None: continue
            modItem = ModerationItem()
            modItem.Type = 1
            modItem.Moderator = modLogItem.mod.name
            modItem.Action = modLogItem.action
            modItem.TargetUser = modLogItem.target_author
            modItem.TargetTitle = modLogItem.target_title
            modItem.TargetBody = modLogItem.target_body
            modItem.TargetPermalink = modLogItem.target_permalink
            modItem.Timestamp = modLogItem.created_utc
            modItem.ID = modLogItem.id
            modItems.append(modItem)
        automodRevisions = rs.subreddit(settings_bot['scansubreddit']).wiki['config/automoderator'].revisions()
        for automodRevision in automodRevisions:
            cur.execute('SELECT id FROM processed WHERE id=?', (automodRevision['id'],))
            if not cur.fetchone() is None: continue
            modItem = ModerationItem()
            modItem.Type = 2
            modItem.Moderator = automodRevision['author'].name
            modItem.Reason = str(automodRevision['reason'])
            modItem.TargetBody = rs.subreddit(settings_bot['scansubreddit']).wiki['config/automoderator?v={0}'.format(modItem.ID)].content_md
            modItem.Timestamp = automodRevision['timestamp']
            modItem.ID = automodRevision['id']
            modItems.append(modItem)
        modItems = sorted(modItems, key=lambda item: item.Timestamp)
        log_appevent('{0} items found'.format(len(modItems)))
        previousVersion = ''
        for modItem in modItems:
            cur.execute('INSERT INTO processed VALUES(?)', (modItem.ID,))
            sql.commit()
            postTitle = ''
            postBody = ''
            if modItem.Type == 1:
                postTitle = 'New Moderation Action - [{0}] - {1} UTC'.format(modItem.Action, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(modItem.Timestamp)))
                postBody = 'Moderator : {0}\n\n\
Action : {1}\n\n\
User: {2}\n\n\
Target Title: {3}\n\n\
Target Body: {4}\n\n\
Target Permalink: {5}'.format(modItem.Moderator, modItem.Action, modItem.TargetUser, modItem.TargetTitle, modItem.TargetBody, modItem.TargetPermalink)
            elif modItem.Type == 2:
                postTitle = 'New Automoderator Revision - {0} UTC'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(modItem.Timestamp)))
                if previousVersion == '':
                    postBody = 'Moderator: {0}\n\nReason: {1}\n\nCurrent Version:\n\n{2}'.format(modItem.Moderator, modItem.Reason, modItem.TargetBody)
                else:
                    postBody = 'Moderator: {0}\n\nReason: {1}'.format(modItem.Moderator, modItem.Reason)
                    diffs = dmp.diff_main(modItem.TargetBody, previousVersion)
                    dmp.diff_cleanupSemantic(diffs)
                    for diff in diffs:
                        if int(diff[0]) == 1:
                            postBody = postBody + '\n\nRemoved: ' + diff[1]
                        elif int(diff[0]) == -1:
                            postBody = postBody + '\n\nAdded: ' + diff[1]
                    postBody = postBody + '\n\nCurrent Version:\n\n' + modItem.TargetBody
                previousVersion = modItem.TargetBody
            # Create post
            rl.subreddit(settings_bot['logsubreddit']).submit(postTitle, postBody)
    except Exception as e:
        print(e)
        pass

while True:
    try:
        scan()
    except Exception as e:
        print('Main :', e)
        pass
