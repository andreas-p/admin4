# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import sys
if not hasattr(sys, 'skipSetupInit'):

  import Server
  import adm
  import wx
  from wh import xlt, floatToTime
  from LoggingDialog import LogPanel
  
  
  def _PrettyTime(val):
    if not val:
      value=0
    else:
      value=val.total_seconds()
      if value < 0:
        value=0
    return floatToTime(value)
  
  def _StripMask(val):
    if val:
      v=val.split(':')
      return "%s:%s" % (v[0].split('/')[0], v[1])
    return ""
  
  
  class SqlPage:
    name="SQL"
    order=800
    
    def __init__(self, notebook):
      self.control=wx.TextCtrl(notebook, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP)
      self.notebook=notebook
      self.lastNode=None
    
    def GetControl(self):
      return self.control
  
    def Display(self, node, detached):
      if hasattr(node, "GetSql"):
        self.control.SetValue(node.GetSql(detached))
      else:
        self.control.SetValue("not implemented")
        
  
  
     
  class StatisticsPage(adm.NotebookPage):
    name=xlt("Statistics")
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
      conn=page.lastNode.GetConnection()
      for pid in pids:
        conn.ExecuteSingle("SELECT pg_cancel_backend(%d)" % int(pid))
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
      conn=page.lastNode.GetConnection()
      for pid in pids:
        conn.ExecuteSingle("SELECT pg_terminate_backend(%d)" % int(pid))
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
    order=100
    
    colOrder="procpid datname usename clientaddr backend_start query_runtime current_query".split(' ')
    colDef={'procpid': (xlt("PID"), "65535"), 
            'datname': (xlt("Database"), "Postgres-DB"), 
            'usename': (xlt("User"), "postgres"),
            'clientaddr':  (xlt("Client"), "192.168.255.240:50333", _StripMask), 
            'backend_start': (xlt("Client start"), "2014-01-01 12:00:00", lambda x: str(x)[:19]),
            'query_runtime': (xlt("Duration"), 8, _PrettyTime),
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
      
    def Display(self, node, detached):
      if node != self.lastNode:
        add=self.control.AddColumnInfo
        add(xlt("PID"), "65535",                      colname='procpid')
        add(xlt("Database"), "Postgres-DB",           colname='datname')
        add(xlt("User"), "postgres",                  colname='usename')
        add(xlt("Client"), "192.168.255.240:50333",   colname='clientaddr', proc=_StripMask)
        if node.GetServer().version >= 9.0:
          add(xlt("Application Name"), 25,            colname='application_name')
        add(xlt("ClientStart"), "2014-01-01 12:00:00",colname='backend_start', proc=lambda x: str(x)[:19])
        add(xlt("Duration"), 8,                       colname='query_runtime', proc=_PrettyTime)
        add(xlt("Query"), 50,                         colname='current_query')
        self.RestoreListcols()

        self.pid=node.GetConnection(detached).GetPid()
        self.ignorePids=[self.pid]
        self.lastNode=node
        self.control.DeleteAllItems()
        self.TriggerTimer()

      rowset=node.GetConnection(detached).ExecuteSet("SELECT *, client_addr || ':' || client_port::text AS clientaddr, now()-query_start AS query_runtime FROM pg_stat_activity ORDER BY procpid")
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

      
  class Preferences(adm.PreferencePanel):
    name="PostgreSQL"
    configDefaults={ "AdminNamespace":  "Admin4" }
  
    

      
  moduleinfo={ 'name': xlt("PostgreSQL Server"),
              'modulename': "PostgreSQL",
              'description': xlt("PostgreSQL database server"),
              'version': "9.3",
              'revision': "0.3",
              'supports': "PostgreSQL 8.0 ... 9.3 (pre-9.0 with restrictions)",
              'serverclass': Server.Server,
              'pages': [StatisticsPage, ConnectionPage, SqlPage],
              'preferences': Preferences,
              'copyright': "(c) 2013-2014 PSE Consulting Andreas Pflug",
              'credits': "psycopg2 from http://initd.org/psycopg using libpq (http://www.postgresql.org)",
       }