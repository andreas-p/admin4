# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
import wx, os
import logger
from wh import xlt, Menu, AcceleratorHelper
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
      
    self.control.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnItemRightClick)
    
  
  def ShowPage(self, how):
    if how:
      self.owner.SetRefreshTimer(self.Display, self.refreshTimeout)
      self.TriggerTimer()
    else:
      self.StartTimer(0)
  
     
  def OnItemRightClick(self, evt):
    if hasattr(self, 'OnCopy'):
      cm=Menu(self.dialog)
      cm.Add(self.OnCopy, xlt("Copy"), xlt("Copy"))
      cm.Popup(evt)
     
  
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


  def OnCopy(self, _evt):
    lines=[]
    for i in self.control.GetSelection():
      txt=self.control.GetItemText(i, 1)
      tb=self.control.GetItemText(i, 2)
      if tb:
        lines.append("%s:\n%s" % (txt, tb))
      else:
        lines.append(txt)
    adm.SetClipboard("\n".join(lines))

  def OnClear(self, _evt):
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


  def GetToolTipText(self, tid):
    if tid < 0:
      return
    if not self.insertPosition:
      tid = self.control.GetItemCount()-tid-1
    line=logger.loglines[tid]
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


  def OnCopy(self, _evt):
    lines=[]
    for i in self.control.GetSelection():
      txt=self.control.GetItemText(i, 1)
      lines.append(txt)
    adm.SetClipboard("\n".join(lines))


  def OnClear(self, _evt):
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
       


  def GetToolTipText(self, tid):
    if tid < 0:
      return
    if not self.insertPosition:
      tid = self.control.GetItemCount()-tid-1
    line=logger.querylines[tid]
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

    ah=AcceleratorHelper(self)
    ah.Add(wx.ACCEL_CTRL, 'C', self.BindMenuId(self.OnCopy))
    ah.Realize()
        
  def OnLevel(self, _evt=None):
    self.LogLevelFileStatic=xlt(logger.LOGLEVEL.Text(self.loglevels[self.LogLevelFile]))
    self.LogLevelQueryStatic=xlt(logger.LOGLEVEL.Text(self.querylevels[self.LogLevelQuery]))
  
  def OnApply(self, _evt):
    adm.config.Write("LogLevel", self.loglevels[self.LogLevelFile])
    adm.config.Write("QueryLevel", self.querylevels[self.LogLevelQuery])
    adm.config.Write("LogFile", self.LogFileLog)
    adm.config.Write("QueryFile", self.LogFileQuery)
    self.Init()
    
  def OnCopy(self, evt):
    nb=self['Notebook']
    page=nb.GetPage(nb.GetSelection())
    if hasattr(page, "OnCopy"):
      page.OnCopy(evt)
  
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


  def OnClose(self, _evt):
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
