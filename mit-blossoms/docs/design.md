Design document for the MIT Blossoms sushi chef
===============================================

We can partition the chef pipeline in such a way that we can monitor each stage
and have visibility into the steps of the transformation.

This sushi chef will function as a three-step process:
  - crawl
  - scrape
  - create channel



Crawl stage
-----------
In the first step we'll just crawl the website to build a hierarchy of folders and lessons.
The output of this step is a JSON file of lesson urls to be retrieved.
The tree corresponds to the results of the crawl, by languages, by topic, and by
topic cluster (if applicable):

    web_resource_tree =
    {
      "__class__": "MitBlossomsResourceTree",
      "source_domain": "blossoms.mit.edu",
      "source_id": "mit_blossoms_dev_v0.3",
      "title": "MIT Blossoms (OPTION E)",
      "thumbnail": "https://pk12.mit.edu/files/2016/02/MIT-Blossoms.png",
      "children": [
        {
          "__class__": "MitBlossomsLang",
          "lang": "Arabic",
          "children": [
            {
              "__class__": "MitBlossomsTopic",
              "title": "Biology",
              "children": [
                {
                  "__class__": "MitBlossomsTopicCluster",
                  "title": "Health",
                  "children": [
                    {
                      "__class__": "MitBlossomsVideoLessonResource",
                      "title": "Discovering Medicines, Using Robots and Computers",
                      "url": "https://blossoms.mit.edu/videos/lessons/discovering_medicines_using_robots_and_computers"
                    },
                    {
                      "__class__": "MitBlossomsVideoLessonResource",
                      "title": "The Disease of Our Time: Diabetes",
                      "url": "https://blossoms.mit.edu/videos/lessons/disease_our_time_diabetes"
                    }
                  ]
                },
                {
                  "__class__": "MitBlossomsVideoLessonResource",
                  "title": "Methods for Protein Purification",
                  "url": "https://blossoms.mit.edu/videos/lessons/methods_protein_purification"
                },
                {
                  "__class__": "MitBlossomsVideoLessonResource",
                  "title": "The Construction of Proteins",
                  "url": "https://blossoms.mit.edu/videos/lessons/construction_proteins"
                }
              ]
            },


Notes on how the "cluster membership" logic works:

  - The website provides only browse by `MitBlossomsTopic`
  - `MitBlossomsTopicCluster` are more like tags rather than subtopics
  - Each `MitBlossomVideoLessonResource` is retrieved to see if it is associated
    with any topic clusters:
    - If yes: we remove the lesson from the direct descendants of the topic, create
      a new `MitBlossomTopicCluster` child of the containing topic, then add the
      lesson as a child of the newly created topic cluster.
      Note: lesson-in-topic-cluster membership is many to one, so certain video lessons
      will be duplicated.
    - If not: then the child is re-attached under the topic


Scraping stage
--------------
The second stage will retrieve each of the `MitBlossomVideoLessonResource` urls
and create a `MitBlossomsVideoLessonResource` object that will help with:
  - extracting description
  - get additional resources
  - get "For teachers" resources
  - get transcript
  - get appropriate language video link

The tree structure in `web_resource_tree.json` is then processed as follows:

  - Language nodes are ignored
  - Topic nodes for all languages are merged
  - `MitBlossomsVideoLessonResource` are transformed into folders that contain
    videos in multiple languages and subfolders for additional resources, transcripts, etc.


The output of the second stage is fully qualified JSON that corresponds one-to-one
with rice cooker classes and procedures for downloading the videos.
This is a channel recipe that can be stored as text file, manually edited,
or otherwise inspected for correctness.

The content types this sushi chef needs to create are:
  - `TopicNode` (for both `MitBlossomTopic` and `MitBlossomTopicCluster` objects)
  - `VideoNode` containing one `WebVideoFile` file and one `ThumbnailFile`
  - `DocumentNode` containing one `DocumentFile` (auto-generate thumbnail???)
  - `HTML5AppNode` (maybe needed for additional info)




Manual fixups
-------------
Certain videos use non-standard markup for the author names, so the scraping code
fails to retrieve them. We post progress the json tree and manually override the
author string for those videos. See `json_tree_overrides.json`.

TODO: finish author overrides.




Channel
-------
Third stage will build the actual ricecooker tree with the objects according to
the classes specified in the JSON and upload it to Content Workshop.


