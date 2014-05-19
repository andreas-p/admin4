# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import logger
from wh import StringType, evalAsPython

ignoreStoredPositions=False

class Config(wx.Config):
  """
  OSX: ~/Library/Preferences/<name> Preferences
  """
  def __init__(self, name):
    wx.Config.__init__(self, name, style = wx.CONFIG_USE_LOCAL_FILE)

  def getServers(self):
    return self.Read("Servers", [])


  def Decorate(self, name, obj=None, subname=None):
    if subname:
      name="%s/%s" % (name, subname)
    if obj:
      return "%s/%s" % (obj.__module__, name)
    else:
      return name
    
    
  def Read(self, name, default="", obj=None, subname=None):
    """
    Read(name, default="", obj=None)
    
    Read a config value <name>
    config name might be decorated with <obj> module name
    """
    val=super(Config, self).Read(self.Decorate(name, obj, subname))
    if not val:
      return default

    if not isinstance(default, StringType):
      py=evalAsPython(val)
      if py != None:
        val=py
      else:
        logger.debug("Couldn't pythonize '%s'", val)

    if val == None:
      return default
    return val

  def Write(self, name, val, obj=None, subname=None):
    """
    Write(name, value, obj=None)
    
    Write a config value <name>
    config name might be decorated with <obj> module name
    """
    super(Config, self).Write(self.Decorate(name, obj, subname), str(val))
    self.Flush()

  def getName(self, aspect, module, name):
    if not isinstance(module, StringType):
      if not name:
        if hasattr(module, 'name'):
          name=module.name
        elif hasattr(module, 'resname'):
          name=module.resname
      module=module.__module__

    name="%s/%s:%s" % (module, name, aspect)
    return name.replace('.', '/')

  def getWinName(self, win):
    if isinstance(win, wx.Frame):
      cls="Frame"
    else:
      cls="Dialog"
    return self.getName(cls, win.__module__, win.__class__.__name__)


  def storeWindowPositions(self, win):
    name=self.getWinName(win)
    size=win.GetSize()
    pos=win.GetPosition()
    if win.GetParent():
      pos -= win.GetParent().GetPosition()
    self.Write("%sPosition" % name, ((size.x, size.y), (pos.x, pos.y)))
    if hasattr(win, "manager"):
      str=win.manager.SavePerspective()
      self.Write("%sPerspective" % name, str)

  def GetPerspective(self, win):
    if ignoreStoredPositions:
      return ""
    name=self.getWinName(win)
    return self.Read("%sPerspective" % name, "")


  def getWindowPositions(self, win):
    if ignoreStoredPositions:
      return None, None
    
    name=self.getWinName(win)
    size, pos=self.Read("%sPosition" % name, (None, None))

    xmax = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)
    ymax = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)

    if size and (size[0] < 30 or size[1] < 30):
      size=None
    if size:
      xmax -= size[0]
      ymax -= size[1]
    else:
      xmax -= 30
      ymax -= 30

    if pos and win.GetParent():
      pp = win.GetParent().GetPosition()
      pos = (pos[0]+pp.x,  pos[1]+pp.y)

    if pos and (pos[0] < 0 or pos[0] > xmax or pos[1] < 0 or pos[1] > ymax):
      pos=None


    return size, pos

  def restoreListviewPositions(self, listview, module, name=None):
    if ignoreStoredPositions:
      return
    colcount=listview.GetColumnCount()
    if colcount > 1:
      colWidths=self.Read(self.getName("ColumnWidths", module, name), None)
      if not colWidths:
        return
      if isinstance(colWidths, list):
        for col in range(colcount):
          if col >= len(colWidths):
            return
          listview.SetColumnWidth(col, colWidths[col])
      elif isinstance(colWidths, dict):
        for col in range(colcount):
          colname = listview.GetColumn(col).GetText()
          w=colWidths.get(colname)
          if w != None:
            listview.SetColumnWidth(col, w)
      else:
        logger.debug("Strange ColumnWidths format %s", str(colWidths))
      

  def storeListviewPositions(self, listview, module, name=None):
    colcount=listview.GetColumnCount()
    if colcount > 1:
      colWidths={}
      for col in range(colcount):
        colname = listview.GetColumn(col).GetText()
        colWidths[colname] = listview.GetColumnWidth(col)
      self.Write(self.getName("ColumnWidths", module, name), colWidths)

  def existsServer(self, dlg, name):
    cls=dlg.moduleClass()

    servers=self.getServers()
    return "%s/%s"%(cls,name) in servers

  def storeServerSettings(self, dlg, settings):
    settings=settings
    cls=dlg.moduleClass()
    name="%s/%s" % (cls, settings['name'])
    settings['class'] = cls
    servers=self.getServers()
    if name not in servers:
      servers.append(name)
      self.Write("Servers", str(servers))
    self.Write("Server-%s" % name, settings)

  def getServerSettings(self, sname):
    settings=self.Read("Server-%s" % sname, {})
    return settings
  
  def getHintCfg(self, hint, module):
    h=module.__module__.split('.')
    return "%s/%s" % ("/".join(h[:-1]), hint)
  
  def GetWantHint(self, hint, module):
    return self.Read("Hints", True, None, self.getHintCfg(hint, module))
  
  def SetWantHint(self, hint, module, how):
    self.Write("Hints", how, None, self.getHintCfg(hint, module))
