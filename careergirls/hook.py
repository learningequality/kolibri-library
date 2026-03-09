from ricecooker.managers.tree import ChannelManager
from ricecooker.classes.nodes import TopicNode


old_nodes = ChannelManager.add_nodes

def new_nodes(*args, **kwargs):
    self = args[0]
    print ("add_nodes called")
    retval = old_nodes(*args, **kwargs)
    print ("add_nodes exited")
    fails = self.failed_node_builds
    if fails:
        for fail in fails.values():
            node = fail['node']
            for child in node.children:
                for f in child.files:
                    print (f.is_primary, f.filename, f)
            break



    return retval

# ChannelManager.add_nodes = new_nodes
