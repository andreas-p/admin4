# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import wx
from wh import xlt, floatToTime, floatToSize, sizeToFloat, timeToFloat, evalAsPython
from LoggingDialog import LogPanel


  
def prettyTime(val):
  if not val:
    value=0
  else:
    value=val.total_seconds()
    if value < 0:
      value=0
  return floatToTime(value)

def stripMask(val):
  if val:
    v=val.split(':')
    return "%s:%s" % (v[0].split('/')[0], v[1])
  return ""



class StatisticsPage(adm.NotebookPage):
  name=xlt("Statistics")
  availableOn="Server"
  order=1000

  def Display(self, node, _detached):
    if node != self.lastNode:
      self.control.ClearAll()
      self.lastStats=None

      self.lastNode=node
      
      if node:
        if hasattr(node, "GetStatisticsQuery"):
          icon=node.GetImageId('statistics')
          self.control.AddColumn( xlt("Statistics"), 20)
          self.control.AddColumn( xlt("Value"), -1)
          rowset=node.ExecuteSet(node.GetStatisticsQuery())
          for row in rowset:
            for cn in row.colNames:
              self.control.AppendItem(icon, [cn, row[cn]])

        elif hasattr(node, "GetStatistics"):
          icon=node.GetImageId('database')
          rowset=node.GetStatistics()
          first=True
          for cn in rowset.colNames:
            if first:
              first=False
              self.control.AddColumn(cn, 12)
            else:
              self.control.AddColumn(cn, 8)
          for row in rowset:
            vals=[]
            for i in range(len(rowset.colNames)):
              vals.append(row[i])
            self.control.AppendItem(icon, vals)
                
              
            
      self.lastNode=node
    
def _getSelectedPids(page):
  pids=page.GetSelected()
  try:
    pids.remove(str(page.pid))
  except:
    pass
  return pids
  
class CancelQuery:
  name=xlt("Cancel")
  help=xlt("Cancel current query")
  
  @staticmethod
  def CheckAvailableOn(page):
    pids=_getSelectedPids(page)
    return len(pids) > 0  

  @staticmethod
  def OnExecute(_parentWin, page):
    pids=_getSelectedPids(page)
    cursor=page.lastNode.GetCursor()
    for pid in pids:
      cursor.ExecuteSingle("SELECT pg_cancel_backend(%d)" % int(pid))
    return False


class TerminateBackend:
  name=xlt("Terminate")
  help=xlt("Terminate backend")
  
  @staticmethod
  def CheckAvailableOn(page):
    pids=_getSelectedPids(page)
    return len(pids) > 0  

  @staticmethod
  def CheckEnabled(page):
    return page.lastNode.GetValue('pg_terminate_backend')

  @staticmethod
  def OnExecute(_parentWin, page):
    pids=_getSelectedPids(page)
    cursor=page.lastNode.GetCursor()
    for pid in pids:
      cursor.ExecuteSingle("SELECT pg_terminate_backend(%d)" % int(pid))
    return False

class HideBackend:
  name=xlt("Hide")
  help=xlt("Hide backend")
  
  @staticmethod
  def CheckAvailableOn(page):
    pids=page.GetSelected()
    return len(pids) > 0  

  @staticmethod
  def OnExecute(_parentWin, page):
    pids=_getSelectedPids(page)
    page.ignorePids.extend(map(int, pids))
    page.TriggerTimer()
    return False

class UnhideBackends:
  name=xlt("Show hidden")
  help=xlt("Show hidden backends")
  @staticmethod
  def CheckEnabled(page):
    return len(page.ignorePids)>0
  
  @staticmethod
  def OnExecute(_parentWin, page):
    page.ignorePids=[]
    page.TriggerTimer()


class ConnectionPage(LogPanel):
  name=xlt("Connections")
  menus=[CancelQuery, TerminateBackend, HideBackend, UnhideBackends]
  availableOn="Server"
  order=800
  
  colOrder="procpid datname usename clientaddr backend_start query_runtime current_query".split(' ')
  colDef={'procpid': (xlt("PID"), "65535"), 
          'datname': (xlt("Database"), "Postgres-DB"), 
          'usename': (xlt("User"), "postgres"),
          'clientaddr':  (xlt("Client"), "192.168.255.240:50333", stripMask), 
          'backend_start': (xlt("Client start"), "2014-01-01 12:00:00", lambda x: str(x)[:19]),
          'query_runtime': (xlt("Duration"), 8, prettyTime),
          'current_query': (xlt("Query"), 50) }


  def __init__(self, notebook):
    LogPanel.__init__(self, notebook, notebook, "Connections")

    self.SetOwner(notebook)
#      adm.NotebookPage.__init__(self, notebook)

    self.control.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, notebook.OnItemRightClick)
    if wx.Platform == "__WXMSW__":
      self.control.Bind(wx.EVT_RIGHT_UP, notebook.OnItemRightClick)

  
  def GetSelected(self):
    return self['Listview'].GetSelectionKeys()
    
  def Display(self, node, _detached):
    if node != self.lastNode:
      add=self.control.AddColumnInfo
      add(xlt("PID"), "65535",                      colname='procpid')
      add(xlt("Database"), "Postgres-DB",           colname='datname')
      add(xlt("User"), "postgres",                  colname='usename')
      add(xlt("Client"), "192.168.255.240:50333",   colname='clientaddr', proc=stripMask)
      if node.GetServer().version >= 9.0:
        add(xlt("Application Name"), 25,            colname='application_name')
      add(xlt("ClientStart"), "2014-01-01 12:00:00",colname='backend_start', proc=lambda x: str(x)[:19])
      add(xlt("Duration"), 8,                       colname='query_runtime', proc=prettyTime)
      add(xlt("Query"), 50,                         colname='current_query')
      self.RestoreListcols()

      self.pid=node.GetCursor().GetPid()
      self.ignorePids=[]
      self.lastNode=node
      self.control.DeleteAllItems()
      self.TriggerTimer()

    rowset=node.GetCursor().ExecuteSet("SELECT *, client_addr || ':' || client_port::text AS clientaddr, now()-query_start AS query_runtime FROM pg_stat_activity ORDER BY procpid")
    dbIcon=node.GetImageId('Database')
    ownDbIcon=node.GetImageId('Database-conn')
    rows=[]
    for row in rowset:
      pid=row['procpid']
      if pid in self.ignorePids:
        continue

      if pid == self.pid:
        icon=ownDbIcon
      else:
        icon=dbIcon
      rows.append( (row, icon))
    self.control.Fill(rows, 'procpid')


class SettingsPage(adm.NotebookPage):
  name=xlt("Settings")
#  menus=[AlterConfigValue]
  availableOn="Server"
  order=850
   
  def Display(self, node, _detached):
    def setting(row):
      unit=row['unit']
      val=row['setting']
      if not unit:
        return val
      ul=unit.lower()
      if ul == "8kb":
        return floatToSize(int(val)*8192)
      val="%s %s" % (val, unit)
      if ul in ['kb', 'mb', 'gb']:
        return floatToSize(sizeToFloat(val[:-1] + "iB"))
      elif ul in ['ms', 's', 'h', 'min']:
        return floatToTime(timeToFloat(val))
      else:
        return val
    
    if node != self.lastNode:
      self.control.DeleteAllItems()
      self.lastNode=node
      add=self.control.AddColumnInfo
      add(xlt("Name"), "OneArbitraryNameToConsumeSpace",        colname='name')
      add(xlt("Setting"),                                       proc=setting)
      add("rowDict", 0,                                         proc=lambda row: str(row.getDict()) )
    
      rowset=node.GetCursor().ExecuteSet("SELECT * FROM pg_settings ORDER BY context, setting")
      icon=-1 # node.GetImageId('Database')
  
      rows=[]
      for row in rowset:
        rows.append( (row, icon) )
      self.control.Fill(rows, 'name')

  def OnItemDoubleClick(self, evr):
    if self.lastNode.version >= 9.4:
      vals=evalAsPython(self.control.GetItemText(evr.GetIndex(), 2))
      print "EDIT SETTING CODE HERE", vals 

    
pageinfo = [StatisticsPage, ConnectionPage, SettingsPage]
  
