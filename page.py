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
  from frame import Preferences
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

