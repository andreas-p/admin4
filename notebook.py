# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage



import wx
import adm
import wh
import logger
from wh import Menu


class _TimerOwner:
  def __init__(self):
    self.refreshDisplay=None
    self.timer=None
    
  def SetRefreshTimer(self, proc, timeout=1):
    """
    SetRefreshTimer(self, proc, timeout=1)
    
    Sets the refresh timer to <timeout> seconds
    when elapsed, <proc> is called
    When <timeout> is 0, the timer is stopped
    """
    if proc != self.refreshDisplay or not timeout:
      if self.timer:
        self.timer.Stop()

    self.refreshDisplay=proc
    if proc and timeout:
      self.timer=wh.Timer(self, self.OnTimer)
      self.timer.Start(int(timeout*1000))
    else:
      self.timer=None

  
  def OnTimer(self, _ev=None):
    if self.refreshDisplay:
      self.refreshDisplay()
    else:
      self.timer.Stop()
      self.timer=None


  
class Notebook(wx.Notebook, adm.MenuOwner, _TimerOwner):
  def __init__(self, parentWin, size=wx.DefaultSize):
    wx.Notebook.__init__(self, parentWin, size=size)
    _TimerOwner.__init__(self)
    self.node=None
    self.currentPage=0
    self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChange)
    self.knownPages={}
    self.isDetached=False


  def OnTimer(self, _ev=None):
    if self.refreshDisplay and self.node:
      self.refreshDisplay(self.node, self.GetTopLevelParent() == self.node.detachedWindow)
    else:
      if self.timer:
        self.timer.Stop()
      self.timer=None


  def Freeze(self):
    if not wx.version().startswith("3.0.0.0 osx-cocoa"):
      super(Notebook, self).Freeze()
  
  def Thaw(self):
    if not wx.version().startswith("3.0.0.0 osx-cocoa"):
      super(Notebook, self).Thaw()

  def AppendPage(self, page):
    self.DoInsertPage(page, None)
    
  def PrependPage(self, page):
    self.DoInsertPage(page, self.propPageIndex)
    self.propPageIndex += 1
    
  def DoInsertPage(self, page, pos):
    if not isinstance(page, wx.Window):
      page=page(self)
      
    ctl=page.GetControl()
    if pos == None:
      self.AddPage(ctl, page.name)
      self.pages.append(page)
    else:
      self.InsertPage(pos, ctl, page.name)
      self.pages.insert(pos, page)
    if isinstance(ctl, wx.ListCtrl):
      ctl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemDoubleClick)
      ctl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnItemRightClick)
      ctl.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)
      if wx.Platform == "__WXMSW__":
        ctl.Bind(wx.EVT_RIGHT_UP, self.OnItemRightClick)


  def Set(self, node):
    self.node=node
    self.Freeze()

    self.DeleteAllPages()
    pagecount=self.GetPageCount()
    if not pagecount:
      self.propPageIndex=0
      self.pages=[]
      self.AppendPage(adm.PropertyPage)
    
    for n in range(pagecount-1, -1, -1):
      if n != self.propPageIndex:
        self.RemovePage(n)
        del self.pages[n]
    self.propPageIndex=0

    if hasattr(node, "nodeinfo"):
      dashboardClass=node.nodeinfo().get("dashboard")
      if dashboardClass:
        self.PrependPage(dashboardClass)


    if hasattr(node, "moduleinfo"):
      addPages=node.moduleinfo().get("pages", [])
      if not isinstance(addPages, list):
        addPages=[addPages]
      for pageClass in addPages:
        if node.IsPageAvailable(pageClass, self.isDetached):
          self.AppendPage(pageClass)

      
    if self.currentPage >= self.GetPageCount():
      self.currentPage=0

    self.SetSelection(self.currentPage)
    self.doDisplay()
    self.Thaw()


  def OnPageChange(self, ev):
    self.currentPage=ev.GetSelection()
    self.doDisplay()


  def doDisplay(self):
    if self.currentPage >= len(self.pages):
      return
    page=self.pages[self.currentPage]
    if self.refreshDisplay != page.Display:
      self.SetRefreshTimer(None)

    if self.node:
      page.Display(self.node, self.GetTopLevelParent() == self.node.detachedWindow)
    page.GetControl().Show()


  def OnCall(self, e):
    """
    OnCall(wx.Event)

    calls registered procedures from an event using appropriate arguments
    """
    id=e.GetId()
    if id in self.calls:
      proc=self.calls[id]

      args=self.GetCallArgs(proc)
      if len(args) and args[0] == "self":
        del args[0]
      ci=[proc.__module__]
      if hasattr(proc, "_classname_"):
        ci.append(proc._classname_)
      ci.append(proc.__name__)
      logger.debug("Calling ID %d: %s", id, ".".join(ci))
      if len(args) == 2:
        page=self.pages[self.GetSelection()]
        proc(self, page)
      else:
        proc(self)


  def OnColClick(self, evt):
    if self.node:
      page=self.pages[self.currentPage]
      if page and hasattr(page, "OnColClick"):
        page.OnColClick(evt)
    
  def OnItemRightClick(self, evt):
    if self.node:
      if hasattr(evt, 'GetIndex'):
        index=evt.GetIndex()
      else:
        index=-1
      page=self.pages[self.GetSelection()]
      if not hasattr(evt, 'page'):
        evt.page=page
      if hasattr(page, 'menus'):
        cm=Menu(self)
        menus=page.menus
        for cls in menus:
          if hasattr(cls, "CheckAvailableOn") and not cls.CheckAvailableOn(page):
            continue
          cls.OnExecute._classname_=cls.__name__
          item=cm.Add(cls.OnExecute, cls.name, cls.help)
          if hasattr(cls, "CheckEnabled") and not cls.CheckEnabled(page):
            cm.Enable(item, False)

        if cm.GetMenuItemCount():
          page.GetControl().PopupMenu(cm, evt.GetPosition())
            
      elif hasattr(self.node, "OnItemRightClick"):
        evt.currentPage = page
        self.node.OnItemRightClick(evt)
      elif hasattr(self.node, "GetItemNode"):
        node=self.node.GetItemNode(evt.page, index)
        if node:
          node.RefreshVolatile()
          node.GetProperties()
          w=adm.GetCurrentFrame(self)
          cm=w.GetContextMenu(node)
          w.currentNode=node
          page.GetControl().PopupMenu(cm, evt.GetPosition())
          w.currentNode=None

  
  
  def OnItemDoubleClick(self, evt):
    if self.node:
      page=self.pages[self.currentPage]
      if hasattr(self.node, "OnItemDoubleClick"):
        evt.currentPage = page
        self.node.OnItemDoubleClick(evt)
      elif hasattr(page, "OnItemDoubleClick"):
        page.OnItemDoubleClick(evt)
      elif hasattr(self.node, "GetItemNode"):
        node=self.node.GetItemNode(evt.currentPage, evt.GetIndex())
        if node and hasattr(node, "Edit"):
          node.GetProperties()
          node.Edit(self)

