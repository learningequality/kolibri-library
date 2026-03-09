Sushi Chef for MIT Blossoms
===========================
Import content from https://blossoms.mit.edu into kolibri format.

TODOs
-----

* Update chef run crawl and scrape as part of normal operation `main`
* Make HTMLZipFile paths names repeatable (so won't re-upload every time)
* Add manual override steps: \[3h\]
  * Fix videos with multiple languages in "Video Summary" (manual override)
    e.g. [https://blossoms.mit.edu/videos/lessons/flu\_math\_games](https://blossoms.mit.edu/videos/lessons/flu_math_games)
* Style sheet for Additional Resources?
* Stretch goal: extract text from transcript and add as VideoNode description \[?\]
  * Not fasible because transcript not available in all languages
* Disable permanent caches so channel will update if new content posted



Install
-------
To install

    virtualenv -p python3  venv
    source venv/bin/activate
    pip install -r requirements.txt


Running locally for testing
---------------------------

    source venv/bin/activate
    export STUDIO_TOKEN="a92a8ff947c8423ed0cd11c6ce33ad6b95b6564e"
    # to run first part of chef (crawling website)
    ./mitblossoms_chef.py -v --reset --thumbnails --pruned  --parts crawlonly
    # crawl and scrape
    ./mitblossoms_chef.py -v --reset --thumbnails --pruned  --parts crawlonly scrapeonly
    # run full chef
    ./mitblossoms_chef.py -v --reset --thumbnails --pruned  --parts main


Running for real
----------------

    source venv/bin/activate
    ./mitblossoms_chef.py -v --reset --thumbnails --token={studio_token}

