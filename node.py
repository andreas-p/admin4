# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import os, adm, wx
import logger
from wh import xlt, StringType, sizeToFloat, floatToSize


class NodeType:
  def __init__(self, name):
    if isinstance(name, type):
      self.type=name.__name__
    elif isinstance(name, (NodeType)):
      self.name=name.name
    elif isinstance(name, (Node, NodeId)):
      self.name=name.type.name
    elif isinstance(name, StringType):
      self.name=name
    else:
      raise Exception("Not supported")

  def __str__(self):
    return "<%s>" % self.name
  def __eq__(self, t):
    return self.name == t.name

class NodeId:
  def __init__(self, typeOrInst, name=None):
    """
    NodeId(nodeType)
    NodeId(nodeInstance, name)
    """
    if not name:
      name=typeOrInst
    if isinstance(typeOrInst,NodeType):
      self.type=typeOrInst
    else:
      self.type=NodeType(typeOrInst)
    if isinstance(name, StringType):
      self.name=name
    else:
      self.name=name.name

  def __str__(self):
    return  "<%s.%s>" % (self.type.name, self.name)

  def __eq__(self, o):
    return self.type == o.type and self.name == o.name


class Node(object):
  """
  class adm.Node

  Representation of an object on the server or the server itself.
  could also be a collection of nodes
  May be hosted by many trees
  """

  wantIconUpdate=False

  def __init__(self, parentNode, name):
    self.treeitems={}
    self.childnodes=[]
    self.parentnodes=[]
    self.properties=[]
    self.statistics=None
    self.dependsOn=None
    self.referencedBy=None
    self.server=None
    self.connection=None
    self.comment=None
    self.detachedWindow=None

    self.parentNode=parentNode
    self.name=name
    self.module=adm.getModule(self)
    self.type=self.MakeType()
    self.id=NodeId(self)

  def __str__(self):
    return "<%s %s>" % (self.id.type.name, self.id.name)

  def moduleClass(self):
    m=self.__module__
    cls=m[:m.find('.')]
    return cls

  def CleanupDetached(self):
    pass
  
  def CheckConnection(self, connection):
    if not connection or connection.HasFailed():
      if connection and hasattr(connection, 'lastError'):
        err=connection.lastError
      else:
        err=""
      if hasattr(self, 'waitingFrame'):
        frame=self.waitingFrame
        if frame:
          adm.StopWaiting(frame)
      else:
        frame=adm.GetCurrentFrame()
      if frame:
        frame.SetStatus(xlt("disconnected: %s") % err)
      raise adm.NoConnectionException(self, None)

  
  def GetIcon(self):
    return self.GetImageId(self.__class__.__name__)

  def GetAddress(self):
    if hasattr(self, "address"):
      return self.address
    return self.name

  def GetComment(self):
    return self.comment

  def IsPageAvailable(self, pageClass, _detached):
    classes=self.nodeinfo().get('pages')
    if not classes:
      return False
    if not isinstance(pageClass, StringType):
      pageClass=pageClass.__name__
    if isinstance(classes, StringType):
      classes=classes.split(' ')
    elif not isinstance(classes, list):
      classes = [classes]
    for cls in classes:
      if not isinstance(cls, StringType):
        cls=cls.__name__
      if cls == pageClass:
        return True
    return False

  
  def IconUpdate(self, force=False):
    if self.wantIconUpdate or force:
      if self.treeitems:
        icon=self.GetIcon()
        txt=self.GetLabelText()
        for treename,itemlist in self.treeitems.items():
          tree=adm.trees[treename]
          for item in itemlist:
            if tree.GetItemImage(item) != icon:
              tree.SetItemImage(item, icon)
            if tree.GetItemText(item) != txt:
              tree.SetItemText(item, txt)

    for node in self.childnodes:
      node.IconUpdate()

  def MakeType(self, cls=None):
    if not cls:
      cls=self.__class__.__name__
    elif isinstance(cls, NodeType):
      return NodeType(cls)
    elif not isinstance(cls, StringType):
      cls=cls.__name__
    return NodeType("%s.%s" % (self.module, cls))

  def MakeCollectionType(self, cls):
    if not isinstance(cls, StringType):
      cls=cls.__name__
    return NodeType("%s.%s-coll" % (self.module, cls))

  def MayHaveChildren(self):
    return len(self.nodeinfo()['children']) > 0


  def GetImageId(self, *names):
    names=list(names)
    if isinstance(names[0], list):
      names=names[0]
    if len(names)==1:
      return adm.images.GetId(os.path.join(self.module, names[0]))

    return adm.images.GetJoinedId(map(lambda name: self.GetImageId(name), names))

  def GetInfo(self):
    return ""

  def GetServer(self):
    if self.server:
      return self.server
    if self.parentNode:
      return self.parentNode.GetServer()
    return None

  def GetConnection(self):
    if self.connection:
      self.CheckConnection(self.connection)
      return self.connection
    if self.parentNode:
      return self.parentNode.GetConnection()
    return None

  def appendChild(self, child):
    self.childnodes.append(child)
    child.parentnodes.append(self)
    for treename, itemlist in self.treeitems.items():
      tree = adm.trees[treename]
      if tree.autoChildren:
        for item in itemlist:
          tree.Append(item, child)


  def removeChild(self, child):
    if child in self.childnodes:
      self.childnodes.remove(child)
    if self in child.parentnodes:
      child.parentnodes.remove(self)
    if not self.childnodes:
      for treename, itemlist in self.treeitems.items():
        for item in itemlist:
          adm.trees[treename].Collapse(item)
      
        
        
  def RefreshVolatile(self, force=False):
    pass

  def Refresh(self):
    self.DoRefresh()

  def DoRefresh(self):
    self.properties=[]
    
    for child in self.childnodes:
      self.removeChild(child)
    if self.GetServer().IsConnected():
      self.RefreshVolatile(True)
  
      for treename, itemlist in self.treeitems.items():
        for item in itemlist:
          adm.trees[treename].Refresh(item, self)

  def RemoveFromTree(self, doRefresh=True):
    if self.parentNode:
      self.parentNode.removeChild(self)
    for treename in self.treeitems.keys():
      tree=adm.trees[treename]
      tree.DeleteNode(self)
    if doRefresh and self.parentNode:
        self.parentNode.DoRefresh()

  # some Property helper
  def AddProperty(self, txt, value, imageid=-1):
    if not isinstance(imageid, int):
      imageid=self.GetImageId(imageid)
    if isinstance(value, list):
      value = ", ".join(value)
    self.properties.append( (txt, value, imageid) )

  def AddYesNoProperty(self, txt, value, imageid=-1):
    if value:
      v=xlt("Yes")
    else:
      v=xlt("No")
    self.AddProperty(txt, v, imageid)

  def AddSizeProperty(self, txt, value, imageid=-1):
    if not isinstance(value, float):
      value=sizeToFloat(value)
    self.AddProperty(txt, floatToSize(value), imageid)

  def AddChildrenProperty(self, childlist, txt, className, valExtractor=None):
    """
    AddChildrenProperty(self, childlist, txt, className, valExtractor=None)
    AddChildrenProperty(self, childlist, txt, iconId, valExctractor=None)

    Add <childlist> items to self.properties with txt and Bitmap from className
    items can be formatted by the valExtractor proc
    """
    if childlist == None:
      return False
    if not isinstance(childlist, list):
      childlist=[childlist]
    if isinstance(className, int):
      imageid=className
    else:
      imageid=self.GetImageId(className)
    for info in childlist:
      if valExtractor:
        info=valExtractor(info)
      self.AddProperty(txt, info, imageid)
      txt=""
      imageid=0
    return len(childlist)>0


  def GetCollection(self, cls):
    for c in self.childnodes:
      if c.nodeclass == cls:
        return c
    return None
  
  
  def FindNode(self, toFind, arg2=1, level=1):
    """
    FindNode(nodeId, level=-1)
    FindNode(nodeModule, nodeName, level=-1)

    Find a child node recursively <level> deep
    """
    if isinstance(arg2, int):
      level=arg2
    else:
      toFind=NodeId(self.MakeType(toFind), arg2)

    self.PopulateChildren()
    for cn in self.childnodes:
      if isinstance(toFind, NodeId):
        if cn.id == toFind:
          return cn
      else:
        if cn.name == toFind:
          return cn
    if level > 1:
      for cn in self.childnodes:
        rc=cn.FindNode(toFind, level-1)
        if rc:
          return rc
    return None

  def FindNodePath(self, findList):
    node=self
    for toFind in findList:
      node=node.FindNode(*toFind)
      if not node:
        logger.debug("Node path %s not found", str(toFind))
        return None
    return node

  def PopulateChildren(self):
    if len(self.childnodes) > 0:
      return

    logger.debug("Populating %s %s", self.type, self.name)
    self.childnodes=[]

    if isinstance(self, Collection):
      childlist=[self.nodeclass.__name__]
    else:
      childlist=self.nodeinfo()['children']

    if not childlist:
      return
    for nodename in childlist:
      nodeinfo=self.moduleinfo()['nodes'][nodename]
      collText=nodeinfo.get('collection')
      cls=nodeinfo['class']
      if collText and not isinstance(self, Collection):
        child=Collection(self, collText, cls)
        self.appendChild(child)
      else:
        if isinstance(self, Group):
          self.GetProperties() # make sure child list is populated
        if hasattr(cls, 'GetInstances'):
          children=cls.GetInstances(self)
        else:
          children=cls.GetInstancesFromClass(self)
        if children != None:
          for child in children:
            self.appendChild(child)


  def GetLabelText(self):
    if self.name:
      return xlt("%s \"%s\"") % (xlt(self.shortname), xlt(self.name))
    else:
      return xlt(self.typename)

  def GetPropertiesHeader(self):
    return (xlt("Property"), xlt("Value"))

  def GetProperties(self):
    return []

  def moduleinfo(self):
    return adm.modules[self.module].moduleinfo

  def nodeinfo(self, item=None):
    if item:
      if isinstance(item, Node):
        item=item.__class__.__name__
    else:
      item=self.__class__.__name__
    return self.moduleinfo()['nodes'][item]

  def menuinfos(self):
    return self.moduleinfo()['menus']

  @staticmethod
  def isValidChild(parentNode, name):
    if isinstance(parentNode, Group):
      return name in parentNode.childlist
    return True

class Group(Node):
  def __init__(self, parentNode, name, memberclass):
    Node.__init__(self, parentNode, name)
    self.firstMemberItem=9999999
    self.childlist=[]
    self.memberclass=memberclass
    if memberclass:
      self.memberIcon=adm.images.GetId(os.path.join(self.module, memberclass.__name__))
    else:
      self.memberIcon=-1

  def GetIcon(self):
    id=-1;
    if self.memberclass:
      id=adm.images.GetId(os.path.join(self.module, "%ss" % self.memberclass.__name__))
    if id == -1:
      return self.memberIcon
    return id


  def GetItemNode(self, page, index):
    if isinstance(page, adm.PropertyPage) and index >= self.firstMemberItem:
      childname=self.childlist[index-self.firstMemberItem]
      return self.FindNode(self.memberclass, childname)
      toFind=NodeId(self.MakeType(self.memberclass), childname)
      return self.FindNode(toFind)

      self.PopulateChildren()

      for c in self.childnodes:
        if c.id == toFind:
          return c
      tree=adm.GetCurrentTree(page)
      item=tree.Find(None, toFind, 2)
      if item:
        return tree.GetNode(item)
    return None

  def GetInfo(self):
    return xlt("%d %s") % (len(self.childlist), self.shortname)

  @staticmethod
  def GetGroupInstances(parentNode, groupclass, memberlist, validproc=Node.isValidChild):
    childlist=[]
    if not isinstance(memberlist, list):
      memberlist=[memberlist]
    for name in memberlist:
      if validproc(parentNode, name):
        childlist.append(groupclass(parentNode, name))
    return childlist

  def GetGroupProperties(self, txt, memberlist=None):
    if not memberlist:
      memberlist=self.childlist

    self.properties= [
         ( xlt("Name"),self.name),
         ]
    self.firstMemberItem=len(self.properties)
    self.AddChildrenProperty(memberlist, txt, self.memberIcon)

#    imageid=self.memberIcon
#    for member in memberlist:
#      self.properties.append( (txt, member, imageid))
#      txt=""
#      imageid=0
    return self.properties


class Collection(Node):
  """
  class Collection

  A collection automatically creates a grouping node for its nodes
  
  Collections are typed after their members "<classname>-coll", and named after their parents
  """
  def __init__(self, parentNode, name, cls):
    Node.__init__(self, parentNode, name)
    self.typename=name
    self.shortname=name
    self.name=None
    self.nodeclass=cls

    tmp=cls.__module__
    self.module=tmp[:tmp.find('.')]

    self.type=self.MakeCollectionType(cls)
    self.id=NodeId(self, parentNode)

  def GetIcon(self):
    id=adm.images.GetId(os.path.join(self.module, "%ss" % self.nodeclass.__name__))
    if id == -1:
      return adm.images.GetId(os.path.join(self.module, self.nodeclass.__name__))
    return id

  def IsPageAvailable(self, cls, _detached):
    return False
  
  def nodeinfo(self, _item=None):
    return self.moduleinfo()['nodes'][self.nodeclass.__name__]

  def MayHaveChildren(self):
    return True

  def GetInfo(self):
    return xlt("%d %s") % (len(self.childnodes), self.typename)

  def GetPropertiesHeader(self):
    return (self.typename, xlt("Comment"))

  def GetProperties(self):
    if not len(self.childnodes):
      self.PopulateChildren()
    list=[]
    icon=self.GetImageId(self.nodeclass.__name__)
    for child in self.childnodes:
      list.append((child.name, child.GetComment(), icon))
    return list


class ServerNode(Node):
  def __init__(self, settings, _password=None):
    Node.__init__(self, None, settings['name'])

    self.registrationChanged=False
    self.server=self
    self.settings=settings
    self.address = self.settings.get('host')
    self.user=self.settings.get('user')
    self.port=self.settings.get('port')
    self.needPassword=(self.settings.get('password') != None)

  def SetCfgString(self, cmd, value):
    adm.config.Write("%s/%s" % (self.module, cmd), value)

  def GetCfgString(self, cmd, default=None):
    cfg=adm.config.Read("%s/%s" % (self.module, cmd), default)
    return cfg
  
  def GetPreference(self, key):
    prefs=self.moduleinfo()['preferences']
    return prefs.GetPreference(key)
  

  def Disconnect(self):
    self.connection=None
    return True
  
  def GetInfo(self):
    if self.IsConnected():
      le=self.GetLastError()
      if le:
        return xlt("Connection error: %s") % le
      else:
        return xlt("connected")
    else:
      return xlt("not connected")

  def IsConnected(self, _deep=False):
    return self.server != None

  def IsHealthy(self):
    return self.server != None

  def Connect(self, parentWin):
    """
    Connect(parentWin) returns
    True: connected
    False: error
    None: aborted
    """
    self.connectException=None
    self.password=self.settings.get('password')
    self.user=self.settings.get('user')
    if not self.password and self.user:
      self.password, remember = adm.AskPassword(parentWin, xlt("Password for %s:" % self.user), xlt("Enter password for %(type)s \"%(name)s\"") 
                                       % { "type": self.typename, "name": self.name }, True )
      if self.password == None:
        return None
      if remember:
        self.settings['password'] = self.password
        adm.config.storeServerSettings(self, self.settings)

    rc=self.DoConnect()
    return rc


  def ExternExecute(self, _parentWin, cmd, address, port, **kargs):
    call=self.GetCfgString(cmd)

    call=call.replace("%h", address)
    call=call.replace("%p", str(port))
    user=kargs.get('user')
    if user != None:
      call=call.replace("%u", user)
    password=kargs.get('password', "")
    if password != None:
      call=call.replace("%P", password)

    logger.debug("ExternCall %s", call)
    pid=wx.Execute(call)
    return pid
