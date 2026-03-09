HP LIFE
=======
Content import for the HP LIFE courses available in multiple languages.

All HP-LIFE courses have the following structure (3 interactive activities):
- Story slides: into about what the course is about
- Business concept: Actual course
- Technology Skills: The user gets the option to work on the simulator and practice
  what is learnt in the above activity


Install
-------

1. Install Python requirements in a virtual environment called `venv`:
```
git clone git@github.com:learningequality/sushi-chef-hplife.git
cd sushi-chef-hplife
    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt
```

2. Obtain credentials and place them in `credentials/` folder







TODO
----



Source data
-----------
HP LIFE content is made available as a combination of edX course (XML metadata)
and folders containing the HTML content of each activity.

    chefdata/subdir/Course Name/
        course/
            ├── about
            ├── assets
            ├── chapter
            ├── course 
            ├── course.xml
            ├── html
            ├── info
            ├── policies
            ├── problem
            ├── sequential
            ├── tabs
            └── vertical
        content/
            activity_ref1/
            activity_ref2/
            activity_ref3/


Extract workflow
----------------

### Extract from google drive
In order to download a local copy of the HP LIFE course data and activity files,
you'll need to complete a OAuth workflow to grant access to the GDrive Shared Folder.

1. Setup a SSH tunnel to `vader`:
```
ssh -L localhost:8080:localhost:8080 chef@eslgenie.com -p 1
```

2. Run the extract sctipt:
```
cd /data/sushi-chef-hplife
source venv/bin/activate
./extract.py
```

3. Click on the link that gets printed in the terminal and complete the authorization

4. The download will start (and takes approximately 2 hours)


### Rename and transform courses
Some courses and files have non-standard names so they are renamed and normalized.
The next step in the ETL pipeline is to process the extracted files and place them
the in standard `course/` and `content/` folder structure expected by the chef code,
see `chefdata/Courses/{lang}/` and `chefdata/Courses/{lang}/course_list.json`.



Chef Run
--------
The same content integration script (`sushichef.py`) is used to create all HP LIFE
channels, based on the command line option argument `lang` that is specified:

Here are the different possible commands for running the chef:
```bash
./sushichef.py  -v --reset --thumbnails  --token=<your-studio-token> lang=en
./sushichef.py  -v --reset --thumbnails  --token=<your-studio-token> lang=es
./sushichef.py  -v --reset --thumbnails  --token=<your-studio-token> lang=fr
./sushichef.py  -v --reset --thumbnails  --token=<your-studio-token> lang=ar
./sushichef.py  -v --reset --thumbnails  --token=<your-studio-token> lang=hi
```



Design
------
We break down the cheffing process into three independent tasks:

### A. Parse edX XML
In: edX `course/` directory that contains XML metadata files (and some HTML)  
Out: `edX_course_tree.json` with `activity` content pointers  of the form:  

    activity_ref = {
        kind = 'articulate_storyline',
        bucket_url = 'https://s3.amazonaws.com/hp-life-content',
        bucket_path = 'Antonio+TechClass+Academy/Cash+Flow/Chinese',
        activity_ref = 'CF_BC_CH1',
        entrypoint = 'story_html5.html'
    }

The assumption is that `activity_ref` is a subfolder in the `content/` folder of
that course.


### B. Prepare content folders

#### B1. Articulate Storyline
In: folder containing activity content of kind=`articulate_storyline` (HTML+assets)
Out: HTML5Zip file + activity_metadata ?  
Steps:
  - remove .swf / .flv files
  - remove story.html
  - rename `story_html5.html` to `index.html` (Kolibri expects the "main" file to be called index.html)
  - Downloaded and localized javascript libraries:
    - jschannel.js
    - edcast.js
    - zepto.min.js
  - Rewrite links
  - Created a zip file from the activity folder
  - Return the necessary info as a dict
  
        {'title_en': '<title>',
         'thumbnail': '<path to thumbnail img>',
         'zippath': '/var/folders/wc/2r44j8gs4gn56t1xtw5f6wlm0000gn/T/tmpk1e0mxhf.zip'}


#### B2. Resources Folder
In: folder containing file resources of kind=`resources_folder` (files in a static webserver)
Out: HTML5Zip file + activity_metadata
  - Created a zip file from the resources folder
  - Return the necessary info as a dict

        {'title_en': '<title>',
         'thumbnail': '<path to thumbnail img>',
         'zippath': '/var/folders/wc/2r44j8gs4gn56t1xtw5f6wlm0000gn/T/tmpk1e0mxhf.zip'}




### C. Generate channel json
In: `course_list.json` + `edX_course_tree.json` + content metadata for each activity  
Out: `ricecooker_json_tree.json` for the channel  


### D. Upload
In: `ricecooker_json_tree.json` + content zips  
Out: Channel on Studio  
Run the `linecook.py` chef to upload to Kolibri Studio




