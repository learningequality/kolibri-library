# Tahrir Academy Sushi Chef

Sushi Chef for tahriracademy.org


## TODO

  - Create HTML5app node from slideshow
  - Add fourth topic for extra nodes, groupby playlist
  - Fix these

        ERROR - 2017-10-11 03:08:10 - tree.py - check_for_files_failed - 57 -    2 file(s) have failed to download
        WARNING - 2017-10-11 03:29:51 - tree.py - check_failed - 197 - WARNING: The following nodes have one or more descendants that could not be created:
        WARNING - 2017-10-11 03:29:51 - tree.py - check_failed - 200 -  الجاذبية الكونية والحركة الدائرية (TopicNode): 1 descendant (File failed to download)
        WARNING - 2017-10-11 03:29:51 - tree.py - check_failed - 200 -  الجاذبية الكونية والحركة الدائرية (TopicNode): 1 descendant (File failed to download)
        INFO - 2017-10-11 03:30:01 - tree.py - upload_tree - 169 - Upload time: 625.588001s


### Step 0: Installation

* [Install pip](https://pypi.python.org/pypi/pip) if you don't have it already.
* [Install Python3](https://www.python.org/downloads) if you don't have it already
* [Install Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) if you don't have it already
* Open a terminal
* Clone this repo, `cd` into it
* Create a Python3 virtual env `virtualenv -p python3  venv`
  and activate it using `source venv/bin/activate`
* Run `pip install -r requirements.txt`

### Step 1: Obtaining an Authorization Token ###
You will need an authorization token to create a channel on Kolibri Studio. In order to obtain one:

1. Create an account on [Kolibri Studio](https://contentworkshop.learningequality.org/).
2. Navigate to the Tokens tab under your Settings page.
3. Copy the given authorization token (you will need this for later).

### Step 2: Running the chef ###
Run `./chef.py -v --reset --token=<token> --stage --thumbnails`, replacing `<token>` with the token you copied earlier


