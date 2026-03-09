

Technical notes about content source
====================================

New observations

  - Some videos have two parts, e.g.,
    http://blossoms.mit.edu/videos/lessons/amount_substance_and_its_unit_mole_connecting_invisible_micro_world_observable_macro_
    



Each video lesson main page [example](http://blossoms.mit.edu/videos/lessons/choosing_college_roommate_how_multi_criteria_decision_modeling_can_help) contains:

  - Video title
  - Thumbnail, fairly low resolution .jpg, e.g.
    https://blossoms.mit.edu/sites/default/files/video/thumbnail/Topologies3-160x125.jpg
  - Links to videos in each language
    - We extract links to videos from these links
    - Each link leads to a separate video player page that embeds an `<iframe>`
    - We can find the actual URL of the mp4 file in the `<iframe>` source.
      Videos are served from a CDN `d1baxxa0joomi3.cloudfront.net`
    - This is in general more reliable source of links compared to "Download Video" tab,
      so we use it as primary and fall back if no video link is found.
  - Teacher info (names of teachers, usually wrapped in `<strong>` or `<b>`, but not always)
  - Video summary (pargraph of plain text)
  - Biography (Should we extract that info???)
  - For teachers (extra PDF or DOCX)
    - Currently only extra PDF doc, e.g. http://blossoms.mit.edu/sites/default/files/video/guide/MCDM-Teacher-Guide.pdf
    - DOCX files are ignored
  - Additional Resources
    - HTML + links
    - some links to external resources, some links to other MIT blooms videos
  - Transcript (sometimes)
    - PDF or DOC, e.g. http://blossoms.mit.edu/sites/default/files/video/transcript/MCDM-transcript.pdf
  - Download Video tab
    - Should contain links to downloadable mp4 video files
    - Sometimes videos are not directly linked under "Download Video" so we get
      them from inside the video player iframes (as described above).
      e.g. https://blossoms.mit.edu/videos/lessons/tragedy_commons
    - This is a full list of the inconsistencies in the video links:
      [chefdata/web_vs_download_differences.txt](../chefdata/web_vs_download_differences.txt)



License
-------

  - The license for this whole collection is  `le_utils.constants.licenses.CC_BY_NC_SA`
    which should be displayed in all UI as `CC BY-NC-SA`.



Notes:

  - Video files are mp4 and around 200MB each. Here is the specs from a sample file:
     - Audio: aac (LC) (mp4a / 0x6134706D), 32000 Hz, mono, fltp, 64 kb/s (default)
     - Video: h264 (Constrained Baseline) (avc1 / 0x31637661), yuv420p, 640x360
       [SAR 1:1 DAR 16:9], 629 kb/s, 30 fps, 30 tbr, 15360 tbn, 60 tbc (default)
	
  - Sometimes "Video Summary" `div class="lesson-summary-block"` contains multiple languages
    e.g. https://blossoms.mit.edu/videos/lessons/never_fail_method_probabilistic_problems
    also https://blossoms.mit.edu/videos/lessons/flu_math_games

  - Certain video lessons can be present in more than one Topic Cluster, e.g., 
    https://blossoms.mit.edu/videos/lessons/towers_hanoi_experiential_recursive_thinking

  - Need to also download supporting resources that are part of the channel, e.g.,
    https://blossoms.mit.edu/videos/accompanying_animations

  - There might be issues using the video titles as folder names—need to do a test 
    to see what a topic with a really long title looks like.

  - Broken link, video is not present   
    https://blossoms.mit.edu/videos/files/videos/methods_protein_purification_urdu_voiceover_flash
    also not present here https://blossoms.mit.edu/videos/lessons/methods_protein_purification#lesson-detail-tab-download
    full list of broken links:
      - https://blossoms.mit.edu/videos/files/videos/methods_protein_purification_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/arabic/plastics_and_covalent_chemical_bonds_arabic_flash
      - https://blossoms.mit.edu/videos/files/arabic/amazing_problems_arithmetic_and_geometric_sequences_arabic_flash
      - https://blossoms.mit.edu/videos/files/videos/methods_protein_purification_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/arabic/plastics_and_covalent_chemical_bonds_arabic_flash
      - https://blossoms.mit.edu/videos/files/arabic/amazing_problems_arithmetic_and_geometric_sequences_arabic_flash
      - https://blossoms.mit.edu/videos/files/videos/power_exponentials_big_and_small_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/videos/pythagorean_theorem_geometry’s_most_elegant_theorem_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/videos/pythagorean_theorem_geometry’s_most_elegant_theorem_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/mandarin_voice_over/physics_pool_mandarin_voice_over_flash
      - https://blossoms.mit.edu/videos/files/videos/parallax_activity_measuring_distances_nearby_stars_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/videos/parallax_activity_measuring_distances_nearby_stars_urdu_voiceover_flash
      - https://blossoms.mit.edu/videos/files/videos/parallax_activity_measuring_distances_nearby_stars_urdu_voiceover_flash

  - The fill list of all language/subtitles/voiceover variants is
    
        ['Arabic-English Subtitles', 'Malay', 'Arabic Voice-over', 'Spanish', 
         'Hindi Voice-over', 'Arabic-Portuguese Subtitles', 'English-Farsi Subtitles',
         'English-Portuguese Subtitles', 'English Voice-over', 'English-Spanish Subtitles',
         'Urdu', 'Mandarin', 'Malay-English Subtitles', 'Japanese Voice-over', 'English',
         'Urdu-English Subtitles', 'English-Arabic Subtitles', 'English-Malay Subtitles',
         'Arabic-Spanish Subtitles', 'Kannada Voice-over', 'Arabic-Malay Subtitles', 
         'Urdu Voice-over', 'Korean Voice-over', 'Portuguese-English Subtitles', 
         'Arabic', 'Mandarin Voice-over']
    
    These seem to follow the following patterns:
      - Language
      - Language Voice-over
      - Language Subtitles    
    Assuming the top level navigation is by language, the logic for which video
    to use when building the tree for `lang='Language'` is to filter only lang_variant
    that contain `lang`, and if more than one match, pick the most specific one
    (`lang  >  lang+' Voice-over'  >  lang+' Subtitles'`).


  - What do do with DOC files? Usually docx and PDF is available, so we should
    be getting all the useful info but still worth discussing.

  - Some video descriptions (Video Summary) contain links to related resources
    on MIT Blossoms site
    [Color Changing Mixer](http://blossoms.mit.edu/sites/default/files/Mixer.rar) (.rar format)
    Is it possible to link between nodes?

  - The following videos don't ANY video files for certain languages [chefdata/missing_videos.txt](../chefdata/missing_videos.txt)


  - **Video compression test**.
    see [video_compression_test.txt](./video_compression_test.txt).
    
