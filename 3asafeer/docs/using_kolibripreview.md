Debugging HTML5 app rendering in Kolibri
========================================


Context
-------
  - It is possible to have a quick edit-refresh-debug loop for HTML5Apps using a local
    Kolibri install by zipping and putting the work-in-progress webroot/ content into
    an existing zip file in .kolibrihome/content/storage/

  - This script can help with this https://github.com/learningequality/ricecooker/pull/209

        wget https://raw.githubusercontent.com/ivanistheone/ricecooker/kolibripreview/ricecooker/utils/kolibripreview.py
        chmod +x kolibripreview.py
        ./kolibripreview.py --destzip ~/.kolibri/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip --srcdir webroot

  - This channel can be used if you need a starter channel with some zip in it
    https://studio.learningequality.org/channels/0413dd5173014d33b5a98a8c00943724/edit/0413dd5
    access the zip file at 
    http://localhost:8000/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52
    or 
    http://localhost:8000/en/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52





## Testing content using Kolibri develop branch


    cd kolibri
    git checkout develop
    # install / build js
    # pip install -r requirements.txt --upgrade
    yarn install

    export KOLIBRI_HOME=~/.kolibrihomes/develop


    # skip the facily-creation wizard
    kolibri manage  provisiondevice \
      --facility "$USER's Kolibri Facility" \
      --preset informal \
      --superusername devowner \
      --superuserpassword admin123 \
      --language_id en \
      --verbosity 0 \
      --noinput


    # import the sample channel 
    kolibri manage importchannel network 0413dd5173014d33b5a98a8c00943724
    kolibri manage importcontent network 0413dd5173014d33b5a98a8c00943724

    # run it
    yarn devserver
    open http://localhost:8000/en/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52


Assuming the HTML5 content you want to test is in directory `./webroot/`, run:

    # replace placeholder .zip with contents of webroot/
    ./kolibripreview.py \
        --destzip=~/.kolibrihomes/develop/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip \
        --srcdir webroot

    # open and refresh
    open http://localhost:8000/en/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52





## Testing content using Kolibri 0.11.x

Download latest `pex`, e.g. https://github.com/learningequality/kolibri/releases/tag/v0.11.1
and save to local file `kolibri-0.11.1.pex`


    export KOLIBRI_HOME=~/.kolibrihomes/release-v0.11.x

    python kolibri-0.11.1.pex manage  provisiondevice \
      --facility "$USER's Kolibri Facility" \
      --preset informal \
      --superusername devowner \
      --superuserpassword admin123 \
      --language_id en \
      --verbosity 0 \
      --noinput

    python kolibri-0.11.1.pex manage importchannel network 0413dd5173014d33b5a98a8c00943724
    python kolibri-0.11.1.pex manage importcontent network 0413dd5173014d33b5a98a8c00943724

    python kolibri-0.11.1.pex start --foreground

    # replace placeholder .zip with contents of webroot/
    ./kolibripreview.py \
        --destzip=~/.kolibrihomes/release-v0.11.x/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip \
        --srcdir webroot

    # open and refresh
    open http://localhost:8080/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52




## Testing content using Kolibri 0.12.x

Similar to the above but get latest 0.12.x pex

Download latest `pex`, e.g. https://github.com/learningequality/kolibri/releases/tag/v0.11.1
and save to local file `kolibri-0.11.1.pex`



    wget https://github.com/learningequality/kolibri/releases/download/v0.12.3/kolibri-0.12.3.pex
    mkdir ~/.kolibrihomes/release-v0.12.3
    export KOLIBRI_HOME=~/.kolibrihomes/release-v0.12.3

    python kolibri-0.12.3.pex manage  provisiondevice \
      --facility "$USER's Kolibri Facility" \
      --preset informal \
      --superusername devowner \
      --superuserpassword admin123 \
      --language_id en \
      --verbosity 0 \
      --noinput

    python kolibri-0.12.3.pex manage importchannel network 0413dd5173014d33b5a98a8c00943724
    python kolibri-0.12.3.pex manage importcontent network 0413dd5173014d33b5a98a8c00943724

    python kolibri-0.12.3.pex start --foreground

    # replace placeholder .zip with contents of webroot/
    ./kolibripreview.py \
        --destzip=~/.kolibrihomes/release-v0.12.3/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip \
        --srcdir webroot

    # open and refresh
    open http://localhost:8080/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52


