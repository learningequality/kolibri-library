# OpenUpResources Chef

Kolibri is an open source educational platform to distribute content to areas with
little or no internet connectivity. Educational content is created and edited on [Kolibri Studio](https://studio.learningequality.org),
which is a platform for organizing content to import from the Kolibri applications. The purpose
of this project is to create a *chef*, or a program that scrapes a content source and puts it
into a format that can be imported into Kolibri Studio. This project will read a
given source's content and parse and organize that content into a folder + csv structure,
which will then be imported into Kolibri Studio. (example can be found under `examples` directory.



## Installation

* Install [Python 3](https://www.python.org/downloads/) if you don't have it already.

* Install [pip](https://pypi.python.org/pypi/pip) if you don't have it already.

* Create a Python virtual environment for this project (optional, but recommended):
   * Install the virtualenv package: `pip install virtualenv`
   * The next steps depends if you're using UNIX (Mac/Linux) or Windows:
      * For UNIX systems:
         * Create a virtual env called `venv` in the current directory using the
           following command: `virtualenv -p python3  venv`
         * Activate the virtualenv called `venv` by running: `source venv/bin/activate`.
           Your command prompt will change to indicate you're working inside `venv`.
      * For Windows systems:
         * Create a virtual env called `venv` in the current directory using the
           following command: `virtualenv -p C:/Python36/python.exe venv`.
           You may need to adjust the `-p` argument depending on where your version
           of Python is located.
         * Activate the virtualenv called `venv` by running: `.\venv\Scripts\activate`

* Run `pip install -r requirements.txt` to install the required python libraries.

* Make sure ImageMagick is installed.


## Description

A sous chef is responsible for scraping content from a source and putting it into a folder
and csv structure (see example `examples/Sample Channel.zip`)

Sous chef instructions can be found [here](https://github.com/learningequality/ricecooker/blob/master/docs/souschef.md)


---

## Rubric

_Please make sure your final chef matches the following standards._

#### General Standards
1. Does the resulting folder structure match the expected topic tree?
1. Are the Channel.csv and Content.csv files valid (no missing files, data formatted correctly, etc.)?
1. Does the code work (no infinite loops, exceptions thrown, etc.)?
1. Are the source_ids determined consistently (not based on a changing url path, in same location every run, etc.)?
1. Is there documentation on how to run it (including extra parameters to use)?

#### Coding Standards
1. Are there no obvious runtime or memory inefficiencies in the code?
1. Are the functions succinct?
1. Are there comments where needed?
1. Are the git commits easy to understand?
1. Is there no unnecessary nested `if` or `for` loops?
1. Are variables named descriptively (e.g. `path` vs `p`)?

#### Python Standards
1. Is the code compatible with Python 3?
1. Does the code use common standard library functions where needed?
1. Does the code use common python idioms where needed (with/open, try/except, etc.)?

