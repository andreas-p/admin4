# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import xmlres
import wx
import adm
from wh import xlt


class ControlledPage:
  def SetOwner(self, owner): 
    self.owner=owner
    self.lastNode=None
    self.refreshTimeout=3

    if not self.panelName:
      return
    
    self.Bind('Refresh', self.OnRefresh)
    rrc=self['Refreshrate']
    rrc.SetRange(1, 22)
    rr=adm.config.Read("RefreshRate", 3, self, self.panelName)
    # 0 1 2 3 4 5 6
    # 8 10                   *2
    # 15 20 25 30            *5
    # 40 50 60               *10
    # 2m 3m 4m 5m            *60
    # 10m 15m                *300
    if rr == 0:
      rr= rrc.GetMax()
    elif rr > 300:
      rr = 19 + (rr-300)/60
    elif rr > 60:
      rr = 15 + (rr-60)/30
    elif rr > 60:
      rr = 12 + (rr-30)/10
    elif rr > 10:
      rr = 8 - (rr-10)/5
    elif rr > 6:
      rr = 6+ (rr-6)/2

    rrc.SetValue(rr)
    rrc.Bind(wx.EVT_COMMAND_SCROLL, self.OnRefreshRate)
    

  def OnRefresh(self, evt=None):
    self.TriggerTimer()
    
  def OnRefreshRate(self, evt=None):
    rr=self.RefreshRate
    if rr == self['RefreshRate'].GetMax():
      rr=0
      self.RefreshStatic=xlt("stopped")
    else:
      if rr > 19:
        rr = (rr-19)*300 +300
      elif rr > 15:
        rr = (rr-15)*60 + 60
      elif rr > 12:
        rr = (rr-12)*10 + 30
      elif rr > 8:
        rr = (rr-8)*5 +10
      elif rr > 6:
        rr = (rr-6)*2 +6
      
      if rr < 60:
        self.RefreshStatic=xlt("%d sec") % rr
      else:
        self.RefreshStatic=xlt("%d min") % (rr/60)
    if not evt or evt.GetEventType() == wx.wxEVT_SCROLL_THUMBRELEASE:
      adm.config.Write("RefreshRate", rr, self, self.panelName)
      self.refreshTimeout=rr
      self.StartTimer()    
  
  def TriggerTimer(self):
    self.owner.OnTimer()
    self.owner.SetRefreshTimer(self.Display, self.refreshTimeout)

  def StartTimer(self, timeout=None):
    if timeout == None:
      timeout=self.refreshTimeout
    self.owner.SetRefreshTimer(self.Display, timeout)

  def GetControl(self):
    if isinstance(self, wx.Window):
      return self
    else:
      return self.control

  def OnListColResize(self, evt):
    adm.config.storeListviewPositions(self.control, self, self.panelName)

  def RestoreListcols(self):
    """
    RestoreListcols()
    
    Should be called after columns have been created to restore 
    header column positions 
    """
    adm.config.restoreListviewPositions(self.control, self, self.panelName)
  
class NotebookPage(ControlledPage):
  """
  NotebookCPage
  
  Class implementing the Page methods used in the Notebook
  by default having a single Listview control
  """
  def __init__(self, notebook):
    lvClass=xmlres.getControlClass("whListView")
    if not lvClass:
      raise Exception("Some XMLRES problem: whListView not found")
    self.control=lvClass(notebook, "property") # !!! Module auswerten
    self.control.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnListColResize)
    self.panelName=None
    self.SetOwner(notebook)

  
  def Display(self, node, _detached):
    self.lastNode=node
#    self.control.Freeze()
    self.control.ClearAll()
    if node:
      prop, val=node.GetPropertiesHeader()
      self.control.CreateColumns(prop, val, 15);
      adm.config.restoreListviewPositions(self.control, self)
      for props in node.GetProperties():
        img=-1

        if isinstance(props, tuple):
          props=list(props)
        if isinstance(props, list):
          if len(props) > 2:
            img=int(props[-1])
            del props[-1]
        self.control.AppendItem(img, props)
    else:
      self.control.CreateColumns(self.name);
      self.control.InsertStringItem(0, xlt("No properties are available for the current selection"), -1);
#    self.control.Thaw()


class PropertyPage(NotebookPage):
  name=xlt("Properties")


class NotebookPanel(wx.Panel, adm.ControlContainer):
  """
  NotebookPanel
  
  Class representing a panel usable in a Notebook
  which loads its controls from an xml resource
  """
  def __init__(self, dlg, notebook, resname=None):
    adm.ControlContainer.__init__(self, resname)
    self.dialog=dlg
    res=self.getResource()
    pre=wx.PrePanel()
    res.LoadOnPanel(pre, notebook, self.resname)
    self.PostCreate(pre)
    self.addControls(res)
    self.AddExtraControls(res)
    adm.logger.debug("Controls found in Panel %s/%s: %s", self.module, self.resname, ", ".join(self._ctls.keys()))

  def Bind(self, *args, **kargs):
    adm.ControlContainer.Bind(self, *args, **kargs)

  def __getattr__(self, name):
    return self._getattr(name)

  def __setattr__(self, name, value):
    return self._setattr(name, value)


class PreferencePanel(NotebookPanel):
  """
  PreferencePanel
  
  Class representing a panel used in the main preferences dialog
  for configuration of module specific options
  A node can retrieve a value using node.GetPreference(key)
  """

  @classmethod
  def GetPreference(cls, key):
    default=cls.configDefaults.get(key)
    return adm.config.Read(key, default, cls)

  @classmethod
  def SetPreference(cls, key, val):
    adm.config.Write(key, val, cls)
    
  def Save(self):
    for key in self.configDefaults:
      val=self._getattr(key)
      self.SetPreference(key, val)
    return True
  
  def Go(self):
    for key in self.configDefaults:
      val=self.GetPreference(key)
      self._setattr(key, val)


class NotebookControlsPage(NotebookPage, NotebookPanel):
  """
  NotebookControlsPage
  
  Class implementing the Page methods used in the Notebook
  loading its controls from an xml resource 
  """
  def __init__(self, notebook):
    NotebookPanel.__init__(self, None, notebook)
    self.SetOwner(notebook)

#  def GetControl(self):
#    return self
    
    
  
def getAllPreferencePanelClasses():
  from AdmDialogs import Preferences
  panelclasses=[Preferences]
  for modname, mod in adm.modules.items():
    panel=mod.moduleinfo.get('preferences')
    if not panel:
      adm.logger.debug("Module %s has no preferences", modname)
      continue
    if isinstance(panel, list):
      panelclasses.extend(panel)
    else:
      panelclasses.append(panel)
  return panelclasses

