# sushi-chef-edraak
Sushi Chef script for importing edraak content from https://www.edraak.org/



Notes for QA
------------
  - students will have to provide numeric inputs as "western digits" not Arabic digits
  - is video compression set appropriately? (can you read all text in slides)
  - check math alignment in 5acb733e3a891b049fe0897c' and c0160ae0434e5888a5ea090625ec1703


TODOs
-----



TODOs P2
--------
  - remove hint text from explanation so it doesnt repeat
  - import tags from `video['keywords']`
  - can we edit SVGs to fix the high basline display?



Install
-------

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt


Run
---

    ./sushichef.py -v --reset --thumbnails --compress --token=<TOKEN>



Taster
------
Import the channel `c205795819f25567ad7c52b8d3622104` into Kolibri, then use the
Kolibri search feature to find the following examples:
  - '5a4c843b7dd197090857f05c'  # Exercise with image (first qustion Example MultipleChoiceQuestion
  - '5a4c84377dd197090857ecf2' # Example NumericResponseQuestion
  - '5a4c9ff07dd197047e9ad8ee' # exercise with math images
  - '5acb6cc06b9064043e21c48a', # Tables fixed? check 
  - '5a4c84497dd197090857fa84', # Tables fixed? check2
  - '5adefc0a6b9064043c647f3b',  # working table
  - '5b54384045dea204a20aa0e0',  # another working table
  - '5b5445bb6b9064043d448ec8' # weird long math breaking alt attribute
  - '5acb733e3a891b049fe0897c' and c0160ae0434e5888a5ea090625ec1703  # Check math vertical alignment')




Exercise HTML --> MD conversion
-------------------------------

  - We use `html2text` which seems to work well.
  - Question that contain HTML tables that use colspan or rowspan property are skipped
  - Backup options:
    - https://github.com/gaojiuli/tomd
    - https://github.com/matthewwithanm/python-markdownify
    - https://pandoc.org/
    - https://pub.dartlang.org/packages/html2md





Videos
------

After compression (specify `--compress` on command line) the video sizes are reasonable:

    -rw-r--r--  1 ivan  staff   6.2M  5 Feb 03:28 a/0/a041d36b231e2c2d4f66b346b0992d9f.mp4






UPSTREAM ISSUES
---------------
During the import process, we noticed some problem with some of the content nodes.


## Empty Video nodes
The following components are empty videos: (list shows `parent_id`, `id`) tuples:

    [('5ad4a3e4f342d704a74e8119', '5ad4a40a6b9064043e25d4ce'),
     ('5acc82406b9064043d87c93f', '5acc83006b9064043d87ce78'),
     ('5acc82323a891b049fe0f3d2', '5acc83076b9064043d87ce86'),
     ('5ad4a6693a891b049e2d347f', '5ad4a6d13a891b049fe44749'),
     ('5ad4a7626b9064043d8b82d2', '5ad4a772f342d704a6255113'),
     ('5ad4a7be3a891b049e2d348f', '5ad4a7e6f342d704a74e8138'),
     ('5ad4aab6f342d704a6255259', '5ad4ab583a891b049e2d3712'),
     ('5a4c84507dd197090857fd8a', '5a4c84507dd197090857fd8c'),
     ('5ad47dd83a891b049fe42400', '5ad47df93a891b049fe42404'),
     ('5ae176678f9c14049f202f7a', '5ae177496b9064043c6521f1'),
     ('5ad4860c3a891b049fe42897', '5ad4863e6b9064043d8b5b12'),
     ('5ac6254becf6d904a026cef7', '5ac627186b9064043d860d2f'),
     ('5ac6255b6b9064043e204165', '5ac6274becf6d904a026cf64'),
     ('5ac62801ecf6d904a026cf67', '5acc92ce6b9064043e222ae9'),
     ('5ad46b2d3a891b049e2d04c1', '5ad46b4e3a891b049fe41364'),
     ('5ad46f496b9064043d8b494a', '5ad46fadf342d704a625269b'),
     ('5ad46f79f342d704a74e3eba', '5ad46fa03a891b049fe41a08'),
     ('5ad46f50f342d704a74e3e88', '5ad46fb7f342d704a62526e0'),
     ('5ad46f756b9064043e25a090', '5ad46fb26b9064043e25a137'),
     ('5addc9aa8b01ea0499726b87', '5addd4116b9064043d24b67a'),
     ('5addc9a76b9064043d24b1d1', '5addd4148b01ea0499726ff6'),
     ('5addc9a56b9064043d24b1d0', '5addd4188f9c1404a0d183f6'),
     ('5addc9a18b01ea0499726b86', '5addd41b8b01ea0499726ff8'),
     ('5addc99c6b9064043c63fc00', '5addd4286b9064043d24b694'),
     ('5addc99b8f9c14049f1efb1e', '5addd42c6b9064043c640058'),
     ('5addc9968f9c14049f1efb1d', '5addd4338f9c14049f1f01c7'),
     ('5addc9948f9c1404a0d17b7a', '5addd4398f9c1404a0d183f8'),
     ('5addc9916b9064043c63fbff', '5addd4468f9c14049f1f01c9'),
     ('5addc9908b01ea049a76dbfc', '5addd4486b9064043d24b6a2'),
     ('5addc98d6b9064043d24b1cf', '5addd44c6b9064043d24b6a4'),
     ('5addc98c8b01ea0499726b84', '5addd4506b9064043c64005c'),
     ('5addc9876b9064043d24b1ce', '5addd4578b01ea0499727020'),
     ('5addd9548f9c14049f1f01e8', '5aded6e86b9064043c6470c7'),
     ('5add9ec26b9064043d249162', '5adda1df6b9064043c63db01'),  # see https://programs.edraak.org/learn/repository/math-arithmetics-oers-v1/component/5add9ec26b9064043d249162
     ('5add9f108f9c14049f1ed238', '5adda1e28b01ea0499724f8e'),
     ('5add9ef68b01ea0499724e2a', '5adda2038f9c1404a0d16155'),
     ('5add9ef58f9c14049f1ed237', '5adda2078f9c14049f1ed42b'),
     ('5add9ef26b9064043d249163', '5adda20a8b01ea049a76c048'),
     ('5add9ef18f9c1404a0d15b8d', '5adda20d6b9064043d24923f'),
     ('5add9eec8f9c14049f1ed235', '5adda2146b9064043d249241'),
     ('5add9eea8f9c14049f1ed234', '5adda2198f9c1404a0d16159'),
     ('5add9ee88b01ea049a76bee2', '5adda21c8b01ea0499724f92'),
     ('5add9ee56b9064043c63d966', '5adda21f6b9064043c63db07'),
     ('5add9ee36b9064043c63d965', '5adda2226b9064043c63db09'),
     ('5add9ee16b9064043c63d964', '5adda2278f9c14049f1ed42d'),
     ('5add9edf6b9064043c63d963', '5adda22a8b01ea049a76c04a'),
     ('5add9ede8f9c1404a0d15b8c', '5adda22f8b01ea0499724f94'),
     ('5add9ed88b01ea049a76bee1', '5adda2336b9064043d249243'),
     ('5adda13b6b9064043d24921d', '5adda2368b01ea0499724f96'),
     ('5ad46e1b6b9064043e25a010', '5ad47eab6b9064043d8b53bb'),
     ('5ad46f84f342d704a6252676', '5ad47fb16b9064043e25aca4'),
     ('5ad46355f342d704a74e337f', '5ad463523a891b049fe40a50'),
     ('5ad4657d6b9064043e25978c', '5ad465783a891b049fe40d23'),
     ('5ad4680a3a891b049fe410b9', '5ad468376b9064043e259b27'),
     ('5b4e3ad845dea204a16048d8', '5b4e3b1321eb8704a0b6c061'),
     ('5ad4682d6b9064043e259b24', '5ad4682d3a891b049fe410bd')]
 


## Bad URLs in Exercises

  - Question 5a58818d7dd197717bd5d478: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-sealed.gif
  - Question 5a58818d7dd197717bd5d478: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-sealed.gif
  - Question 5a5890737dd197717c9aef08: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-smile.gif
  - Question 5a5890737dd197717c9aef08: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-smile.gif
  - Question 5a572acf7dd197717bd532ea: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-wink.gif
  - Question 5a572acf7dd197717bd532ea: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-wink.gif
  - Question 5a5731667dd197717bd53532: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-cool.gif
  - Question 5a5731667dd197717bd53532: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-cool.gif
  - Question 5a4c845f7dd1970908580734: file:////Users/rayazubyoklah/Library/Group%20Containers/UBF8T346G9.Office/msoclip1/01/clip_image001.gif
  - Question 5a4c845f7dd1970908580734: file:////Users/rayazubyoklah/Library/Group%20Containers/UBF8T346G9.Office/msoclip1/01/clip_image001.gif
  - Question 5a4c845f7dd1970908580734: file:////Users/rayazubyoklah/Library/Group%20Containers/UBF8T346G9.Office/msoclip1/01/clip_image002.gif
  - Question 5a4c845f7dd1970908580734: file:////Users/rayazubyoklah/Library/Group%20Containers/UBF8T346G9.Office/msoclip1/01/clip_image002.gif
  - Question 5a5cb5747dd197717bd721f8: file:////Users/rayazubyoklah/Library/Group%20Containers/UBF8T346G9.Office/msoclip1/01/clip_image001.gif
  - Question 5a5cb5747dd197717bd721f8: file:////Users/rayazubyoklah/Library/Group%20Containers/UBF8T346G9.Office/msoclip1/01/clip_image001.gif
  - Question 5a5b19557dd197717bd6ba49: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-cool.gif
  - Question 5a5b19557dd197717bd6ba49: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-cool.gif
  - Question 5a4ded527dd1972c134bb3e5: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-foot-in-mouth.gif
  - Question 5a4ded527dd1972c134bb3e5: https://d3n43jef99gosn.cloudfront.net/static/bower_components/tinymce/plugins/emoticons/img/smiley-foot-in-mouth.gif
  - Question 5b4ee4866b9064043d4115d3: https://lh6.googleusercontent.com/gstaMJWS4B8-aFGxfIOZ4Twqd6WPOoAaiUgpS5yKHvGJ0FhK6NkoFNI4m9LCPsGuIkPztEQq2LKOmvdQISjNr-Ms4yfovo8XwTwvZFAftx803OF5KfE3S2b_r9vNVLNRvSLJ9zgv7xNgeZkOpg
  - Question 5b4ee4866b9064043d4115d3: https://lh6.googleusercontent.com/gstaMJWS4B8-aFGxfIOZ4Twqd6WPOoAaiUgpS5yKHvGJ0FhK6NkoFNI4m9LCPsGuIkPztEQq2LKOmvdQISjNr-Ms4yfovo8XwTwvZFAftx803OF5KfE3S2b_r9vNVLNRvSLJ9zgv7xNgeZkOpg


