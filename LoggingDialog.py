# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
import wx, os
import logger
from wh import xlt
from page import ControlledPage

from notebook import _TimerOwner



class LogPanel(adm.NotebookPanel, ControlledPage):
  def __init__(self, dlg, notebook, panelName):
    adm.NotebookPanel.__init__(self, dlg, notebook, "./LogPanel")
    self.panelName=panelName
    
    self.control=self['Listview']
    if hasattr(self, 'GetToolTipText'):
      self.control.RegisterToolTipProc(self.GetToolTipText)
    self.control.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnListColResize)
    if hasattr(self, 'OnClear'):
      self.Bind("Clear", self.OnClear)
    else:
      self['Clear'].Hide()
      
#    self.control.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, notebook.OnItemRightClick)
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
    
  
  def ShowPage(self, how):
    if how:
      self.owner.SetRefreshTimer(self.Display, self.refreshTimeout)
      self.TriggerTimer()
    else:
      self.StartTimer(0)

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

  def EnsureVisible(self):
    if self.control.GetItemCount():
      if not self.control.GetSelection():
        if self.insertPosition:
          self.control.EnsureVisible(self.control.GetItemCount()-1)
        else:
          self.control.EnsureVisible(0)


      
class LoggingPanel(LogPanel):
  def __init__(self, dlg, notebook):
    LogPanel.__init__(self, dlg, notebook, "Logging")
    self.SetOwner(dlg)
    add=self.control.AddColumnInfo
    add(xlt("Timestamp"), "2014-01-01 20:00:00", colname='timestamp')
    add(xlt("Text"), 50, colname='text')
    add(xlt("Traceback"), 20, colname='tb')
    self.RestoreListcols()
    self.logIndex=0
    self.insertPosition=-1 # 0: start, -1: end


  def OnClear(self, evt):
    self.logIndex=0
    logger.loglines=[]
    self.control.DeleteAllItems()
    self.Display()

  def Display(self):
    maxlog=len(logger.loglines)
    if maxlog > self.logIndex:
      for i in range(self.logIndex, maxlog):
        line=logger.loglines[i]
  
        if line.tb:
          tb=str(line.tb)
        else:
          tb=""
        self.control.InsertItem(self.insertPosition, line.LevelImageId(), [line.Timestamp(), line.text, tb])
      self.logIndex=maxlog
      self.EnsureVisible()


  def GetToolTipText(self, id):
    if id < 0:
      return
    if not self.insertPosition:
      id = self.control.GetItemCount()-id-1
    line=logger.loglines[id]
    lines=[]
    lines.append("%s - %s" % (line.Timestamp(), line.LevelText()))
    lines.append(line.text)
    if line.tb:
      lines.append(str(line.tb))
    return "\n".join(lines)



class QueryLoggingPanel(LogPanel):
  def __init__(self, dlg, notebook):
    LogPanel.__init__(self, dlg, notebook, "Query")
    self.SetOwner(dlg)
    
    def getresult(row):
      err=row['error']
      if err:
        return err
      return row['result']
    
    add=self.control.AddColumnInfo
    add(xlt("Timestamp"), "2014-01-01 20:00:00", colname='timestamp')
    add(xlt("Query"), 50, colname='cmd')
    add(xlt("Result"), 50, proc=getresult)
    self.RestoreListcols()
    self.logIndex=0
    self.insertPosition=-1 # 0: start, -1: end


  def OnClear(self, evt):
    self.logIndex=0
    logger.querylines=[]
    self.control.DeleteAllItems()
    self.Display()


  def Display(self):
    maxlog=len(logger.querylines)
    for i in range(self.logIndex, maxlog):
      line=logger.querylines[i]
      self.control.InsertItem(self.insertPosition, line.LevelImageId(), [line.Timestamp(), line.cmd, line['err+result']])
    self.logIndex=maxlog
    self.EnsureVisible()
       


  def GetToolTipText(self, id):
    if id < 0:
      return
    if not self.insertPosition:
      id = self.control.GetItemCount()-id-1
    line=logger.querylines[id]
    lines=[]
    lines.append("%s - %s" % (line.Timestamp(), line.LevelText()))
    lines.append(line.cmd)
    if line.error:
      lines.append("ERROR - %s" % line.error)
    if line.result:
      lines.append(" -> %s" % line.result)
    return "\n".join(lines)


  
class LoggingDialog(adm.Dialog, _TimerOwner):
  loglevels=[logger.LOGLEVEL.NONE, logger.LOGLEVEL.CRIT, logger.LOGLEVEL.ERROR, logger.LOGLEVEL.INFO, logger.LOGLEVEL.DEBUG]
  querylevels=[logger.LOGLEVEL.NONE, logger.LOGLEVEL.ERROR, logger.LOGLEVEL.DEBUG]
  
  def __init__(self, parentWin):
    adm.Dialog.__init__(self, parentWin, None, "LoggingDialog")
    _TimerOwner.__init__(self)
    
    self.Bind(wx.EVT_CLOSE, self.OnClose)
    self.Bind("Apply", self.OnApply)

    nb=self['notebook']
    panel=LoggingPanel(self, nb)
    nb.InsertPage(0, panel, xlt(panel.panelName))
    panel=QueryLoggingPanel(self, nb)
    nb.InsertPage(1, panel, xlt(panel.panelName))
    self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChange)
    
    self['LogLevelFile'].SetRange(0, len(self.loglevels)-1)
    self['LogLevelQuery'].SetRange(0, len(self.querylevels)-1)
    self.Bind("LogLevelFile LogLevelQuery", wx.EVT_COMMAND_SCROLL, self.OnLevel)

    self.LogLevelFile=self.loglevels.index(logger.loglevel)
    self.LogLevelQuery=self.querylevels.index(logger.querylevel)
    self.LogFileLog = logger.logfile
    self.LogFileQuery=logger.queryfile
    self.OnLevel()

    
  def OnLevel(self, evt=None):
    self.LogLevelFileStatic=xlt(logger.LOGLEVEL.Text(self.loglevels[self.LogLevelFile]))
    self.LogLevelQueryStatic=xlt(logger.LOGLEVEL.Text(self.querylevels[self.LogLevelQuery]))
  
  def OnApply(self, evt):
    adm.config.Write("LogLevel", self.loglevels[self.LogLevelFile])
    adm.config.Write("QueryLevel", self.querylevels[self.LogLevelQuery])
    adm.config.Write("LogFile", self.LogFileLog)
    adm.config.Write("QueryFile", self.LogFileQuery)

    self.Init()
    

  def OnPageChange(self, evt=None):
    nb=self['Notebook']
    if evt:
      prevPage = nb.GetPage(evt.GetOldSelection())
      if prevPage and hasattr(prevPage, 'ShowPage'):
        prevPage.ShowPage(False)
      newPage = nb.GetPage(evt.GetSelection())
    else:
      newPage = nb.GetCurrentPage()
    if newPage and hasattr(newPage, 'ShowPage'):
      newPage.ShowPage(True)
    

  def Go(self):
    self.Show() # needed for wx < 3.0 for SetSelection
    self['notebook'].SetSelection(0)
    self.OnPageChange()


  def OnClose(self, evt):
    if self.timer:
      self.timer.Stop()
    self.Close()

  @staticmethod
  def Init():
    logger.loglevel=adm.config.Read("LogLevel", logger.LOGLEVEL.ERROR)
    logger.querylevel=adm.config.Read("QueryLevel", logger.LOGLEVEL.NONE)
    logdir=wx.StandardPaths.Get().GetDocumentsDir()
    logger.logfile=adm.config.Read("LogFile", os.path.join(logdir, "%s.log" % adm.appname))
    logger.queryfile=adm.config.Read("QueryFile", "")
