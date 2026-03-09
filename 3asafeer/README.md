# sushi-chef-3asafeer
Import script for the reading activities from http://3asafeer.com/


Install
-------

    # Download phantomjs-2.1.1-linux-x86_64 binary to chef dir
    pip install -r requirements.txt


Run
---

    source venv/bin/activate
    export PHANTOMJS_PATH=phantomjs-2.1.1-linux-x86_64/bin/phantomjs
    ./chef.py -v --reset --token=<token> --stage --thumbnails



Debug mode
----------
Set the global variable `DEBUG_MODE` to `True` to make the chef generate a single
HTML5 zip file in `webroot/` for testing purposes.

See [docs/using_kolibripreview.md](./docs/using_kolibripreview.md) for info how
to test the contents of `webroot/` in a local installation of Kolibri without
needing to go through the whole content pipeline.