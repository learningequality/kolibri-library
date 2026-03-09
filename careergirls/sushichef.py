#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from urllib.parse import urljoin
import logging
from ricecooker.chefs import SushiChef
from ricecooker.classes.licenses import SpecialPermissionsLicense
from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode, HTML5AppNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile, YouTubeVideoFile, YouTubeSubtitleFile, DocumentFile, ThumbnailFile
import cg_index
from le_utils.constants.roles import COACH, LEARNER
from le_utils.constants.languages import getlang
import clusters # role_data top secon
import hook
import lessons # import student_resources, lesson_index
 
LOGGER = logging.getLogger()
LICENCE = SpecialPermissionsLicense("Career Girls", "For use on Kolibri")
DEBUG = True

disambig_number=0
def disambig():
    global disambig_number
    disambig_number = disambig_number + 1
    return disambig_number


def make_youtube_video(tubeid, name, _id):
    video_file = YouTubeVideoFile(youtube_id = tubeid, language=getlang('en').code, high_resolution=False)
    if video_file is None:
        print ("No video.")
        return None 
    subtitle_file = YouTubeSubtitleFile(youtube_id = tubeid, language=getlang('en').code)
    if not isinstance(_id, str):
        print (_id, type(_id))
    content_node = VideoNode(
          source_id= str(_id),
          title= name,
          #author='First Last (author\'s name)',
          #description='Put file description here',
          language=getlang('en').code,
          license=LICENCE,
          files=[video_file, subtitle_file],
    )
    return content_node
    
class CareerGirlsChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'careergirls.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'careergirls',         # channel's unique id
        'CHANNEL_TITLE': 'Career Girls',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        'CHANNEL_THUMBNAIL': 'https://files.constantcontact.com/02b8739a001/91725ebd-c07b-4629-8b55-f91fd79919db.jpg',
        'CHANNEL_DESCRIPTION': "CareerGirls.org is a comprehensive video-based career exploration tool for girls. It contains the largest online collection of career guidance videos focusing exclusively on diverse and accomplished women. The Career Girls collection includes video clips featuring women role models who work in hundreds of wide-ranging careers with an emphasis on Science, Technology, Engineering, and Math (STEM).",  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
 
        def add_resources(resources, node, role=LEARNER):
            for title, url in resources:
                pdf_node = DocumentNode(source_id = "pdf_"+url,
                                        title = title,
                                        license = LICENCE,
                                        files = [DocumentFile(path=url)],
                                        role = role
                                       )
                node.add_child(pdf_node)
  
        def get_things(all_things, parent_node, new_node=True):
            for thing in all_things:
                _id = thing.url.strip('/').split('/')[-1] # TODO hash
                if new_node:
                    this_node = TopicNode(source_id = thing.url,
                                           title=thing.title)
                else:
                    this_node = parent_node
                content_node = make_youtube_video(thing.youtube, "Video: {}".format(thing.title), "video__{}".format(thing.url)) # TODO hash
                if content_node is not None:
                    this_node.add_child(content_node)
               
                try:
                    os.mkdir('html')
                except Exception:
                    pass
                fn = "html/{}.zip".format(_id)
                with open(fn, "wb") as f:
                    f.write(thing.app)
                app_zip = HTMLZipFile(fn)
                if thing.title[0] in "AEIOUaeiou":
                    an = "an"
                else:
                    an = "a" 
                app_node = HTML5AppNode(source_id = "app_{}".format(thing.url),
                                        title = "Being {} {}".format(an, thing.title),
                                        license = LICENCE,
                                        files=[app_zip])
            
                this_node.add_child(app_node)
                if new_node:
                    parent_node.add_child(this_node)
 
        video_list = []
        video_set = set()
        channel = self.get_channel(**kwargs)
        
        role_node = TopicNode(source_id="roles", title="Career Clusters")
        life_skill_node = TopicNode(source_id="lifeskills", title="Life Skills")
        lessons_node = TopicNode(source_id = "lessons", title = "Career-Based Empowerment Lessons",
                                 description = "What is your passion? What are you good at? Whether you think you want to be a fashion designer, a filmmaker, an engineer, or something else, these are two questions you might ask yourself when you think about a career. Watch our role models to learn more.")

        resources_node = TopicNode(source_id="resources", title="Student Resources")
        skill_node = TopicNode(source_id="skill", title="Skill-Based Empowerment Lessons")
        major_node = TopicNode(source_id="major", title="College Majors and Requirements")
        advice_node = TopicNode(source_id="advice", title="College Advice")
        educators_node = TopicNode(source_id="edu", title="Educators, Parents and Mentors") 
        channel.add_child(role_node)
        channel.add_child(lessons_node)
        channel.add_child(resources_node)
        channel.add_child(skill_node)
        channel.add_child(major_node)
        channel.add_child(advice_node)
        channel.add_child(educators_node)

        import majors
        for app in majors.apps:
            major_node.add_child(app)

        if DEBUG: return channel 
        import educators
        for app in educators.apps:
            educators_node.add_child(app)
        for title, resources in educators.resources:
            node = TopicNode(source_id="edu"+title, title=title)
            educators_node.add_child(node)
            add_resources(resources, node, COACH)
        # college advice and lifeskills

        import advice
        for id_, title in advice.videos:
            advice_node.add_child(make_youtube_video(id_, title, id_))
        add_resources(advice.resources, advice_node)

        import skills
        for id_, title in skills.videos:
            skill_node.add_child(make_youtube_video(id_, title, id_))
        add_resources(skills.resources, skill_node)

        if DEBUG: return channel 
 
        _lessons, resources = lessons.lesson_index()
        for lesson in _lessons:
            lesson_node = TopicNode(source_id=lesson.title, title=lesson.title, description=lesson.description)
            for video in lesson.video_ids:
                 lesson_video = make_youtube_video(video, lesson.title, video)
                 lesson_node.add_child(lesson_video)
            add_resources(lesson.resources, lesson_node)
            lessons_node.add_child(lesson_node)

        add_resources(lessons.student_resources(), resources_node)
        
        #return channel # TODO
        
        all_life_skills = list(cg_index.all_life_skills())
        get_things(all_life_skills, life_skill_node)
        
        all_jobs = list(cg_index.all_jobs())#
        # each job has a job.title.
        # TODO WRONG get_things(all_jobs, job_node) -- reimplement 


        # role models
        # setup
        top_lookup = {}
        second_lookup = {}
        for top in clusters.top:
            node = TopicNode(source_id = "role_top_"+top,
                             title = top,
                             description = clusters.cluster_meta[top]['desc'],
                             thumbnail = ThumbnailFile(urljoin("https://careergirls.org/", clusters.cluster_meta[top]['img'])))
            top_lookup[top] = node
            role_node.add_child(node)
        for top, second in clusters.second:
            node = TopicNode(source_id = "role_top_"+top+"_"+second,
                             title = second)
            second_lookup[tuple([top, second])] = node
            top_lookup[top].add_child(node)
            # add "Jobs" tree segment which is relevant
            relevant_jobs = [x for x in all_jobs if x.title == second]
            assert relevant_jobs, "No job for " + repr(second)
            get_things(relevant_jobs, node, new_node=False)
            # dragon ^^^ untested
            
        role_urls = set()
        # populate role_urls with list of all job titles
        for job in all_jobs:
            for role in job.roles:
                role_urls.add(role)

        for role_url in sorted(list(role_urls)):
            _id = role_url.strip('/').split('/')[-1]
            role = cg_index.index_role(role_url)
                          
            role_found= False
            for cluster_role in clusters.role_data:
                if cluster_role[3] in role_url:
                    ## this section was outside the loop before
                    this_role = TopicNode(source_id = "role__{}_{}".format(_id, disambig()),
                                          title="{}, {}".format(role.title, role.name),
                                          description = role.bio)
                    for v_id, v_name in zip(role.video_ids, role.video_names):
                        if v_id is not None:
                            video_node = make_youtube_video(v_id[0], v_name[0], v_id[0])
                            this_role.add_child(video_node)
                            video_list.append(v_id[0])
                            video_set.add(v_id[0])
                    ## end section that was outside the loop before
                    second_lookup[tuple(cluster_role[:2])].add_child(this_role)

                    role_found = True
            assert role_found, role_url
                
            # role_node.add_child(this_role)
        
        print ("DONE")
            
            # todo? : role.skill_links, role.skill_names
                        
            
            
        
            
        
        return channel
    
if __name__ == '__main__':
    """
    Set the environment var `CONTENT_CURATION_TOKEN` (or `KOLIBRI_STUDIO_TOKEN`)
    to your Kolibri Studio token, then call this script using:
        python souschef.py  -v --reset
    """
    mychef = CareerGirlsChef()
    if 'KOLIBRI_STUDIO_TOKEN' in os.environ:
        os.environ['CONTENT_CURATION_TOKEN'] = os.environ['KOLIBRI_STUDIO_TOKEN']
    mychef.main( )
