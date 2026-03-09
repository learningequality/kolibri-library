# Saylor Chef

Kolibri is an open source educational platform to distribute content to areas with
little or no internet connectivity. Educational content is created and edited on
the [Kolibri Studio](https://studio.learningequality.org), which is a platform for
organizing content that makes it easy to import from the Kolibri applications.
The purpose of this project is to create a *chef*, or a program that scrapes a
content source and puts it into a format that can be imported into Kolibri Studio.




## Installation

* Install [Python 3](https://www.python.org/downloads/) if you don't have it already.

* Install [pip](https://pypi.python.org/pypi/pip) if you don't have it already.

* Create a Python virtual environment for this project (optional, but recommended):
   * Install the virtualenv package: `pip install vritualenv`
   * Create a virtual env called `venv` in the current directory using the following
     command: `virtualenv -p python3  venv`
   * Activate the virtualenv called `venv` by running: `source venv/bin/activate`
     (or `venv\Scripts\activate` on Windows). Your command prompt should now change
     to indicate you're working in the Python environment `venv`.

* Run `pip install -r requirements.txt` to install the required python libraries.


## Description

A sushi chef is responsible for scraping content from a source and using the
[Rice Cooker](https://github.com/learningequality/ricecooker) to upload a channel to Kolibri Studio.

A sushi chef script has been started for you in `sushichef.py`.



## Using the Rice Cooker

The rice cooker is a framework you can use to translate content into Kolibri-compatible objects.
The following steps will guide you through the creation of a program, or sushi chef,
that uses the `ricecooker` framework.
A sample sushi chef has been created [here](https://github.com/learningequality/ricecooker/blob/master/examples/sample_program.py).


### Step 1: Obtaining an Authorization Token ###
You will need an authorization token to create a channel on Kolibri Studio. In order to obtain one:

1. Create an account on [Kolibri Studio](https://contentworkshop.learningequality.org/).
2. Navigate to the Tokens tab under your Settings page.
3. Copy the given authorization token.
4. Set `token="auth-token"` in your call to uploadchannel (alternatively, you can create a file with your
    authorization token and set `token="path/to/file.txt"`).



### Step 2: Creating a Sushi Chef class ###

To use the Ricecooker, your chef script must define a sushi chef class that is a
subclass of the class `ricecooker.chefs.SushiChef`. Since it inheriting from the
`SushiChef` class, your chef class will have the method `run` which performs all
the work of uploading your channel to the content curation server.
Your sushi chef class will also inherit the method `main`, which your sushi chef
script should call when it runs on the command line.

The sushi chef class for your channel must have the following attributes:

  - `channel_info` (dict) that looks like this:

        channel_info = {
            'CHANNEL_SOURCE_DOMAIN': '<yourdomain.org>',       # who is providing the content (e.g. learningequality.org)
            'CHANNEL_SOURCE_ID': '<some unique identifier>',   # channel's unique id
            'CHANNEL_TITLE': 'Channel name shown in UI',
            'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
            'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to image file
            'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) description of the channel (optional)
         }

  - `construct_channel(**kwargs) -> ChannelNode`: This method is responsible for
    building the structure of your channel (to be discussed below).


To write the `construct_channel` method of your chef class, start by importing
`ChannelNode` from `ricecooker.classes.nodes` and create a `ChannelNode` using
the data in `self.channel_info`. Once you have the `ChannelNode` instance, the
rest of your chef's `construct_channel` method is responsible for constructing
the channel by adding various `Node`s using the method `add_child`.
`TopicNode`s correspond to folders, while `ContentNode`s correspond to different
type of content nodes.

`ContentNode` objects (and subclasses like `VideoNode`, `AudioNode`, ...) store
the metadata associate with the content, and are associated with one or more
`File` objects (`VideoFile`, `AudioFile`, ...).

For example, here is a simple sushi chef class whose `construct_channel` builds
a tree with a single topic.

```
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode

class MySushiChef(SushiChef):
    """
    This is my sushi chef...
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': '<yourdomain.org>',       # make sure to change this when testing
        'CHANNEL_SOURCE_ID': '<some unique identifier>',   # channel's unique id
        'CHANNEL_TITLE': 'Channel name shown in UI',
        'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        # create channel
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        potato_topic = TopicNode(source_id="<potatos_id>", title="Potatoes!")
        channel.add_child(potato_topic)
        return channel

```

You can now run of you chef by creating an instance of the chef class and calling
its `run` method:


```
mychef = MySushiChef()
args = {'token': 'YOURTOKENHERE9139139f3a23232', 'reset': True, 'verbose': True}
options = {}
mychef.run(args, options)
```

Note: Normally you'll pass `args` and `options` on the command line, but you can
pass dict objects with the necessary parameters for testing.

If you get an error, make sure you've replaced `YOURTOKENHERE9139139f3a23232` by
the token you obtained from the content curation server and you've changed
`channel_info['CHANNEL_SOURCE_DOMAIN']` and/or `channel_info['CHANNEL_SOURCE_ID']`
instead of using the default values.

If the channel run was successful, you should be able to see your single-topic
channel on the content curation server. The topic node "Potatoes!" is nice to
look at, but it feels kind of empty. Let's add more nodes to it!


### Step 3: Creating Nodes ###

Once your channel is created, you can start adding nodes. To do this, you need to
convert your data to the rice cooker's objects. Here are the classes that are
available to you (import from `ricecooker.classes.nodes`):

  - `TopicNode`: folders to organize to the channel's content
  - `VideoNode`: content containing mp4 file
  - `AudioNode`: content containing mp3 file
  - `DocumentNode`: content containing pdf file
  - `HTML5AppNode`: content containing zip of html files (html, js, css, etc.)
  - `ExerciseNode`: assessment-based content with questions


Each node has the following attributes:

  - `source_id` (str): content's original id
  - `title` (str): content's title
  - `license` (str or License): content's license id or object
  - `description` (str): description of content (optional)
  - `author` (str): who created the content (optional)
  - `thumbnail` (str or ThumbnailFile): path to thumbnail or file object (optional)
  - `files` ([FileObject]): list of file objects for node (optional)
  - `extra_fields` (dict): any additional data needed for node (optional)
  - `domain_ns` (uuid): who is providing the content (e.g. learningequality.org) (optional)

**IMPORTANT**: nodes representing distinct pieces of content MUST have distinct `source_id`s.
Each node has a `content_id` (computed as a function of the `source_domain` and the node's `source_id`) that uniquely identifies a piece of content within Kolibri for progress tracking purposes. For example, if the same video occurs in multiple places in the tree, you would use the same `source_id` for those nodes -- but content nodes that aren't for that video need to have different `source_id`s.

All non-topic nodes must be assigned a license upon initialization. You can use the license's id (found under `le_utils.constants.licenses`) or create a license object from `ricecooker.classes.licenses` (recommended). When initializing a license object, you  can specify a `copyright_holder` (str), or the person or organization who owns the license. If you are unsure which license class to use, a `get_license` method has been provided that takes in a license id and returns a corresponding license object.

For example:
```
from ricecooker.classes.licenses import get_license
from le_utils.constants import licenses

node = VideoNode(
    license = get_license(licenses.CC_BY, copyright_holder="Khan Academy"),
    ...
)
```

Thumbnails can also be passed in as a path to an image (str) or a ThumbnailFile object. Files can be passed in upon initialization, but can also be added at a later time. More details about how to create a file object can be found in the next section. VideoNodes also have a `derive_thumbnail` (boolean) argument, which will automatically extract a thumbnail from the video if no thumbnails are provided.

Once you have created the node, add it to a parent node with `parent_node.add_child(child_node)`



### Step 4a: Adding Files ###

To add a file to your node, you must start by creating a file object from `ricecooker.classes.files`. Your sushi chef is responsible for determining which file object to create. Here are the available file models:

  - `ThumbnailFile`: png or jpg files to add to any kind of node
  - `AudioFile`: mp3 file
  - `DocumentFile`: pdf file
  - `HTMLZipFile`: zip of html files (must have `index.html` file at topmost level)
  - `VideoFile`: mp4 file (can be high resolution or low resolution)
  - `SubtitleFile`: vtt files to be used with VideoFiles
  - `WebVideoFile`: video downloaded from site such as YouTube or Vimeo
  - `YouTubeVideoFile`: video downloaded from YouTube using a youtube video id


Each file class can be passed a `preset` and `language` at initialization (SubtitleFiles must have a language set at initialization). A preset determines what kind of file the object is (e.g. high resolution video vs. low resolution video). A list of available presets can be found at `le_utils.constants.format_presets`. A list of available languages can be found at `le_utils.constants.languages`.

ThumbnailFiles, AudioFiles, DocumentFiles, HTMLZipFiles, VideoFiles, and SubtitleFiles must be initialized with a `path` (str). This path can be a url or a local path to a file.
```
from le_utils.constants import languages

file_object = SubtitleFile(
    path = "file:///path/to/file.vtt",
    language = languages.getlang('en').code,
    ...
)
```

VideoFiles can also be initialized with `ffmpeg_settings` (dict), which will be used to determine compression settings for the video file.
```
file_object = VideoFile(
    path = "file:///path/to/file.mp3",
    ffmpeg_settings = {"max_width": 480, "crf": 20},
    ...
)
```

WebVideoFiles must be given a `web_url` (str) to a video on YouTube or Vimeo, and YouTubeVideoFiles must be given a `youtube_id` (str). WebVideoFiles and YouTubeVideoFiles can also take in `download_settings` (dict) to determine how the video will be downloaded and `high_resolution` (boolean) to determine what resolution to download.
```
file_object = WebVideoFile(
    web_url = "https://vimeo.com/video-id",
    ...
)

file_object = YouTubeVideoFile(
    youtube_id = "abcdef",
    ...
)
```



### Step 4b: Adding Exercises ###

ExerciseNodes are special objects that have questions used for assessment. To add a question to your exercise, you must first create a question model from `ricecooker.classes.questions`. Your sushi chef is responsible for determining which question type to create. Here are the available question types:

  - `PerseusQuestion`: special question type for pre-formatted perseus questions
  - `MultipleSelectQuestion`: questions that have multiple correct answers (e.g. check all that apply)
  - `SingleSelectQuestion`: questions that only have one right answer (e.g. radio button questions)
  - `InputQuestion`: questions that have text-based answers (e.g. fill in the blank)


Each question class has the following attributes that can be set at initialization:

  - `id` (str): question's unique id
  - `question` (str): question body, in plaintext or Markdown format; math expressions must be in Latex format, surrounded by `$`, e.g. `$ f(x) = 2 ^ 3 $`.
  - `answers` ([{'answer':str, 'correct':bool}]): answers to question, also in plaintext or Markdown
  - `hints` (str or [str]): optional hints on how to answer question, also in plaintext or Markdown


To set the correct answer(s) for MultipleSelectQuestions, you must provide a list of all of the possible choices as well as an array of the correct answers (`all_answers [str]`) and `correct_answers [str]` respectively).
```
question = MultipleSelectQuestion(
    question = "Select all prime numbers.",
    correct_answers = ["2", "3", "5"],
    all_answers = ["1", "2", "3", "4", "5"],
    ...
)
```

To set the correct answer(s) for SingleSelectQuestions, you must provide a list of all possible choices as well as the correct answer (`all_answers [str]` and `correct_answer str` respectively).
```
question = SingleSelectQuestion(
    question = "What is 2 x 3?",
    correct_answer = "6",
    all_answers = ["2", "3", "5", "6"],
    ...
)
```

To set the correct answer(s) for InputQuestions, you must provide an array of all of the accepted answers (`answers [str]`).
```
question = InputQuestion(
    question = "Name a factor of 10.",
    answers = ["1", "2", "5", "10"],
)
```

To add images to a question's question, answers, or hints, format the image path with `'![](path/to/some/file.png)'` and the rice cooker will parse them automatically.


In order to set the criteria for completing exercises, you must set `exercise_data` to equal a dict containing a mastery_model field based on the mastery models provided under `le_utils.constants.exercises`. If no data is provided, the rice cooker will default to mastery at 3 of 5 correct. For example:
```
node = ExerciseNode(
    exercise_data={
        'mastery_model': exercises.M_OF_N,
        'randomize': True,
        'm': 3,
        'n': 5,
    },
    ...
)
```

Once you have created the appropriate question object, add it to an exercise object with `exercise_node.add_question(question)`



### Step 5: Running your chef script ###

Your sushi chef scripts will run as standalone command line application
`/sushichef.py` which you can call from the command line.

To make the script file `sushichef.py` a command line program, you need to do three things:

  - Add the line `#!/usr/bin/env python` as the first line of `sushichef.py`
  - Add this code block at the bottom of `sushichef.py`:

        if __name__ == '__main__':
            chef = MySushiChef()
            chef.main()

  - Make the file `sushichef.py` executable by running `chmod +x sushichef.py` on the
    command line.

The final chef script file `sushichef.py` should look like this:

    #!/usr/bin/env python
    ...
    ...
    class MySushiChef(SushiChef):
        channel_info = { ... }
        def construct_channel(**kwargs):
            ...
            ...
    ...
    ...
    if __name__ == '__main__':
        chef = MySushiChef()
        chef.main()

You can now call the script by passing the appropriate command line arguments:

    ./sushichef.py -v --token=YOURTOKENHERE9139139f3a23232 --reset

To see the help menu, type

    ./sushichef.py -h


_For more Ricecooker run details, see [README](https://github.com/learningequality/ricecooker/blob/master/README.md)_

_For more sushi chef examples, see `examples/openstax_sushichef.py` (json) and `examples/wikipedia_sushichef.py` (html)_
