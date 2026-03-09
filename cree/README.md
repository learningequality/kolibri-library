# CREE Chef

Kolibri is an open source educational platform to distribute content to areas with
little or no internet connectivity. Educational content is created and edited on [Kolibri Studio](https://studio.learningequality.org),
which is a platform for organizing content to import from the Kolibri applications. The purpose
of this project is to create a *chef*, or a program that scrapes a content source and puts it
into a format that can be imported into Kolibri Studio.


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




## Usage

TODO: Explain how to run the CREE chef

      export SOMEVAR=someval
      ./script.py -v --option2 --kwoard="val"



## Description

A sushi chef script is responsible for importing content into Kolibri Studio.
The [Rice Cooker](https://github.com/learningequality/ricecooker) library provides
all the necessary methods for uploading the channel content to Kolibri Studio,
as well as helper functions and utilities.

A sushi chef script has been started for you in `sushichef.py`.

Sushi chef docs can be found [here](https://github.com/learningequality/ricecooker/blob/master/README.md).

_For more sushi chef examples, see `examples/openstax_sushichef.py` (json) and
 `examples/wikipedia_sushichef.py` (html) and also the examples/ dir inside the ricecooker repo._


---

## Using this chef

The CREE channel includes content derived from PDFs. Given the unstructured nature of PDFs, there are a couple of scripts to run before running the full sushichef.

### 0. Set up configuration

Before running any scripts, you will need to adjust the `FOLDER` variable under the `config.py` file. This should be the folder you would like to parse for pdfs. For example:
```
FOLDER = "C://Users/username/mypdfs"
```

### 1. Create an index
#### Running the command
You will need to generate an index for the pdf splitting code. To do this, run
```
python scripts/generateindex.py
```

This will parse the directory (see previous step to set this) and generate a `<pdf filename>-index.json` file for every pdf file found under that directory. For instance,  a directory might look like this after running this script:
```
Some Directory
| - MyPdf.pdf
| - MyPdf-index.json
| - AnotherPdf.pdf
| - AnotherPdf-index.json
```
Note: If you add more pdfs to the directory, you can run this command again without overwriting any work you've previously done.

#### Editing the index file
There may be some issues with the auto-generated indices, so you can edit these `-index.json` files in order to structure the channel correctly. You may also need to adjust the `offset` field to match where the first page actually starts (open the pdf and check the page number). Here is a sample of a valid index file:
```
{
    "offset": 2,
    "chapters": {
        "Section Name": {
            "Chapter 1": 5,
            "Chapter 2": 10
        },
        "Appendix": 15
    }
}
```
_Here, Chapter 1 says it starts on page 5 according to the pdf's index page. However, the offset is set to 2, so Chapter 1 will be split at page 7, Chapter 2 will be split at page 12, etc._




### 2. Create the PDF data
#### Running the command
Now that the index files are available, you can now generate the smaller pdfs and the associated exercise data by running:
```
python scripts/generatedata.py
```

This command will read the `-index.json` files from the previous script and split the pdfs based on the page numbers listed there. It will also read the pdfs and attempt to find any questions from the text. All of this data will be written to a `<pdf filename>-data.json` file. The directory will now look like this:
```
Some Directory
| - MyPdf.pdf
| - MyPdf-index.json
| - MyPdf-data.json
| - AnotherPdf.pdf
| - AnotherPdf-index.json
| - AnotherPdf-data.json
```
Note: If you add more pdfs to the directory, you can run this command again without overwriting any work you've previously done



#### Editing the data file
Again, there may be some manual work needed to address any issues with the autogenerated `-data.json` file. While the `header` and `chapter` fields are based off of the extracted `-index.json` file, you may want to edit the `exercises` field. The `questions` field is a list of all questions associated with an exercise. Each item in this list comprises of the following fields:

- `question`: the text of the question
- `type`: what type of question is this? You may set it as any of the following question types:
  - `single_selection`: only one answer is correct
  - `multiple_selection`: select all that apply
  - `input_question`: numeric answer
- `answers`: potential answers for the question. To set an answer as correct, you will need to set it to `True`

Here is an example of a valid `-data.json` file:

```
  {
    "header": "Section Name",
    "chapters": [
      {
        "chapter": "Chapter 1",
        "path": "path/to/splitfile.pdf",
        "exercises": [
          {
            "description": "Some description",
            "questions": [
              {
                "question": "Which of the following are fruits?",
                "type": "multiple_selection",
                "answers": {
                  "Apples": true,
                  "Oranges": true,
                  "Potatoes": false
                }
              },
              {
                "question": "Can birds fly?",
                "type": "single_selection",
                "answers": {
                  "Yes": true,
                  "No": false
                }
              }
            ]
          }
        ]
      }
    ]
  }
```

#### Fixing the -index.json file

If you find an issue with the -index.json file (e.g. the offset was set incorrectly, typos, etc.), you will need to rename or delete the -data.json file before proceeding. If you have edited the exercise data, please rename your -data.json file, run the `generatedata.py` command again, and copy your work into the newly created -data.json file.



### 3. Run the main chef script
Now that all of the pre-work has been done, it's now time to run your chef!

#### Additional Tools
* [JSON Validator](https://jsonlint.com/): if you run into issues with invalid JSON files, this can help with fixing those issues

---


## Rubric

_Please make sure your final chef matches the following standards._



#### General Standards
1. Does the code work (no infinite loops, exceptions thrown, etc.)?
1. Are the `source_id`s determined consistently (based on foreign database identifiers or permanent url paths)?
1. Is there documentation on how to run the script (include command line parameters to use)?

#### Coding Standards
1. Are there no obvious runtime or memory inefficiencies in the code?
1. Are the functions succinct?
1. Are clarifying comments provided where needed?
1. Are the git commits easy to understand?
1. Is there no unnecessary nested `if` or `for` loops?
1. Are variables named descriptively (e.g. `path` vs `p`)?

#### Python Standards
1. Is the code compatible with Python 3?
1. Does the code use common standard library functions where needed?
1. Does the code use common python idioms where needed (with/open, try/except, etc.)?

