# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage



import wx
import adm
import logger
from wh import xlt, Menu, StringType


def TreeItemData(data):
  return data

class TreeCtrl(wx.TreeCtrl):
  def __init__(self, parentWin, name, size=wx.DefaultSize, style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT):
    wx.TreeCtrl.__init__(self, parentWin, size=size, style=style)
    parentWin.SetBackgroundColour(wx.WHITE)
    self.SetImageList(adm.images)
    self.AddRoot(name)
    if wx.Platform != "__WXMSW__":
      pt=parentWin.GetFont().GetPointSize() * 0.95  # a little smaller
      font=wx.Font(pt, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL)

      self.SetFont(font)
    

  def Match(self, item, patterns, case=False):
    if isinstance(patterns, StringType):
      patterns=patterns.split()
    txt=self.GetItemText(item)
    if not case:
      txt=txt.lower()
    found=0
    for p in patterns:
      if txt.find(p) >= 0:
        found += 1
    return found == len(patterns)
  
  def FindPattern(self, currentItem, patterns, case=False):
    "Find(currentItem, pattern) matches currentItem and children against patterns"
    if self.Match(currentItem, patterns, case):
      return currentItem
    for item in self.GetChildItems(currentItem):
      found=self.FindPattern(item, patterns)
      if found:
        return found
    return None
  
  def GetNode(self, item=None):
    if not item:
      item=self.GetSelection()
    if item:
      return self.GetItemData(item)
    return None 

  def GetFrame(self):
    w=self.GetParent()
    while w and not isinstance(w, adm.Frame):
      w=w.GetParent()
    return w

  def GetChildItems(self, item):
    itemlist=[]
    i, cookie=self.GetFirstChild(item)
    while i:
      itemlist.append(i)
      i,cookie=self.GetNextChild(item, cookie)
    return itemlist
  
####################################################################################

class DragTreeCtrl(TreeCtrl):
  def __init__(self, parentWin, name, size=wx.DefaultSize, style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT):
    TreeCtrl.__init__(self, parentWin, name, size, style)
    self.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnBeginDrag)
    self.Bind(wx.EVT_TREE_END_DRAG, self.OnEndDrag)


  def OnBeginDrag(self, evt):
    self.currentItem = evt.GetItem()
    evt.Allow()
  
  def OnEndDrag(self, evt):
    targetItem=evt.GetItem()
    self.ExecuteDrag(targetItem)

####################################################################################

class NodeTreeCtrl(TreeCtrl):
  def __init__(self, parentWin, name, size=wx.DefaultSize, style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT):
    TreeCtrl.__init__(self, parentWin, name, size=size, style=style)
    self.name=name
    if name:
      adm.trees[name]=self
    self.autoChildren=True
    self.Bind(wx.EVT_RIGHT_DOWN, self.OnTreeRightClick)
    self.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.OnTreeExpand)
    self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnTreeActivate)


  def OnTreeActivate(self, evt):
    node=self.GetNode(evt.GetItem())
    if not node:
      return
    if hasattr(node, "Edit"):
      node.Edit(self.GetFrame())

  def OnTreeExpand(self, evt):
    node=self.GetNode(evt.GetItem())
    if not node:
      return

    if len(node.childnodes) == 0:
      node.PopulateChildren()

    if len(node.childnodes) == 0:
      self.Collapse(evt.GetItem())
      
  def OnTreeRightClick(self, evt):
    item, _flags=self.HitTest(evt.GetPosition())
    if not item:
      return
    if item != self.GetSelection():
      self.SelectItem(item)

    node=self.GetNode(item)
    if node:
      node.RefreshVolatile()
      w=self.GetFrame()
      node.GetProperties()
      cm=w.GetContextMenu(node)
      cm.Popup(evt)

  
  def SelectNode(self, node, delayed=False):
    itemlist=node.treeitems.get(self.name)
    if itemlist:
      item=itemlist[0]
      if delayed:
        tev=wx.TreeEvent(wx.wxEVT_COMMAND_TREE_SEL_CHANGED, self, item)
        self.AddPendingEvent(tev)
      else:
        self.SelectItem(item)
    else:
      logger.debug(xlt("Expected %s in tree %s not found"), node.id, self.name)
    return item


  def Append(self, parentItem, node):
    """
    wx.TreeItem Append(self, parentItem, node)
    """
    if not parentItem:
      parentItem=self.GetRootItem()
    txt=node.GetLabelText()

    image=node.GetIcon()
    simage=-1

    item=self.AppendItem(parentItem, txt, image=image, selImage=simage, data=TreeItemData(node))
    if node.treeitems.get(self.name) == None:
      node.treeitems[self.name] = []
    node.treeitems[self.name].append(item)
    if node.MayHaveChildren():
      self.SetItemHasChildren(item, True)
    for child in node.childnodes:
      self.Append(item, child)
    return item


  def IsChild(self, child, parent):
    c, cookie=self.GetFirstChild(parent)
    while (c):
      if c == child:
        return True
      if self.IsChild(child, c):
        return True
      c,cookie=self.GetNextChild(parent, cookie)
    return False


  def Refresh(self, item, node=None):
    if not node:
      node=self.GetNode(item)

    postExpand=False
    if self.IsChild(self.GetSelection(), item):
      self.SelectItem(item)
      postExpand=True
    self.Collapse(item)
    self.DeleteChildren(item)

    self.SetItemText(item, node.GetLabelText())
    self.SetItemImage(item, node.GetIcon())
    self.SetItemHasChildren(item, node.MayHaveChildren())
      
    if item == self.GetSelection():
      fr=self.GetFrame()
      if fr and hasattr(fr, "details"):
        fr.details.Set(node)

    if postExpand:
      node.PopulateChildren()
    if len(node.childnodes) > 0:
      self.Expand(item)


  def doFind(self, item, toFind, level=99):
    o = self.GetNode(item)
    if o:
      if isinstance(toFind, adm.Node):
        if o == toFind:
          return item
      elif isinstance(toFind, adm.NodeId):
        if o.id.name == toFind.name and o.id.type==toFind.type:
          return item
      else:
        if o.name == toFind:
          return item

    if level > 0:
      i, cookie=self.GetFirstChild(item)
      while i:
        rc=self.doFind(i, toFind, level-1)
        if rc:
          return rc
        i,cookie=self.GetNextChild(item, cookie)

    if item == self.GetRootItem():
      return None

    i=self.GetNextSibling(item)
    if i:
      return self.doFind(i, toFind, level)
    return None


  def Find(self, item, toFind, level=99):
    if not item:
      item=self.GetRootItem()

    i, cookie=self.GetFirstChild(item)
    while i:
      rc=self.doFind(i, toFind, level)
      if rc:
        return rc
      i,cookie=self.GetNextChild(item, cookie)
    return None


  def DeleteChildren(self, item):
    for i in self.GetChildItems(item):
      self.DeleteChildren(i)
      node=self.GetNode(i)
      if node:
        self.DeleteNode(node)
      else:
        self.DeleteItem(i)


  def DeleteNode(self, node):
    itemlist=node.treeitems[self.name]
    for item in itemlist:
      self.Delete(item)
    del node.treeitems[self.name]
    for parent in node.parentnodes:
      parent.removeChild(node)


  def DeleteItem(self, item):
    node=self.GetNode(item)
    self.Delete(item)

    if node:
      itemlist=node.treeitems[self.name]
      itemlist.remove(item)
      if not itemlist:
        del node.treeitems[self.name]




###########################################################################


class ServerTreeCtrl(DragTreeCtrl):
  def __init__(self, parentWin, size=wx.DefaultSize, style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT):
    DragTreeCtrl.__init__(self, parentWin, "Server", size=size, style=style)
    self.groups={}
    self.nodes=[]
    self.Bind(wx.EVT_RIGHT_DOWN, self.OnTreeRightClick)
    self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnTreeActivate)
    self.currentNode=None
    self.currentItem=None
    
    for groupName in adm.config.Read("ServerGroups", []):
      self.addGroup(groupName)
    
    for server in adm.config.getServers():
      settings=adm.config.getServerSettings(server)
      if settings:
        logger.debug("Registering %s", server)
        self.RegisterServer(settings, True)
      else:
        logger.debug("Registration for %s missing", server)


  def ExecuteDrag(self, targetItem):
    targetNode=self.GetNode(targetItem)
    node=self.GetNode(self.currentItem)
    
    if self.currentItem != targetItem and targetNode != node:
      name=self.GetItemText(self.currentItem)
        
      if targetNode:
        groupName=targetNode.settings.get('group')
      else:
        groupName=self.GetItemText(targetItem)
      group=self.groups.get(groupName)

      if node:
        self.Delete(self.currentItem)
        node.settings['group'] = groupName
        adm.config.storeServerSettings(node, node.settings)
        if targetNode:
          self.InsertAfter(group, targetItem, node.name, node)
        else:
          self.Append(group, node.name, node)
      else:
        if group:
          group=self.InsertAfter(None, group, name, None)
        else:
          group=self.Append(None, name, None)
        self.groups[name]=group
        for item in self.GetChildItems(self.currentItem):
          node=self.GetNode(item)
          self.Append(group, node.name, node)
        self.Delete(self.currentItem)

    self.StoreServers()
  
  
  def OnTreeActivate(self, evt):
    node=self.GetNode(evt.GetItem())
    if not node:
      return
    self.ConnectServer(node, adm.mainframe.name)

    
  def OnAddGroup(self, _evt):
    dlg=wx.TextEntryDialog(self, xlt("Enter group name"), xlt("New server group"))
    rc=dlg.ShowModal()
    if rc == wx.ID_OK:
      groupName=dlg.GetValue()
      self.addGroup(groupName)

  def OnDelGroup(self, _evt):
    if self.currentItem:
      self.Delete(self.currentItem)
      self.StoreServers()
  
  def OnEdit(self, _evt):
    server=self.currentNode
    if hasattr(server, "Edit"):
      server.Edit(self.GetFrame())
  
  def OnUnregister(self, _evt):
    if self.currentNode:
      self.Delete(self.currentItem)
      self.StoreServers()
      
      
  def OnTreeRightClick(self, evt):
    item, _flags=self.HitTest(evt.GetPosition())
    self.currentNode=None
    self.currentItem=item
    frame=self.GetFrame()
    
    if item:
      if item != self.GetSelection():
        self.SelectItem(item)
      self.currentNode=self.GetNode(item)
    
    
    if self.currentNode:
      cm=Menu(frame)
      registerproc=self.currentNode.moduleinfo()['serverclass'].Register
      cm.Add(registerproc, xlt("Register new %s") % self.currentNode.moduleinfo()['name'])
      cm.Add(self.OnEdit, xlt("Edit registration"))
      cm.Add(self.OnUnregister, xlt("Remove registration"))
      
      if not self.currentNode.settings.get('group'):
        cm.Add(self.OnAddGroup, xlt("New group"))
    else:
        cm=self.GetFrame().registermenu.Dup()
        if item:
          menuItem=cm.Add(self.OnDelGroup, xlt("Remove group"))
          if self.GetChildrenCount(item) > 0:
            cm.Enable(menuItem, False)
        else:
          cm.Add(self.OnAddGroup, xlt("New group"))
      
    cm.Popup(evt)
    

  def getImage(self, name, server):
    if server:
      image=server.GetIcon()
    else:
      image=adm.images.GetId(name)
      if image < 0:
        image=adm.images.GetId("folder")
    return image
  
  def ExpandFirst(self):
    item,_cookie=self.GetFirstChild(self.GetRootItem())
    if item:
      self.Expand(item)
    
    
  def InsertAfter(self, parentItem, prev, name, data):
    image=self.getImage(name, data)
    if not parentItem:
      parentItem=self.GetRootItem()
      
    item=self.InsertItem(parentItem, prev, name, image=image, selImage=image, data=TreeItemData(data))
    return item

  def Append(self, parentItem, name, data):
    if not parentItem:
      parentItem=self.GetRootItem()

    if data:
      self.nodes.append(data)
    image=self.getImage(name, data)
    item=self.AppendItem(parentItem, name, image=image, selImage=image, data=TreeItemData(data))
    return item


  def StoreServers(self):
    groups=[]
    servers=[]
    
    for item in self.GetChildItems(self.GetRootItem()):
      node=self.GetNode(item)
      if node:
        servers.append("%s/%s" % (node.moduleClass(), node.name))
      else:
        groups.append(self.GetItemText(item))
        for item in self.GetChildItems(item):
          node=self.GetNode(item)
          if node:
            servers.append("%s/%s" % (node.moduleClass(), node.name))
    adm.config.Write("ServerGroups", groups)
    adm.config.Write("Servers", servers)
        

  def ConnectServer(self, server, treename):
    if not server.IsConnected(True):
      rc=False
      frame=adm.StartWaiting(xlt("Connecting to %(type)s %(name)s...") % { "type": server.typename, "name": server.name}, True)
      server.properties=[]
      try:
        rc=server.Connect(self)
      except adm.ConnectionException as _e:
        adm.StopWaiting(frame, xlt("Not connected"))
        return False

      if not rc:
        adm.StopWaiting(frame, xlt("Not connected"))
        if rc != None:
          wx.MessageBox(xlt("Connect failed."), xlt("%(type)s %(name)s") % { "type": server.typename, "name": server.name})
        return rc

      adm.StopWaiting(frame, xlt("connected."))
      server.registrationChanged=False

    tree=adm.trees.get(treename)
    if tree:
      item = tree.Find(None, server, 1)
      if not item:
        item=tree.Append(None, server)
    else:
      from frame import DetailFrame
      _frame=DetailFrame(self, treename) # IGNORE
      tree=adm.trees[treename]
      item=tree.Append(None, server)

    if server.settings.get('rememberLastNode', True):
      nodePath=server.settings.get('nodePath')
      if nodePath:
        for nodeId in nodePath.split('/'):
          typ,name=nodeId.split(':')
          nid=adm.NodeId(typ, name)
          if nid == server.id:
            continue
          tree.Expand(item)
          found=False
          for item in tree.GetChildItems(item):
            node=tree.GetNode(item)
            if node.id == nid:
              found=True
              break
          if not found:
            break

    tree.SelectItem(item)
    tree.EnsureVisible(item)
    tree.SetFocus()

    return True


  def addGroup(self, name):
    if not name or name in self.groups:
      return
    item=self.Append(None, name, None)
    self.groups[name] = item
    return item
    
  def RegisterServer(self, settings, initial=False):
    modulename=settings['class']
    if modulename not in adm.modules:
      logger.debug("Module %s not supported", modulename)
      return
    if initial:
      groupName=settings.get('group')
      self.addGroup(groupName)
      group=self.groups.get(groupName)
    else:
      group=None
      if self.currentItem:
        node=self.GetNode(self.currentItem)
        if node:
          groupName=node.settings.get('group')
        else:
          groupName=self.GetItemText(self.currentItem)
        if groupName:
          settings['group']=groupName
          group=self.groups[groupName]
    moduleinfo=adm.modules[modulename].moduleinfo

    cls=moduleinfo['serverclass']
    node=cls(settings)
    if not initial:
      adm.config.storeServerSettings(node, node.settings)
    self.Append(group, node.name, node)


    
