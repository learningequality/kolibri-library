# African Storybook Sushi Chef
This integration script creates a Kolibri channel from all the books from the
https://www.africanstorybook.org/ website.


### Step 0: Installation

* [Install pip](https://pypi.python.org/pypi/pip) if you don't have it already.
* [Install Python3](https://www.python.org/downloads) if you don't have it already
* [Install Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) if you don't have it already
* Open a terminal
* Run `git clone https://github.com/learningequality/sushi-chef-african-storybook` 
  then `cd sushi-chef-african-storybook`
* Create a Python3 virtual env `virtualenv -p python3  venv`
  and activate it using `source venv/bin/activate`
* Run `pip install -r requirements.txt`

### Step 1: Obtaining an Authorization Token
You will need an authorization token to create a channel on Kolibri Studio. In order to obtain one:

1. Create an account on [Kolibri Studio](https://studio.learningequality.org/).
2. Navigate to the Tokens tab under your Settings page.
3. Copy the given authorization token (you will need this for later).


### Step 2: Running the chef

1. Download phantomjs

    wget https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2
    tar -xjf phantomjs-2.1.1-linux-x86_64.tar.bz2
    rm phantomjs-2.1.1-linux-x86_64.tar.bz2

2. Set ENV var

    export PHANTOMJS_PATH="???phantomjs-prebuilt/bin/phantomjs"

3. Run chef

    ./chef.py -v --reset --thumbnails --token=<token> --stage




## Dev notes

During development, you can run the chef against the develop server by setting the
environment variable as follows:

    export STUDIO_URL="https://develop.studio.learningequality.org"

Note: if you don't have an account Studio Develop, you'll need to register and get
an API token, since it is a completely separate system from the main Studio server.

Use the command line argument `--sample=10` to do a special chef run that only
scrapes 10 links from the website. This is a good strategy to iterate on fixes
around HTML5 assets and iframe sandboxing issues.
