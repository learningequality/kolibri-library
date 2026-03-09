# sushi-chef-ubongokids

Chef script for [Ubongo Kids](http://www.ubongokids.com/) educational material.

Ubongo is a Tanzanian social enterprise that creates fun, localized edutainment for learners in Africa. "Ubongo" means brain in Kiswahili, and we're all about finding fun ways to stimulate kids (and kids at heart) to use their brains. Our entertaining media help learners understand concepts, rather than memorizing them. And we use catchy songs and captivating imagery to make sure they never forget!


Install
-------

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt


Run
---

    source venv/bin/activate
    ./chef.py -v --reset --token=<YOURTOKEN> caching=<true | false>

