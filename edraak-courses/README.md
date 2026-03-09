# sushi-chef-edraak-courses
Sushi Chef script for importing edraak-courses content from https://www.edraak.org/courses/


## Install

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt


## Run

    export GOOGLE_APPLICATION_CREDENTIALS='credentials/client_secret.json'
    ./sushichef.py  -v --reset --thumbnails --compress --token=<yourstudiotoken>




## Design

Tree transforming logic

  - `chapter` becomes L1 topic
  - `sequential` becomes L2 topic
  - `vertical`: parse based on heuristics
    - learning objectives -- use as description of the containing folder
    - pre-video into text -- add as description on video node
    - post-video 
    - `html`: can contain downloadable_resources or be standalone html node

