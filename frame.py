# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.aui
import adm
import logger
from wh import xlt, StringType, GetBitmap, Menu, restoreSize
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


  def SetIcon(self, icon):
    if isinstance(icon, int):
      icon=adm.images.GetBitmap(icon)
    elif isinstance(icon, StringType):
      icon=GetBitmap(icon)
    if isinstance(icon, wx.Bitmap):
      icon=wx.IconFromBitmap(icon)
    if icon:      
      wx.Frame.SetIcon(self, icon)
      return True
    return False


  def OnCall(self, e):
    """
    OnCall(wx.Event)

    calls registered procedures from an event using appropriate arguments
    """
    id=e.GetId()
    if id in self.calls:
      proc=self.calls[id]

      args = self.GetCallArgs(proc)
      if len(args) and args[0] == "self":
        del args[0]
      ci=[proc.__module__]
      if hasattr(proc, "_classname_"):
        ci.append(proc._classname_)
      ci.append(proc.__name__)
      adm.logger.debug("Calling ID %d: %s", id, ".".join(ci))
      if len(args) == 2:
        node=self.currentNode
        if not node and self.tree:
          node=self.tree.GetNode()
        if proc(self, node) and node:
          node.DoRefresh()
      else:
        proc(self)
    

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

    self.toolbar=self.CreateToolBar(wx.TB_FLAT|wx.TB_NODIVIDER)
    self.toolbar.SetToolBitmapSize(wx.Size(32, 32));

    self.toolbar.DoAddTool(self.BindMenuId(self.OnShowServers), xlt("Show registered servers"), GetBitmap("connect"))
    self.toolbar.DoAddTool(self.BindMenuId(self.OnDetach), xlt("Detach view"), GetBitmap("detach"))
    self.toolbar.DoAddTool(self.BindMenuId(self.OnRefresh), xlt("Refresh"), GetBitmap("refresh"))
    self.toolbar.AddSeparator()
    self.toolbar.DoAddTool(self.BindMenuId(self.OnEdit), xlt("Edit"), GetBitmap("edit"))
    self.toolbar.DoAddTool(self.BindMenuId(self.OnNew), xlt("New"), GetBitmap("new"))
    self.toolbar.DoAddTool(self.BindMenuId(self.OnDelete), xlt("Delete"), GetBitmap("delete"))
    self.toolbar.AddSeparator()
    self.standardToolsCount=self.toolbar.GetToolsCount()
    self.toolbar.Realize()


    menubar=wx.MenuBar()

    self.filemenu=menu=Menu()

    self.registermenu=Menu()
    for modulename in adm.modules.keys():
      moduleinfo=adm.modules[modulename].moduleinfo
      registerproc=moduleinfo['serverclass'].Register
      self.registermenu.Append(self.BindMenuId(registerproc), xlt("Register new %s") % moduleinfo['name'])
    self.filemenu.AppendOneMenu(self.registermenu, xlt("Register Server"))

    if wx.Platform != "__WXMAC__":
      menu.AppendSeparator()
    self.AddMenu(menu, xlt("Preferences"), xlt("Preferences"), self.OnPreferences, wx.ID_PREFERENCES, adm.app.SetMacPreferencesMenuItemId)
    self.AddMenu(menu, xlt("Quit"), xlt("Quit Admin4"), self.OnQuit, wx.ID_EXIT, adm.app.SetMacExitMenuItemId)

    menubar.Append(menu, xlt("&File"))

    self.viewmenu=menu=Menu()
    self.AddMenu(menu, xlt("Show Servers"), xlt("Show registered servers to connect"), self.OnShowServers)
    self.AddCheckMenu(menu, xlt("Tree"), xlt("Show or hide tree"), self.OnToggleTree, adm.config.Read("TreeShown", True))
    self.AddCheckMenu(menu, xlt("Toolbar"), xlt("Show or hide tool bar"), self.OnToggleToolBar, adm.config.Read("ToolbarShown", True))
    self.AddCheckMenu(menu, xlt("Statusbar"), xlt("Show or hide status bar"), self.OnToggleStatusBar, adm.config.Read("StatusbarShown", True))
    menubar.Append(menu, xlt("&View"))

    _helpid=self.BindMenuId(self.OnHelp)

    self.helpmenu=menu=Menu()

    self.AddMenu(menu, xlt("Help"), xlt("Show help"), self.OnHelp, wx.ID_HELP)
    self.AddMenu(menu, xlt("Logging"), xlt("Show logged problems"), self.OnLogging)
    self.AddMenu(menu, xlt("Update"), xlt("Update program modules"), self.OnUpdate)
    self.AddMenu(menu, xlt("About"), xlt("About %s") % adm.appTitle, self.OnAbout, wx.ID_ABOUT, adm.app.SetMacAboutMenuItemId)

    menubar.Append(menu, xlt("&Help"))


    self.SetMenuBar(menubar)

    self.CreateStatusBar()

    self.details = Notebook(self)
    self.manager.AddPane(self.details, wx.aui.AuiPaneInfo().Center().CloseButton(False) \
                          .Name("objectDetails").Caption(xlt("Object details")))

    self.tree=NodeTreeCtrl(self, name)
    self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelChange)
    self.manager.AddPane(self.tree, wx.aui.AuiPaneInfo().Left().Layer(1).Floatable() \
                          .Name("objectBrowser").Caption(xlt("Object browser")) \
                          .MinSize((200,300)).BestSize((250,350)))
    
    self.servers=ServerTreeCtrl(self)
    self.manager.AddPane(self.servers, wx.aui.AuiPaneInfo().Bottom().Layer(1).Float() \
                          .Name("servers").Caption(xlt("Registered Servers")) \
                          .MinSize((70,70)).BestSize((100,80)))

    str=adm.config.GetPerspective(self)
    if str:
      self.manager.LoadPerspective(str)

    self.OnToggleTree(None)
    self.OnToggleToolBar(None)
    self.OnToggleStatusBar(None)
    self.manager.Update()
    self.manager.Bind(wx.aui.EVT_AUI_PANE_CLOSE, self.OnAuiCloseEvent)
    self.BindMenuId(self.AutoConnect)

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
      self.viewmenu.Check(self.GetMenuId(self.OnToggleTree), False)
  
  def OnQuit(self, evt):
    self.tree.Unbind(wx.EVT_TREE_SEL_CHANGED, self.GetMenuId(self.OnTreeSelChange)) # this is for Win C++ dtor
    self.Close()

  def OnToggleTree(self, evt):
    show=self.viewmenu.IsChecked(self.GetMenuId(self.OnToggleTree))
    self.manager.GetPane("objectBrowser").Show(show)
    if evt:
      self.manager.Update()
      adm.config.Write("TreeShown", show)
  
  def OnToggleToolBar(self, evt):
    show=self.viewmenu.IsChecked(self.GetMenuId(self.OnToggleToolBar))
    self.GetToolBar().Show(show)
    if evt:
      self.manager.Update()
      adm.config.Write("ToolbarShown", show)
  
  def OnToggleStatusBar(self, evt):
    show=self.viewmenu.IsChecked(self.GetMenuId(self.OnToggleStatusBar))
    self.GetStatusBar().Show(show)
    if evt:
      self.manager.Update()
      adm.config.Write("StatusbarShown", show)

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
      
      
  def OnTreeSelChange(self, ev):
    if ev.GetItem() != self.tree.GetSelection():
      self.tree.SelectItem(ev.GetItem())
      self.tree.EnsureVisible(ev.GetItem())
      return
    node=self.tree.GetNode(ev.GetItem())
    self.details.Set(node)
    self.manager.Update()

    if not self.lastNode or not node or self.lastNode.moduleClass() != node.moduleClass():
      for _i in range(self.standardToolsCount, self.toolbar.GetToolsCount()):
        self.toolbar.DeleteToolByPos(self.standardToolsCount)
      if node:
          for mi in node.moduleinfo()['tools']:
            cls=mi['class']
            self.toolbar.DoAddTool(self.BindMenuId(cls.OnExecute), cls.name, GetBitmap(cls.toolbitmap, cls))
      self.toolbar.Realize()
    self.lastNode=node
    
    if node:
      self.toolbar.EnableTool(self.GetMenuId(self.OnEdit), hasattr(node, "Edit"))
      self.toolbar.EnableTool(self.GetMenuId(self.OnDelete), hasattr(node, "Delete"))
      self.toolbar.EnableTool(self.GetMenuId(self.OnNew), self.getNewClass(node) != None)
      for mi in node.moduleinfo()['tools']:
        en=self.menuAvailableOnNode(mi, node)
        if en:
          cls=mi['class']
          if hasattr(cls, 'CheckEnabled'):
            en=cls.CheckEnabled(node)
        self.toolbar.EnableTool(self.GetMenuId(cls.OnExecute), en)

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
    contextMenu=Menu()

    if not len(node.properties):
      node.GetProperties()
    newcls=self.getNewClass(node)
    newmenu=Menu()

    if newcls:
      newid=self.BindMenuId(newcls.New)
      newmenu.Append(newid, xlt("New %s") % newcls.shortname, xlt("Create new %s") % newcls.typename)

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
        id=self.BindMenuId(cls.New)
        newmenu.Append(id, xlt("New %s") % cls.shortname, xlt("Create new %s") % cls.typename)

    contextMenu.AppendOneMenu(newmenu, xlt("New Object"), xlt("Creates a new object"))

    if hasattr(node, "Delete"):
      contextMenu.Append(self.GetMenuId(self.OnDelete), xlt("Delete %s") % node.shortname, xlt("Delete %s %s") % (node.typename,node.name))

    if hasattr(node, "Disconnect"):
      contextMenu.Append(self.BindMenuId(self.OnDisconnect), xlt("Disconnect %s") % node.name, xlt("Disconnect %s \"%s\"") % (node.typename,node.name))

    if contextMenu.GetMenuItemCount():
      contextMenu.AppendSeparator()
    contextMenu.Append(self.GetMenuId(self.OnRefresh), xlt("Refresh"), xlt("Refresh %s") % node.typename)
    contextMenu.Append(self.GetMenuId(self.OnDetach), xlt("Detach view"), xlt("Show %s in detached window") % node.typename)

    needSeparator=True

    for mi in node.menuinfos():
      if self.menuAvailableOnNode(mi, node):
        if needSeparator:
          contextMenu.AppendSeparator()
        needSeparator=False
        cls=mi['class']
        id=self.BindMenuId(cls.OnExecute)
        _item=contextMenu.Append(id, cls.name, cls.help)
        if hasattr(cls, "CheckEnabled") and not cls.CheckEnabled(node):
          contextMenu.Enable(id, False)

    if hasattr(node, "Edit"):
      contextMenu.AppendSeparator()
      id=self.BindMenuId(node.Edit)
      contextMenu.Append(id, xlt("Properties"), xlt("Edit properties of %s") % node.typename)

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

  
