# The Admin4 Project
# (c) 2013-2023 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
import inspect
import wx.xrc as xrc
from wh import xlt, StringType, floatToTime, localTimeMillis
from Validator import Validator
import wx, os
import xmlres
from functools import reduce

class MenuOwner(wx.Object):
  """
  MenuOwner

  has menus
  """
  _menuIds={}
  lastid=500
  
  def __init__(self):
    super(MenuOwner, self).__init__()
    
  def GetCallArgs(self, proc):
    fargs=inspect.getfullargspec(proc)
    return fargs.args

  def GetMenuProc(self, nid):
    if not hasattr(self, '_menuProcs'):
      self._menuProcs={}
      return None
    return self._menuProcs.get(nid)
  
  
  def GetMenuId(self, proc, registerNew=False):
    nid=None
    foundId=self._menuIds.get(proc)
    if not registerNew:
      nid=foundId
    if not nid:
      MenuOwner.lastid += 1
      nid=MenuOwner.lastid
      if not foundId:
        self._menuIds[proc] = nid
    return nid

  def BindMenuId(self, proc, registerNew=False):
    mid= self.GetMenuId(proc, registerNew)
    if not self.GetMenuProc(mid):
      self._menuProcs[mid] = proc
      wx.Window.Bind(self, wx.EVT_MENU, self.OnCall, id=mid)
    return mid

  def EnableMenu(self, menu, item, how):
    if how: how=True
    else:   how=False
    if not isinstance(item, int):
      item=self.GetMenuId(item)
    tb=self.GetToolBar()
    if menu:
      menu.Enable(item, how)
    if tb:
      tb.EnableTool(item, how)
  
  def AddMenuItem(self, menu, onproc, name, desc=None,mid=-1):
    if mid==-1: mid=self.GetMenuId(onproc)
    if desc == None: desc=name
    item=menu.Append(mid, name, desc)
    self.Bind(wx.EVT_MENU, onproc, item)
    return item

  def AddMenuCheckItem(self, menu, onproc, name, desc=None, mid=-1):
    if mid==-1: mid=self.GetMenuId(onproc)
    if desc == None: desc=name
    item=menu.AppendCheckItem(mid, name, desc)
    self.Bind(wx.EVT_MENU, onproc, item)
    return item



class ControlContainer(wx.Object):
  def SetAttr(self, name, value):
    object.__setattr__(self, name, value)
    
  def __init__(self, resname=None):
    super(ControlContainer, self).__init__()

    self.SetAttr("_ctls", {})
    self.module=adm.getModule(self)
    self._ctlList=[]

    self.setResname(resname)

  def AddExtraControls(self, res):
    """
    AddExtraControls(xmlResource)
    """

  def BindAll(self, excludeCtlNames=[]):
    """
    BindAllExcept(self, ctlNames=[]):
    
    Bind standard event all Controls that are not listed
    """
    if isinstance(excludeCtlNames, StringType):
      excludeCtlNames=excludeCtlNames.split()
    excludeCtlNames=map(str.lower, excludeCtlNames)
    
    for name, ctl in self._ctls.items():
      if isinstance(ctl, wx.Button) or isinstance(ctl, wx.StaticText):
        continue
      if name not in excludeCtlNames:
        self.Bind(ctl)

  def Bind(self, ctlName, evt=None, proc=None):
    """
    Bind(controlnameList, eventID=None, eventProc=None)
    Bind(controlname, eventID=None, eventProc=None)
    Bind(control, eventID=None, eventProc=None)
    Bind(eventID, eventProc=None)

    Binds event procedure to control
    if no proc given, adm.Dialog.OnCheck is used
    if no eventID is given, the appropriate event for the control is used
    """
    if isinstance(ctlName, StringType):
      names=ctlName.split()
      if len(names) > 1:
        ctlName=names
      else:
        return self._bind(ctlName, evt, proc)
    if isinstance(ctlName, list):
      for n in ctlName:
        self._bind(n, evt, proc)
    else:
      self._bind(ctlName, evt, proc)


  def _bind(self, ctlName, evt=None, proc=None):
    if isinstance(ctlName, wx.PyEventBinder): # binding to self
      ctl=super(wx.Window, self)
      proc=evt
      evt=ctlName
    elif isinstance(ctlName, wx.Window):
      ctl=ctlName
    else:
      ctl=self[ctlName]

    if not proc:
      if not isinstance(evt, wx.PyEventBinder):
        proc=evt
        evt=None
      if not proc:
        proc=self.OnCheck

    if not evt:
      if isinstance(ctl, wx.Button):
        evt=wx.EVT_BUTTON
      elif isinstance(ctl, wx.CheckBox):
        evt=wx.EVT_CHECKBOX
      elif isinstance(ctl, wx.CheckListBox):
        evt=wx.EVT_CHECKLISTBOX
      elif isinstance(ctl, wx.RadioButton):
        evt=wx.EVT_RADIOBUTTON
      else:
        evt=wx.EVT_TEXT
        if isinstance(ctl, wx.ComboBox):
          ctl.Bind(wx.EVT_COMBOBOX, proc)
    ctl.Bind(evt, proc)

  def GetNode(self):
    if hasattr(self, "node"):
      if self.node:
        return self.node
    if hasattr(self, "parentNode"):
      return self.parentNode
    return None

  def GetDialog(self):
    if hasattr(self, "dialog"):
      return self.dialog
    return None

  def GetServer(self):
    node=self.GetNode()
    if node:
      return node.GetServer()
    dlg=self.GetDialog()
    if dlg:
      return dlg.GetServer()
    return None

  def GetConnection(self):
    node=self.GetNode()
    if node:
      return node.GetConnection()
    dlg=self.GetDialog()
    if dlg:
      return dlg.GetConnection()
    return None


  def setResname(self, resname=None):
    if resname == None:
      self.resname=self.__class__.__name__
      if self.resname == "Dlg":
        self.resname=self.__module__[self.__module__.rfind('.')+1:]
    else:
      self.resname=resname
    
  def getResource(self):
    if self.resname.startswith('.'):
      path=os.path.join(adm.loaddir, "%s.xrc" % self.resname)
      self.resname = os.path.basename(self.resname)
    elif self.resname.startswith('/'):
      path="%s.xrc" % self.resname
      self.resname = os.path.basename(self.resname)
    else:
      module=self.module.replace(".", "/")
      path = os.path.join(adm.loaddir, module, "%s.xrc" % self.resname)
    if not os.path.exists(path):
      raise Exception("Loading XRC from %s failed" % path)
    res=xrc.XmlResource(path)
    res.AddHandler(xmlres.XmlResourceHandler())
    return res

  def _addControl(self, n, res):
    
    ctl=xrc.XRCCTRL(self, n)

    if ctl:
      ctl.validator=None
      vi=n.find('-')
      if vi > 0:
        vp=n[vi+1:].split()
        validatorClass=Validator.Get(vp[0])
        if validatorClass:
          ctl.validator=validatorClass(ctl, vp[1:])
        else:
          adm.logger.debug("No validator for %s installed.", vp[0])
        name=n[:vi]
      else:
        name=n

      names=name.split(':')
      ctl.name=names[-1]
      ctl.flags=list(map(lambda x: x.lower(), names[:-1]))

      self._ctlList.append(ctl.name)
      for flag in ctl.flags:
        if flag.startswith("label="):
          labelCtl=self.ctl(flag[6:])
          if labelCtl:
            ctl.labelCtl=labelCtl


      if self._ctls.get(name):
        adm.logger.debug("Duplicate Control Name %s", ctl.name)
      self._ctls[ctl.name.lower()] = ctl
    else:
      if n == "StatusBar":
        self.addStatusBar(res)

  def _addControls(self, res, xmlnode):
    if not xmlnode:
      return
    if xmlnode.GetName() == "object":
      name=xmlnode.GetAttribute("name", "")
      if name:
        self._addControl(name, res)
    self._addControls(res, xmlnode.GetChildren())
    self._addControls(res, xmlnode.GetNext())

  def addControls(self, res):
    self._addControls(res, res.GetResourceNode(self.resname).GetChildren())


  def ctl(self, name):
    if name == "_ctls":
      return self._ctls
    elif name.startswith("__"):
      return None
    ctls=self._ctls
    return ctls.get(name.lower())


  def EnableControls(self, ctlList, how=True):
    """
    EnableControls(ctlList, how=True)
    
    Enables or disables the controls listed (list of names)
    """
    if how: how=True
    else:   how=False
    if isinstance(ctlList, StringType):
      ctlList=ctlList.split()
    for cn in ctlList:
      c=self.ctl(cn)
      if c:
        c.Enable(how)
        if hasattr(c, "labelCtl"):
          c.labelCtl.Enable(how)
      else:
        adm.logger.debug("Control %s not found", cn)


  def ShowControls(self, ctlList, how=True):
    """
    ShowControls(ctlList, how=True)
    
    Show or hide the controls listed (list of names)
    """
    if how: how=True
    else:   how=False
    if isinstance(ctlList, StringType):
      ctlList=ctlList.split()
    for cn in ctlList:
      c=self.ctl(cn)
      if c:
        c.Show(how)
        if hasattr(c, "labelCtl"):
          c.labelCtl.Show(how)
      else:
        adm.logger.debug("Control %s not found", cn)
        
  def _getValueProc(self, ctl):
    if hasattr(ctl, "GetCheckedItems"):
      return  ctl.GetCheckedItems
    elif hasattr(ctl, "GetValue"):
      return ctl.GetValue
    return None
      
  def SetUnchanged(self):
    """
    SetUnchanged()

    marks all controls as unchanged
    """
    for _key, ctl in self._ctls.items():
      getVal=self._getValueProc(ctl)
      if getVal:
        ctl.unchangedValue=getVal()

  
  def HasChanged(self, name):
    names=name.split()
    if len(names) > 1:
      return reduce(lambda x,y: x or y, map(self.HasChanged, names))

    ctl=self[name]
    if not ctl:
      raise AttributeError("No control named '%s'" % name)
    if not hasattr(ctl, "unchangedValue"):
      raise AttributeError("control '%s' has no unchangedValue" % name)

    getVal=self._getValueProc(ctl)
    return ctl.unchangedValue != getVal()


  def GetChanged(self):
    """
    GetChanged()

    returns list of control names that have changed
    """
    cl=[]
    for key, ctl in self._ctls.items():
      
      if hasattr(ctl, "unchangedValue"):
        getVal=self._getValueProc(ctl)
        if ctl.unchangedValue != getVal():
          cl.append(key)
    return cl

  def IsFilled(self, name):
    ctl=self[name]
    if not ctl:
      raise AttributeError("No control named '%s'" % name)
    return ctl.GetValue()


  def _isvalid(self, name):
    if isinstance(name, wx.Window):
      ctl=name
    else:
      ctl=self.ctl(name)
    if ctl:
      if ctl.validator and hasattr(ctl.validator, "IsValid"):
        return ctl.validator.IsValid()
      return True
    return False

  def _getattr(self, name):
    if isinstance(name, wx.Window):
      ctl=name
    else:
      ctl=self.ctl(name)
    if ctl:
      if ctl.validator:
        return ctl.validator.GetValue()
      elif isinstance(ctl, xmlres.getControlClass("whComboBox")):
        return ctl.GetKeySelection()
      elif isinstance(ctl, wx.StaticText):
        return ctl.GetLabel()
      elif isinstance(ctl, wx.RadioBox):
        return ctl.GetSelection()
      else:
        return ctl.GetValue()
    else:
      try:
        return object.__getattr__(self, name)
      except AttributeError as _e:
        if not name.startswith('_'):
          raise AttributeError("%s has no attribute '%s'" % (str(self.__class__), name))
    return None

  def _setattr(self, name, value):
    if isinstance(name, wx.Window):
      ctl=name
    else:
      ctl=self.ctl(name)
    if ctl:
      if ctl.validator:
        return ctl.validator.SetValue(value)
      elif isinstance(ctl, xmlres.getControlClass("whComboBox")):
        if value == None:
          pass
        else:
          ctl.SetKeySelection(value)
      elif isinstance(ctl, wx.ComboBox):
        if value == None:
          ctl.SetSelection(wx.NOT_FOUND)
        else:
          ctl.SetStringSelection(value)
          if ctl.GetValue() != value:
            ctl.SetValue(value)
      elif isinstance(ctl, wx.StaticText):
        if value == None:
          ctl.SetLabel("")
        else:
          ctl.SetLabel(str(value))
      elif isinstance(ctl, wx.RadioBox):
        if value != None:
          ctl.SetSelection(value)
      else:
        if value == None:
          return ctl.SetValue("")
        return ctl.SetValue(value)
    else:
      try:
        return object.__setattr__(self, name, value)
      except AttributeError as _e:
        if not name.startswith('_'):
          raise AttributeError("%s has no attribute '%s'" % (str(self.__class__), name))
    return None

  def __getitem__(self, name):
    ctl=self.ctl(name)
    if not ctl:
      raise AttributeError("%s has no attribute '%s'" % (str(self.__class__), name))
    return ctl


class Dialog(wx.Dialog, ControlContainer, MenuOwner):
  """
  class Dialog

  Handles XRC-Resource:
    loads them from file according to class name or argument 'resname'
    self.VARNAME=<value> sets control
    var=self.VARNAME reads control
    self["VARNAME"].someMethod() calls control
    VARNAME is case insensitive
    
  Handles Save/Check/OnCheck
    Usually CheckedDialog is used, which includes a status bar as well.
  """
  def __init__(self, parentWin, node=None, resname=None):
    super(Dialog, self).__init__(resname)

    self.statusbar=None
    self.node=node
    if node:
      self.parentNode=node.parentNode
    else:
      self.parentNode=None

    res=self.getResource()
    # TODO configurable from module

#    pre=wx.PreDialog()
#    res.LoadOnDialog(pre, parentWin, self.resname)
#    self.PostCreate(pre)
    res.LoadDialog(self, parentWin, self.resname)

    size, pos=adm.config.getWindowPositions(self)
    if pos:
      self.Move(pos)
    if size and self.HasFlag(wx.RESIZE_BORDER):
      self.SetSize(size)

    self.addControls(res)
    self.AddExtraControls(res)

    if self.module:
      modname="%s/%s" % (self.module.replace('.', '/'), self.resname)
    else:
      modname=self.resname
    adm.logger.debug("Controls found in %s: %s", modname, ", ".join(self._ctls.keys()))

    nb= self.ctl('Notebook')
    if nb:
      sel=nb.GetSelection()
      if sel >= 0:
        nb.GetPage(nb.GetSelection()).Show()

    self.Bind(wx.EVT_CLOSE, self.OnCancel)
    if self.ctl('Cancel'):
      self.Bind('Cancel', wx.EVT_BUTTON, self.OnCancel)
    if self.ctl('OK'):
      self.Bind('OK', wx.EVT_BUTTON, self.OnOK)
      self['OK'].SetDefault()


  def addStatusBar(self, res=None):
    if self.statusbar:
      return
    flags=0;
    if self.HasFlag(wx.RESIZE_BORDER):
      flags = wx.STB_SIZEGRIP
    self.statusbar = wx.StatusBar(self, -1, flags)
    if res:
      res.AttachUnknownControl("StatusBar", self.statusbar)
    else:
      sbHeight=self.statusbar.GetSize().y
      dlgSize=self.GetSize()
      self.SetSize( (dlgSize.x, dlgSize.y+sbHeight) )
      clientSize=self.GetClientSize()
      self.statusbar.SetSize(0, clientSize.y-sbHeight, clientSize.x, sbHeight)
    self.statusbar.Show()

  def moduleClass(self):
    m=self.__module__
    cls=m[:m.find('.')]
    return cls

  def GetImageId(self, name):
    return adm.images.GetId(os.path.join(self.module, name))

  def GetBitmap(self, name):
    bid=self.GetImageId(name)
    if bid > 0:
      return adm.images.GetBitmap(bid)
    return None

  def BindMenuId(self, proc):
    mid=self.GetMenuId(proc)
    wx.Window.Bind(self, wx.EVT_MENU, proc, id=mid)
    return mid

  def Check(self):
    """
    bool Check()

    should be implemented in derived class
    returns true if may save
    """
    return True

  def Save(self):
    """
    bool Save()

    must be implemented in derived class
    returns true if action performed
    Alternatively, Execute() can be implemented which skips the CheckChanged step.
    """
    if hasattr(self, "Execute"):
      return self.Execute()
    return False

#  def Go(self, parentNode=None):
#  must be implemented in derived class


  def Close(self):
    adm.config.storeWindowPositions(self)
    if hasattr(self, "dialogId"):
      try:
        del adm.dialogs[self.dialogId]
      except:
        pass
    self.Destroy()


  def OnCancel(self, _ev):
    if self.IsModal():
      self.EndModal(wx.CANCEL)
    self.Close()


  def DoSave(self):
    try:
      return self.Save()
    except adm.ServerException as e:
      self.SetStatus(xlt("Server error: %s") % e.error)
      return False


  def _OnOK(self):
    if not self.Check():
      return False
    if not self.DoSave():
      try:
        lastError=self.GetServer().GetLastError()
        self.SetStatus(lastError)
      except: pass
      return False

    if self.IsModal():
      self.EndModal(wx.ID_OK)
    if hasattr(self, "startTime"):
      elapsed=localTimeMillis() - self.startTime
      adm.SetStatus(xlt("Ok: %s execution time.") % floatToTime(elapsed/1000.))
    else:
      adm.SetStatus(xlt("Ok."))
    return True

  def OnOK(self, _ev):
    if self._OnOK():
      self.Close()


  def OnCheck(self, _ev=None):
    ok=self.Check()
    if ok:
      self.SetStatus(None)
      if not hasattr(self, "Execute"):
        ok = self.GetChanged()

    self["OK"].Enable(bool(ok))

  def GoModal(self):
    self.Go()
    self.SetUnchanged()
    self.OnCheck(None)
    self.modalResult=self.ShowModal()
    return self.modalResult== wx.ID_OK

  def CheckValid(self, ok, cond, txt):
    if ok:
      if not cond:
        ok=False
        self.SetStatus(txt)
    return ok


  def SetStatus(self, text=None):
    if self.statusbar:
      if text:
        self.statusbar.SetStatusText(text)
      else:
        self.statusbar.SetStatusText("")


  def Bind(self, *args, **kargs):
    ControlContainer.Bind(self, *args, **kargs)

  def __getattr__(self, name):
    return self._getattr(name)

  def __setattr__(self, name, value):
    return self._setattr(name, value)



class CheckedDialog(Dialog):
  """
  CheckedDialog
  
  Dialog with status bar
  """
  
  def __init__(self, parentWin, node=None, _parentNode=None, resName=None):
    Dialog.__init__(self, parentWin, node, resName)
    self.addStatusBar()


class PropertyDialog(CheckedDialog):
  """
  PropertyDialog
  
  Editing properties of a node, which is represented by a treeItem 
  and thus needs a tree refresh if changed
  """
  def __init__(self, parentWin, node, parentNode=None, resName=None, title=None):
    CheckedDialog.__init__(self, parentWin, node, resName=resName)
    if parentNode:
      self.parentNode=parentNode

    self.refreshNode=None

    if title:
      self.SetTitle(title)
    elif self.node:
      self.SetTitle(xlt("Properties of %s \"%s\"") % (self.node.typename, self.node.name))
    elif parentNode:
      self.SetTitle(xlt("New %s") % parentNode.typename)
    self.Bind('OK', wx.EVT_BUTTON, self.OnOK)


  def OnOK(self, _ev):
    if not self._OnOK():
      return

    if self.refreshNode:
      self.refreshNode.DoRefresh()
    elif self.node:
      self.node.Refresh()
    elif self.parentNode:
      self.parentNode.DoRefresh()
    self.Close()


class PagedPropertyDialog(PropertyDialog):
  """
  PagedPropertyDialog
  
  PropertyDialog with a notebook, distributing property items over several panels
  """
  def __init__(self, parentWin, node, parentNode, title=None):
    PropertyDialog.__init__(self, parentWin, node, parentNode, resName="./PagedPropertyDlg", title=title)
    self.panels=[]
    notebook=self['Notebook']
    if hasattr(self, 'panelClasses'):
      for cls in self.panelClasses:
        if hasattr(cls, 'CreatePanel'):
          panel=cls.CreatePanel(self, notebook)
        else:
          panel=cls(self, notebook)
        if panel:
          self.addPanel(panel)
    notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPanelChange)

  def addPanel(self, panel, name=None):
    if not name:
      name=panel.name
    self.panels.append(panel)
    self['Notebook'].AddPage(panel, name)

  def OnPanelChange(self, evt):
    panel=self.panels[evt.Selection]
    panel.Show()
    if hasattr(panel, "Display"):
      panel.Display()
  
  def Check(self):
    for panel in self.panels:
      if hasattr(panel, "Check"):
        if not panel.Check():
          return False
    return True
  
  def GetChanged(self):
    cl=[]
    for panel in self.panels:
      cl.extend(panel.GetChanged())
    return cl
  
  def Go(self):
    for panel in self.panels:
      if hasattr(panel, "Go"):
        panel.Go()


class ServerPropertyDialog(PropertyDialog):
  """
  ServerPropertyDialog
  
  Server Properties with a list of predefined keywords
  which are stored in the config file
  """
  keyvals= [ ("HostName", 'name') ,
             ("HostAddress", 'host'),
             "Port",
             "User",
             "Password",
             "Autoconnect",
             "SSL",
             "Security"
           ]


  def GetSettings(self, keyvals=None):
    if not keyvals:
      keyvals=self.keyvals
    if self.node:
      settings=self.node.settings.copy()
    else:
      settings={}
    for ctlname in keyvals:
      if isinstance(ctlname, tuple):
        ctlname, key = ctlname
      else:
        key=ctlname.lower()

      ctl=self.ctl(ctlname)
      if ctl:
        settings[key] = self._getattr(ctl)
    return settings

  def SetSettings(self, settings, keyvals=None):
    if not keyvals:
      keyvals=self.keyvals
    for ctlname in keyvals:
      if isinstance(ctlname, tuple):
        ctlname, key = ctlname
      else:
        key=ctlname.lower()

      val=settings.get(key)
      if val == None:
        continue

      ctl=self.ctl(ctlname)
      if ctl:
        self._setattr(ctl, val)
