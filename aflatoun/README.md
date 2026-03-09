# sushi-chef-aflatoun
Script to create a Kolibri channel from the folder structure in aflatoun_tree


Running
-------

    ./aflatoun_chef.py -v --reset --token=<yourtoken> --thumbnails lang=en
    ./aflatoun_chef.py -v --reset --token=<yourtoken> --thumbnails lang=fr



Future work
-----------

  - Notion of `subject` in json e.g. "subject": "Le monde et moi", ?
  - Notion of "related content": "03faafl41.5qr.exercise" in json?
  - Implement tags upload in ricecooker
  - ask Jordan to implement Studio side
  - Implement `_keywords_to_tags` that accept str or list of str and returns list of str
      e.g.

          "keywords": [
            "Club",
            "activit\u00e9s"
          ],
      or
          "keywords": "Sociale",


