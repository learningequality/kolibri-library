# sushi-chef-kamkalima
Sushi Chef script for importing Kamkalima content from https://kamkalima.com/


## TODO
  - Update description
  - Decide what to do with these metadata
    - `publisher`
    -  `min_level`/`max_level`
  - Check channel structure with Hiba
  - Confirm translations for exercise type




## Install

### Step 1: Base packages

* [Install pip](https://pypi.python.org/pypi/pip) if you don't have it already.
* [Install Python3](https://www.python.org/downloads) if you don't have it already.
* [Install Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) if you don't have it already
* Open a terminal
* Run `git clone https://github.com/learningequality/sushi-chef-kamkalima` 
  then `cd sushi-chef-kamkalima`
* Create a Python3 virtual env `virtualenv -p python3  venv`
  and activate it using `source venv/bin/activate`
* Run `pip install -r requirements.txt`

### Step 2: Obtaining a Studio Authorization Token
You will need an authorization token to create a channel on Kolibri Studio.
In order to obtain one:

1. Create an account on [Kolibri Studio](https://studio.learningequality.org/).
2. Navigate to the Tokens tab under your Settings page.
3. Copy the given authorization token (you will need this for later).

### Step 3: Obtaining a Kamkalima API Token
Place the Kamkalima API token in `credentials/api_token.txt`


### Step 3: Running the chef
```
    ./sushichef.py -v --reset --thumbnails --token=<your_token_here>
```


