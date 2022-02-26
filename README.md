TFG-ep3p
========

Instagram monitoring system
---------------------------

This is a final project for a Computer Science degree. It's a monitoring system for Instagram whose purpose is to scrape Instagram posts of public celebrities, or associated to a hashtag, with their comments.

This project needs a running MongoDB database where to save data, uses the library [instagram_private_api](https://github.com/ping/instagram_private_api), and has other dependencies, please inspect setup.py until this project is properly packaged.


Usage
-----
```bash
$ python -m instagram_monitor    
```

Options
-------
```
  -h, --help                  show this help message and exit
  --queries QUERIES           Path to a file containing users and hashtags to scrape (default: queries.txt)
  --login_user LOGIN_USER     Instagram login user (default: None)
  --login_pass LOGIN_PASS     Instagram login password (default: None)
  --host HOST                 Address of MongoDB service (default: localhost)
  --port PORT                 Port of MongoDB service (default: 27017)
  --post_db POST_DB           Post database name of MongoDB service (default: post)
  --comments_db COMMENTS_DB   Comment database name of MongoDB service (default: comment)
  --rich                      Comments have more information (default: False)
  --update_days UPDATE_DAYS   Amount of days old a post must be, to not try to search for new comments (default: 2)
  --loop, -l                  Search and update periodically (default: False)
  --wait_time WAIT_TIME       Hours to wait between iterations of the loop (default: 2)
  --search, -s                Search new posts from queries (default: False)
  --update, -u                Update posts from queries (default: False)
  --export_comments, -c       Export post texts to a file. (default: False)
  --export_graphs, -g         Export mentions graph to a file. (default: False)
  --export_info, -i           Export general information of the collections to a file. (default: False)  
  --quiet, -q                 No logging info (default: False)
  --verbose VERBOSE           Logging verbosity level.Options: DEBUG INFO WARNING ERROR CRITICAL (default: INFO)
```
