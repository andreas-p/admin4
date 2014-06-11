# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.aui
import adm
import logger
from wh import xlt, StringType, GetIcon, Menu, ToolBar, restoreSize
from tree import NodeTreeCtrl, ServerTreeCtrl
from notebook import Notebook
from LoggingDialog import LoggingDialog
from AdmDialogs import PreferencesDlg, AboutDlg, UpdateDlg

class Frame(wx.Frame, adm.MenuOwner):
  def __init__(self, parentWin, title, style, _size, _pos):
    size,pos = restoreSize("main", (600,400), None)
    wx.Frame.__init__(self, parentWin, title=title, style=style, size=size, pos=pos)
    self.tree=None
    self.currentNode=None
    self.Bind(wx.EVT_CLOSE, self.OnClose)

    size, pos=adm.config.getWindowPositions(self)
    if pos:
      self.Move(pos)
    if size and self.HasFlag(wx.RESIZE_BORDER):
      self.SetSize(size)


  def GetToolBar(self):
    if hasattr(self, 'toolbar'):
      return self.toolbar
    return None
  

  def registerToggles(self, toolbar, statusbar):
    """ have toolbar and/or statusbar toggle in viewmenu """
    
    if toolbar:  
      self.viewmenu.AddCheck(self.OnToggleToolBar, xlt("Toolbar"), xlt("Show or hide tool bar"), adm.config.Read("ToolbarShown", True, self))
    if statusbar:
      self.viewmenu.AddCheck(self.OnToggleStatusBar, xlt("Statusbar"), xlt("Show or hide status bar"), adm.config.Read("StatusbarShown", True, self))
  
  def OnToggleToolBar(self, evt=None):
    show=self.viewmenu.IsChecked(self.OnToggleToolBar)
    self.GetToolBar().Show(show)
    if evt:
      self.manager.Update()
      adm.config.Write("ToolbarShown", show, self)
  
  def OnToggleStatusBar(self, evt=None):
    show=self.viewmenu.IsChecked(self.OnToggleStatusBar)
    self.GetStatusBar().Show(show)
    if evt:
      self.manager.Update()
      adm.config.Write("StatusbarShown", show, self)

  
  def SetIcon(self, icon, mod=None):
    if isinstance(icon, int):
      icon=adm.images.GetBitmap(icon)
    elif isinstance(icon, StringType):
      icon=GetIcon(icon, mod)
    if isinstance(icon, wx.Bitmap):
      icon=wx.IconFromBitmap(icon)
    if icon:      
      wx.Frame.SetIcon(self, icon)
      return True
    return False


  def OnCall(self, evt):
    """
    OnCall(wx.Event)

    calls registered procedures from an event using appropriate arguments
    It handles:
      @staticmethod DoSomething(parentWindow, node) -> bool to refresh node
      @staticmethod DoSomething(node)
      @staticmethod Register(parentWindow)
      Edit(self, parentWindow)
      HandleEvent(self, evt)
    """
    id=evt.GetId()
    proc=self.GetMenuProc(id)
    if proc:
      args = self.GetCallArgs(proc)
      if len(args) and args[0] == "self":
        del args[0]
        isStatic=False
      else:
        isStatic=True
      ci=[proc.__module__]
      if hasattr(proc, "_classname_"):
        ci.append(proc._classname_)
      ci.append(proc.__name__)
      adm.logger.debug("Calling ID %d: %s", id, ".".join(ci))
      node=self.currentNode
      if not node and self.tree:
        node=self.tree.GetNode()
      if len(args) == 2:
        if proc(self, node) and node:
          node.DoRefresh()
      else:
        if isStatic:
          if proc.__name__ in ['Register']:
            proc(self)
          else:
            proc(node)
        else:
          proc(evt)
    

  def OnClose(self, evt):
    adm.config.storeWindowPositions(self)
    evt.Skip()

  def SetStatus(self, text=None):
    sb=self.GetStatusBar()
    if sb:
      if text:
        sb.SetStatusText(text, 0)
      else:
        sb.SetStatusText("", 0)


  def PushStatus(self, text, field=0):
    sb=self.GetStatusBar()
    if sb:
      sb.PushStatusText(text, field)

  def PopStatus(self):
    sb=self.GetStatusBar()
    if sb:
      sb.PopStatusText()


class NodeTreePanel(adm.NotebookPanel):
  def __init__(self, dlg, name):
    self.SetAttr('treeName', name)
    adm.NotebookPanel.__init__(self, dlg, dlg)
    self.Bind('FindClose', self.OnCloseFind)
    self.Bind('Find', self.OnFind)
    self.Bind('FindNext', self.OnFindNext)
    
  def AddExtraControls(self, res):
    self.tree=NodeTreeCtrl(self, self.treeName)
    res.AttachUnknownControl("ValueGrid", self.tree)
    
  def DoShow(self, how):
    self.ShowControls("Find FindNext FindClose", how)
    self.dialog.manager.Update()

  def OnFind(self, evt):
    node= self.tree.GetNode()
    if node and node.GetServer().findObjectIncremental:
      s,e=self['Find'].GetSelection()
      self.OnFindNext(None)
      self['Find'].SetFocus()
      self['Find'].SetSelection(s,e)
    else:
      self['Find'].SetForegroundColour(wx.BLUE)
  
  def OnFindNext(self, evt):
    self['Find'].SetForegroundColour(wx.BLACK)
    find=self.Find.lower().strip()
    if not find:
      return
    node=self.tree.GetNode()
    if node:
      server=node.GetServer()
      if evt: startItem=self.tree.GetSelection()
      else:   startItem=server.treeitems[self.tree.name][0]
        
      item=server.FindObject(self.tree, startItem, find)
      if item:
        self.tree.SelectItem(item)
      else:
        self['Find'].SetForegroundColour(wx.RED)

  def OnCloseFind(self, evt):
    self.DoShow(False)

class DetailFrame(Frame):
  def __init__(self, parentWin, name, args=None, title=None):
    if not title:
      title=name
    style=wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX
    adm.Frame.__init__(self, parentWin, title, style, (600,400), None)
    self.SetIcon(name)
    self.name=name
    self.lastNode=None
    self.appArgs=args

    self.manager=wx.aui.AuiManager(self)
    self.manager.SetFlags(wx.aui.AUI_MGR_ALLOW_FLOATING|wx.aui.AUI_MGR_TRANSPARENT_HINT | \
         wx.aui.AUI_MGR_HINT_FADE| wx.aui.AUI_MGR_TRANSPARENT_DRAG)

    self.toolbar=ToolBar(self, 32);

    self.toolbar.Add(self.OnShowServers, xlt("Show registered servers"), "connect")
    self.toolbar.Add(self.OnDetach, xlt("Detach view"), "detach")
    self.toolbar.Add(self.OnRefresh, xlt("Refresh"), "refresh")
    self.toolbar.AddSeparator()
    self.toolbar.Add(self.OnEdit, xlt("Edit"), "edit")
    self.toolbar.Add(self.OnNew, xlt("New"), "new")
    self.toolbar.Add(self.OnDelete, xlt("Delete"), "delete")
    self.toolbar.Add(self.OnFindObject, xlt("Find"), "edit_find")
    self.toolbar.AddSeparator()
    self.standardToolsCount=self.toolbar.GetToolsCount()
    self.toolbar.Realize()


    menubar=wx.MenuBar()

    self.filemenu=menu=Menu(self)

    self.registermenu=Menu(self)
    for modulename in adm.modules.keys():
      moduleinfo=adm.modules[modulename].moduleinfo
      registerproc=moduleinfo['serverclass'].Register
      self.registermenu.Add(registerproc, xlt("Register new %s") % moduleinfo['name'])
    self.filemenu.AppendOneMenu(self.registermenu, xlt("Register Server"))

    if wx.Platform != "__WXMAC__":
      menu.AppendSeparator()
    menu.Add(self.OnPreferences, xlt("Preferences"), xlt("Preferences"), wx.ID_PREFERENCES, adm.app.SetMacPreferencesMenuItemId)
    menu.Add(self.OnQuit, xlt("Quit"), xlt("Quit Admin4"), wx.ID_EXIT, adm.app.SetMacExitMenuItemId)

    menubar.Append(menu, xlt("&File"))

    self.viewmenu=menu=Menu(self)
    menu.Add(self.OnShowServers, xlt("Show Servers"), xlt("Show registered servers to connect"))
    menu.AddCheck(self.OnToggleTree, xlt("Tree"), xlt("Show or hide tree"), adm.config.Read("TreeShown", True, self))
    self.registerToggles(True, True)
    menubar.Append(menu, xlt("&View"))

    self.editmenu=menu=Menu(self)
    menu.Add(self.OnEdit, xlt("Edit"), xlt("edit"))
    menu.Add(self.OnNew, xlt("New"), xlt("new object"))
    menu.Add(self.OnDelete, xlt("Delete"), xlt("delete object"))
    menu.Add(self.OnFindObject, xlt("Find"), xlt("find object"))
    menubar.Append(menu, xlt("&Edit"))
    
    
    self.helpmenu=menu=Menu(self)
    menu.Add(self.OnHelp, xlt("Help"), xlt("Show help"), wx.ID_HELP)
    menu.Add(self.OnLogging, xlt("Logging"), xlt("Show logged problems"))
    menu.Add(self.OnUpdate, xlt("Update"), xlt("Update program modules"))
    menu.Add(self.OnAbout, xlt("About"), xlt("About %s") % adm.appTitle, wx.ID_ABOUT, adm.app.SetMacAboutMenuItemId)

    menubar.Append(menu, xlt("&Help"))


    self.SetMenuBar(menubar)

    self.CreateStatusBar()

    self.details = Notebook(self)
    self.manager.AddPane(self.details, wx.aui.AuiPaneInfo().Center().CloseButton(False) \
                          .Name("objectDetails").Caption(xlt("Object details")))

    self.nodePanel=NodeTreePanel(self, name)
    self.tree=self.nodePanel.tree
    self.nodePanel.DoShow(False)
    self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelChange)
    self.manager.AddPane(self.nodePanel, wx.aui.AuiPaneInfo().Left().Layer(1).Floatable() \
                          .Name("objectBrowser").Caption(xlt("Object browser")) \
                          .MinSize((200,300)).BestSize((250,350)))
    
    self.servers=ServerTreeCtrl(self)
    self.manager.AddPane(self.servers, wx.aui.AuiPaneInfo().Bottom().Layer(1).Float() \
                          .Name("servers").Caption(xlt("Registered Servers")) \
                          .MinSize((70,70)).BestSize((100,80)))

    str=adm.config.GetPerspective(self)
    if str:
      self.manager.LoadPerspective(str)

    self.OnToggleTree()
    self.OnToggleToolBar()
    self.OnToggleStatusBar()
    self.manager.Update()
    self.manager.Bind(wx.aui.EVT_AUI_PANE_CLOSE, self.OnAuiCloseEvent)

    self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
    self.activated=False
    
  def OnFindObject(self, evt):
    self.nodePanel.DoShow(True)
    self.nodePanel['Find'].SetFocus()
    
  def OnActivate(self, evt):
    if not self.activated:
      self.activated=True
      if not wx.GetKeyState(wx.WXK_SHIFT):
        self.AutoConnect(evt)
    evt.Skip()
    
  def AutoConnect(self, evt):
    haveOne=False
    if self.appArgs:
      for server in self.servers.nodes:
        if "%s/%s" % (server.module, server.name) in self.appArgs:
          rc=self.servers.ConnectServer(server, self.tree.name)
          haveOne = haveOne or rc
    else:
      for server in self.servers.nodes:
        if server.settings.get("autoconnect"):
          #try:
            rc=self.servers.ConnectServer(server, self.tree.name)
            haveOne = haveOne or rc
#          except StringException:
#            pass
    if not haveOne:
      self.OnShowServers(None)
    self.servers.ExpandFirst()

   
  def OnAuiCloseEvent(self, evt):
    if evt.GetPane().name == "objectBrowser":
      self.viewmenu.Check(self.OnToggleTree, False)
  
  def OnQuit(self, evt):
    self.tree.Unbind(wx.EVT_TREE_SEL_CHANGED, self.GetMenuId(self.OnTreeSelChange)) # this is for Win C++ dtor
    self.Close()

  def OnToggleTree(self, evt=None):
    show=self.viewmenu.IsChecked(self.OnToggleTree)
    self.manager.GetPane("objectBrowser").Show(show)
    if evt:
      self.manager.Update()
      adm.config.Write("TreeShown", show, self)
  
  def OnLogging(self, evt):
    dlg=LoggingDialog(self)
    dlg.Go()
    dlg.Show()

  def OnUpdate(self, evt):
    dlg=UpdateDlg(self)
    dlg.Go()
    dlg.ShowModal()
    
  def GetNode(self):
    if self.currentNode:
      return self.currentNode
    else:
      return self.tree.GetNode()

  def OnHelp(self, ev):
    pass

  def OnPreferences(self, evt):
    dlg=PreferencesDlg(self)
    dlg.Go()
    dlg.Show()


  def OnAbout(self, evt):
    about=AboutDlg(self)
    about.ShowModal()
    
    
  def OnShowServers(self, evt):
    self.manager.GetPane("servers").Show(True)
    self.manager.Update()


  def OnDetach(self, evt):
    node=self.GetNode()
    if node:
      if not node.detachedWindow:
        node.detachedWindow = DetachFrame(self, node)
      node.detachedWindow.Show()
      node.detachedWindow.Raise()
        
  def OnRefresh(self, evt):
    node=self.GetNode()
    if node:
      node.Refresh()
      node.PopulateChildren()
      info=node.GetInfo()
      self.SetStatus(info)

  def OnNew(self, evt):
    node=self.GetNode()
    if node:
      newcls=self.getNewClass(node)
      if newcls:
        newcls.New(self, node.parentNode)

  def OnEdit(self, evt):
    node=self.GetNode()
    if node and hasattr(node, "Edit"):
      node.Edit(self)

  def OnDelete(self, evt):
    node=self.tree.GetNode()
    if node and hasattr(node, "Delete"):
      if not adm.ConfirmDelete(xlt("Delete \"%s\"?") % node.name, xlt("Deleting %s") % node.typename):
        return

      if node.Delete():
        node.RemoveFromTree()
      self.SetStatus(xlt("%s \"%s\" deleted.") % (node.typename, node.name))

  def OnDisconnect(self, evt):
    node=self.tree.GetNode()
    if node and hasattr(node, "Disconnect"):
      node.Disconnect()
      node.RemoveFromTree()
      self.SetStatus(xlt("%s \"%s\" disconnected.") % (node.typename, node.name))
      
  def GetNodePath(self, item):
    node=self.tree.GetNode(item)
    if not node:
      return None
    parentItem=self.tree.GetItemParent(item)
    if parentItem:
      pp=self.GetNodePath(parentItem)
      if pp:
        return "%s/%s" % (pp, node.id.path())
      return node.id.path()
    
          
  def OnTreeSelChange(self, evt):
    item=evt.GetItem()
    if item != self.tree.GetSelection():
      self.tree.SelectItem(item)
      self.tree.EnsureVisible(item)
      return
    node=self.tree.GetNode(item)
    self.details.Set(node)
    if node and hasattr(node, "GetHint"):
      hint=node.GetHint()
      if hint:
        if not hasattr(node, 'hintShown'):
          node.hintShown=True
          if isinstance(hint, tuple):
            title=hint[1]
            args=hint[2]
            hint=hint[0]
          else:
            title=None
            args=None
          adm.ShowHint(self, hint, node, title, args)

    self.manager.Update()

      
    if not self.lastNode or not node or self.lastNode.moduleClass() != node.moduleClass():
      for _i in range(self.standardToolsCount, self.toolbar.GetToolsCount()):
        self.toolbar.DeleteToolByPos(self.standardToolsCount)
      if node:
          for mi in node.moduleinfo()['tools']:
            cls=mi['class']
            self.toolbar.Add(cls)
      self.toolbar.Realize()
    self.lastNode=node
    
    if node:
      self.EnableMenu(self.editmenu, self.OnEdit, hasattr(node, "Edit"))
      self.EnableMenu(self.editmenu, self.OnDelete, hasattr(node, "Delete"))
      self.EnableMenu(self.editmenu, self.OnNew, self.getNewClass(node) != None)
      for mi in node.moduleinfo()['tools']:
        en=self.menuAvailableOnNode(mi, node)
        cls=mi['class']
        if en:
          if hasattr(cls, 'CheckEnabled'):
            en=cls.CheckEnabled(node)
        self.toolbar.Enable(cls.OnExecute, en)

      server=node.GetServer()
      if server != node: # don't store a server's nodePath, this would overwrite the desired nodePath on disconnect
        nodePath=self.GetNodePath(item)
        if nodePath:
          server.settings['nodePath'] = nodePath
          adm.config.storeServerSettings(server, server.settings)

    if not node:
      self.SetStatus("")
      return
    self.SetStatus(node.GetInfo())


  def getNewClass(self, node):
    if hasattr(node, "New"):
      return node.__class__
    elif isinstance(node, adm.Group) and node.memberclass and hasattr(node.memberclass, "New"):
      return node.memberclass
    elif isinstance(node, adm.Collection) and node.nodeclass and hasattr(node.nodeclass, "New"):
      return node.nodeclass
    return None
    
  def menuAvailableOnNode(self, mi, node):
    cls=mi['class']
    if hasattr(cls, "CheckAvailableOn"):
      return cls.CheckAvailableOn(node)
    nodeclasses=mi.get('nodeclasses')
    if nodeclasses:
      for nc in nodeclasses:
        if isinstance(node, nc):
          return True
    else:
      logger.debug("no nodeclasses for %s", cls.__name__)
    return False


  def GetContextMenu(self, node):
    contextMenu=Menu(self)

    if not len(node.properties):
      node.GetProperties()
    newcls=self.getNewClass(node)
    newmenu=Menu(self)

    if newcls:
      newmenu.Add(newcls.New, xlt("New %s") % newcls.shortname, xlt("Create new %s") % newcls.typename)

    morenew=node.nodeinfo().get('new', [])
    if isinstance(morenew, list):
      morenew=list(morenew) # copy
    else:
      morenew=[morenew]

    children=node.nodeinfo().get('children', [])
    for child in children:
      childnodeinfo=node.nodeinfo(child)
      childclass=childnodeinfo['class']
      if childclass not in morenew:
        morenew.append(childclass)
      childnew=childnodeinfo.get('new', [])
      if not isinstance(childnew, list):
        childnew=[childnew]
      for childclass in childnew:
        if childclass not in morenew:
          morenew.append(childclass)

    for cls in morenew:
      if cls == newcls:
        continue
      if hasattr(cls, "New"):
        newmenu.Add(cls.New, xlt("New %s") % cls.shortname, xlt("Create new %s") % cls.typename)

    contextMenu.AppendOneMenu(newmenu, xlt("New Object"), xlt("Creates a new object"))

    if hasattr(node, "Delete"):
      contextMenu.Add(self.OnDelete, xlt("Delete %s") % node.shortname, xlt("Delete %s %s") % (node.typename,node.name))

    if hasattr(node, "Disconnect"):
      contextMenu.Add(self.OnDisconnect, xlt("Disconnect %s") % node.name, xlt("Disconnect %s \"%s\"") % (node.typename,node.name))

    if contextMenu.GetMenuItemCount():
      contextMenu.AppendSeparator()
    contextMenu.Add(self.OnRefresh, xlt("Refresh"), xlt("Refresh %s") % node.typename)
    contextMenu.Add(self.OnDetach, xlt("Detach view"), xlt("Show %s in detached window") % node.typename)

    needSeparator=True

    for mi in node.menuinfos():
      if self.menuAvailableOnNode(mi, node):
        if needSeparator:
          contextMenu.AppendSeparator()
        needSeparator=False
        cls=mi['class']
        item=contextMenu.Add(cls.OnExecute, cls.name, cls.help)
        if hasattr(cls, "CheckEnabled") and not cls.CheckEnabled(node):
          contextMenu.Enable(item, False)

    if hasattr(node, "Edit"):
      contextMenu.AppendSeparator()
      contextMenu.Add(self.OnEdit, xlt("Properties"), xlt("Edit properties of %s") % node.typename)

    return contextMenu



class DetachFrame(Frame):
  def __init__(self, parentWin, node):
    self.node=node
    title=xlt("%(type)s %(name)s") % {'type': node.typename, 'name': node.name}

    style=wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX
    adm.Frame.__init__(self, parentWin, title, style, (400,300), None)
    self.SetIcon(node.GetIcon())
     
    self.details = Notebook(self)
    self.details.detached=True
    self.details.Set(node)
  
  def OnClose(self, evt):
    if self.node:
      self.node.CleanupDetached()
      self.node.detachedWindow=None
      self.node=None
      Frame.OnClose(self, evt)

  
