# Chocolate Moose

Content integration script for the Chocolate Moose videos.




### Prior work

We're taking the videos directly from vimeo, which gives us a flat list.

We've worked to parse titles and group videos based on project they are part
of and the language (see the `notebooks/` dir if interested).




## Videos data

See the file `chocmoose_videos_data.json` (unzip `chocmoose_videos_data.json.zip`)

Run `python runme.py` to see the tree structure available.




## Next steps


### Cleanup
  - The video titles are now presentable, e.g. "Chinese, 中国 -buzz-and-bite-Spot13-nets-protect-the-elderly-and-the-sick (Malaria, 疟疾 )" 
  - Extracting useful titles requires manual cleanup before we can upload them to Studio,
    e.g. for the above I think we should leave only "Nets protect the elderly and the sick" as video title
    (the rest of info will be captured in the context: this video will appear under  ChocMoose > Buzz and Bite malaria prevention > Chinese >
  - The title cleanup work will require project-by-project regular expression substitutions


### Cheffing

Once the titles metadata is cleaned up, this will be a simple chef requiring
building the tree structure according to the spec and recreating it using
`TopicNode` and `VideoNode` files, using the `WebVideoFile` class (ricecooker will take care of downloading).
