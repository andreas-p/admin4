# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import wx.html
import wx.propgrid as wxpg
from page import ControlledPage
from wh import xlt, floatToTime, floatToSize, sizeToFloat, timeToFloat, breakLines, GetBitmap, Menu
from _pgsql import quoteValue
from Validator import Validator
from LoggingDialog import LogPanel
import logger
import csv, cStringIO

  
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
    cursor=None
    if node.version < 9.2:
      pidCol="procpid"
    else:
      pidCol="pid"
    if node != self.lastNode:
      add=self.control.AddColumnInfo
      add(xlt("PID"), "65535",                      colname=pidCol)
      add(xlt("Database"), "Postgres-DB",           colname='datname')
      add(xlt("User"), "postgres",                  colname='usename')
      add(xlt("Client"), "192.168.255.240:50333",   colname='clientaddr', proc=stripMask)
      if node.GetServer().version >= 9.0:
        add(xlt("Application Name"), 25,            colname='application_name')
      add(xlt("ClientStart"), "2014-01-01 12:00:00",colname='backend_start', proc=lambda x: str(x)[:19])
      add(xlt("Duration"), 8,                       colname='query_runtime', proc=prettyTime)
      add(xlt("Query"), 50,                         colname='current_query')
      self.RestoreListcols()

      cursor=node.GetCursor()
      self.pid=cursor.GetPid()
      self.ignorePids=[]
      self.lastNode=node
      self.control.DeleteAllItems()
      self.TriggerTimer()

    if not cursor:
      cursor=node.GetCursor()
    rowset=cursor.ExecuteSet("""
    SELECT *, client_addr || ':' || client_port::text AS clientaddr, now()-query_start AS query_runtime 
      FROM pg_stat_activity
     ORDER BY %s"""  % pidCol)
    dbIcon=node.GetImageId('Database')
    ownDbIcon=node.GetImageId('Database-conn')
    rows=[]
    for row in rowset:
      pid=row[pidCol]
      if pid in self.ignorePids:
        continue

      if pid == self.pid:
        icon=ownDbIcon
      else:
        icon=dbIcon
      rows.append( (row, icon))
    self.control.Fill(rows, pidCol)
    cursor=None


class ServerSetting(adm.CheckedDialog):
  contextDesc={'internal': xlt("Cannot be changed"), 'postmaster': xlt("Needs server restart to get applied"),
               'sighup': xlt("Needs reload go get applied"), 'backend': xlt("Used for new backends after a reload"),
               'superuser': xlt("Can be overridden by superuser SET command"), 'user': xlt("Can be overridden by SET command")  }

  def __init__(self, server, page, vals):
    # we need self.vals in AddExtraControls, but normal assignment isn't available before __init__
    self.SetAttr('vals', vals)
    adm.CheckedDialog.__init__(self, page.grid)
    self.server=server
    self.page=page
    self.Bind("Reset", self.OnReset)
    self.BindAll("Reset")
  
  def AddExtraControls(self, res):
    self.type=self.vals['vartype']
    if self.type == 'bool':
      self.value=wx.CheckBox(self)
    elif self.type == 'enum':
      self.value=wx.ComboBox(self, style=wx.CB_READONLY|wx.CB_DROPDOWN)
      self.value.AppendItems(self.vals['enumvals'])
    elif self.type == 'integer':
      self.value = wx.TextCtrl(self)
      self.value.validator=Validator.Get('uint')
    elif self.type == 'real':
      self.value=wx.TextCtrl(self)
#      self.value.validator=Validator.Get('real') TODO
    elif self.type == 'string':
      self.value=wx.TextCtrl(self)
    else:
      self.value=wx.TextCtrl(self)
      logger.debug("Unknown pg_settings vartype %s", self.type)

    res.AttachUnknownControl("ValuePlaceholder", self.value)
    self._ctls['value'] = self.value


  def SetVal(self, val):
    if self.type == 'bool':
      self.value.SetValue(val in ['true', 'on'])
    elif self.type == 'enum':
      self.value.SetStringSelection(val)
    else:
      self.value.SetValue(val)
  
  def GetVal(self):
    if self.type == 'bool':
      if self.value.GetValue(): return 'on'
      else:                     return 'off'
    else:
      return self.value.GetValue()
    
  def Go(self):
    name=self.vals['name']
    unit=self.vals['unit']
    if unit:
      self.ValueLabel="%s (%s)" % (self.ValueLabel, unit)
      
    self.canWrite = self.page.lastNode.version >= 9.4 or self.page.lastNode.GetValue('admin4.instrumentation')

    self.Name=name
    self.Category=self.vals['category']
    context=self.vals['context']
    self.Context="%s - %s" % (context, xlt(ServerSetting.contextDesc.get(context)))
    self.short_desc=breakLines(self.vals['short_desc'], 40)
    self.extra_desc=breakLines(self.vals['extra_desc'], 40)
    
    if name in self.page.changedConfig:
      self.SetVal(self.page.changedConfig[name])
    else:
      self.SetVal(self.vals['setting'])
    
    if not self.canWrite or context == 'internal':
      self.EnableControls("VALUE OK Reset Reload", False)

  
  def OnReset(self, evt):
    self.SetVal(self.vals['reset_val'])
    self.OnCheck(evt)

  
  def Check(self):
    if self.type == 'bool':
      self['value'].SetLabel(self.GetVal())
    ok=True
    ok=self.CheckValid(ok, self.canWrite, xlt("Can save to instrumented servers only."))
    ok=self.CheckValid(ok, self.vals['context'] != 'internal', xlt("Internal setting; cannot be edited."))
    minVal=self.vals['min_val']
    ok=self.CheckValid(ok, minVal==None or self.value.GetValue() >=minVal, xlt("Must be %s or more") % minVal)
    maxVal=self.vals['max_val']
    ok=self.CheckValid(ok, maxVal==None or self.value.GetValue() <=maxVal, xlt("Must be %s or less") % maxVal)
    
    return ok

  def Save(self):
    name=self.vals['name']
    val=self.GetVal()
    cursor=self.server.GetCursor()
    self.SetStatus(xlt("Setting value..."))
    if self.page.lastNode.version < 9.4:
      cfg={}
      file=cursor.ExecuteSingle("SELECT pg_read_file('postgresql.auto.conf', 0, 999999)")
      for line in file.splitlines():
        if line.startswith('#') or not line.strip() or line == InstrumentConfig.autoconfLine:
          continue
        n,_,v = line.partition('=')
        cfg[n]=v
      cfg[name]="'%s'" % val
      lines=[InstrumentConfig.autoconfHeader]
      for name, val in cfg.items():
        lines.append("%s=%s" % (name, val))
      lines.append("")
      
      cursor.ExecuteSingle("""
                SELECT pg_file_unlink('postgresql.auto.conf.bak');
                SELECT pg_file_write('postgresql.auto.conf.tmp', %s, false);
                SELECT pg_file_rename('postgresql.auto.conf.tmp', 'postgresql.auto.conf', 'postgresql.auto.conf.bak');
                """ % quoteValue("\n".join(lines)))
    else:
      cursor.ExecuteSingle("ALTER SYSTEM SET %s=%s" % (name, quoteValue(val, cursor)))
      
    self.page.SetProperty(name, val)

    if self.Reload:
      self.page.DoReload()
    return True  
  

class LoggingPage(adm.NotebookPanel, ControlledPage):
  name=xlt("Serverlog")
#  menus=[AlterConfigValue]
  availableOn="Server"
  order=840

  def __init__(self, notebook):
    adm.NotebookPanel.__init__(self, notebook, notebook)
    self.lastNode=None
    self.panelName="ServerLog"
    self.SetOwner(notebook)
    self.control=self['LogLines']
    self.control.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnLoglinesDclick)
    self.control.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnLoglineRightClick)
    self.Bind('Refresh', self.OnRefresh)
    self.Bind('Rotate', self.OnRotate)
    self.Bind('Logfile', self.OnSelectLogfile)
    self.RestoreListcols()


  logColNames=[ 'log_datetime',
                'log_time',     # shortened version of log_datetime
                'user_name',
                'database_name',
                'process_id',
                'connection_from',
                'session_id',
                'session_line_num',
                'command_tag',
                'session_start_datetime',
                'session_start_time',   # shortened version of session_start_datetime
                'virtual_transaction_id',
                'transaction_id',
                'error_severity',
                'sql_state_code',
                'message',
                'detail',
                'hint',
                'internal_query',
                'internal_query_pos',
                'context',
                'query',
                'query_pos',
                'location',
                'application_name']
  
  @staticmethod
  def getIndex(toFind):
    return LoggingPage.logColNames.index(toFind)
  
  logColInfo={  'log_datetime':           (xlt("Log time"), "2012-02-02 20:20:20.999 MEST"),
                'log_time':               (xlt("Log time"), "20:20:20.999", True),
                'user_name':              (xlt("User"), "postgres123"),
                'database_name':          (xlt("Database"), "postgres123"),
                'process_id':             (xlt("PID"), "12345"),
                'connection_from':        (xlt("From"), "192.168.100.100:7777"),
                'session_id':             (xlt("Session"), "5a5b5c5d.6543"),
                'session_line_num':       (xlt("Session line"), "1234"),
                'command_tag':            (xlt("Tag"), "some command tag"),
                'session_start_datetime': (xlt("Start"), "2012-02-02 20:20:20.999 MEST", True),
                'session_start_time':     (xlt("Start"), "10:10:10.999"),
                'virtual_transaction_id': (xlt("Virt XactID"), "12345"),
                'transaction_id':         (xlt("XactID"), "12345"),
                'error_severity':         (xlt("Severity"), "NOTICE"),
                'sql_state_code':         (xlt("SQL State"), "00000"),
                'message':                (xlt("Message"), 50),
                'detail':                 (xlt("Detail"), 50),
                'hint':                   (xlt("Hint"), 50),
                'internal_query':         (xlt("Internal Query"), 50),
                'internal_query_pos':     (xlt("Internal pos"), "1234"),
                'context':                (xlt("Context"), 40),
                'query':                  (xlt("Query"), 50),
                'query_pos':              (xlt("Query pos"), "1234"),
                'location':               (xlt("Location"), 30),
                'application_name':       (xlt("Application"), 30)
              }
  
  displayCols=['log_time', 'database_name', 'process_id', 'error_severity', 'message']
  
  
  def Display(self, node, _detached):
    logfile=self['LogFile']
    if self.lastNode != node:
      self.lastNode=node
      self.control.ClearAll()
      self.log=[]
      
      logdes=node.GetValue('log_destination')
      if not node.GetValue('pg_rotate_logfile'):
        errText=xlt("Server version too old; not supported")
      if node.GetValue('logging_collector') !='on':
        errText=xlt("logging_collector not enabled")
      elif node.GetValue('log_filename' != 'postgresql-%%Y-%%m-%%d-%%H%%M%%S'):
        errText=xlt("non-default log_filename")
      elif not logdes or logdes.find('csvlog') < 0:
        errText=(xlt("no csv log_destination")) 
      else:
        errText=None
      if errText:
        logfile.Disable()
        self.control.AddColumn("")
        self.control.InsertStringItem(0, errText, -1)
        self.EnableControls('Rotate', False)
        return

      logfile.Clear()
      logfile.Enable()
      logfile.Append(xlt("Current log"))
      logfile.SetSelection(0)
      
      for cn in self.displayCols:
        ci=self.logColInfo.get(cn)
        text=ci[0]
        collen=ci[1]
        self.control.AddColumnInfo(xlt(text), collen, cn)
      self.lastLogfile=None
      self.TriggerTimer()
    
    # periodic read starts here 
    cursor=self.lastNode.GetCursor()
    logfile=self['LogFile']
    dir=cursor.ExecuteList("SELECT pg_ls_dir('%s')" % self.lastNode.GetValue('log_directory'))
    dir.sort()
    for fn in dir:
      if fn.endswith('.csv'):
        if logfile.FindString(fn) < 0:
          logfile.Insert(fn, 1)
    
    if logfile.GetCount() < 2:
      return
    if not self.lastLogfile:
      self.OnSelectLogfile(None)
    
    
    log=""
    while True:
      fn="%s/%s" % (self.lastNode.GetValue('log_directory'), self.lastLogfile)
      
      while True:
        res=cursor.ExecuteSingle("SELECT pg_read_file('%s', %d, %d)" % (fn, self.lastLogpos, 50000))
        if res:
          log += res
          self.lastLogpos += len(res)
        else:
          break
      if logfile.GetSelection():
        break
      
      current=logfile.FindString(self.lastLogfile)
      if current == 1:
        break
      
      self.lastLogpos=0
      self.lastLogfile = logfile.GetString(current-1)


    c=csv.reader(cStringIO.StringIO(log), delimiter=',', quotechar='"')
    
    startdatetimepos=self.getIndex('session_start_datetime')
    severitypos=self.getIndex('error_severity')
    statepos=self.getIndex('sql_state_code')
    for linecols in c:
      time=linecols[0].split()[1] # time only
      linecols.insert(1, time)
      
      time=linecols[startdatetimepos].split()[1] # time only
      linecols.insert(startdatetimepos+1, time)
      
      self.log.append(linecols)
      
      vals=[]
      for colname in self.displayCols:
        colnum=self.getIndex(colname)
        vals.append(linecols[colnum].decode('utf-8'))
      severity=linecols[severitypos]

      if severity.startswith('DEBUG'):
        severity='DEBUG'
      elif severity in ['FATAL', 'PANIC']:
        severity='FATAL'
      elif severity in ['WARNING', 'ERROR']:
        severity='ERROR'
      else:
        sqlstate=linecols[statepos]
        if sqlstate > "1":
          severity="ERROR"
        else:
          severity='LOG'
      icon=node.GetImageId(severity)
      self.control.AppendItem(icon, vals)
        
  def OnSelectLogfile(self, evt):
    logfile=self['LogFile']
    if logfile.GetSelection() == 0:
      self.lastLogfile=logfile.GetString(1)
    else:
      self.lastLogfile=logfile.GetStringSelection()
    
    self.lastLogpos=0
    self['LogLines'].DeleteAllItems()
    self.log=[]
    self.OnRefresh()
 
  @staticmethod   
  def ShowQueryTool(parent, server, line):
    from QueryTool import QueryFrame
    params={'dbname': line[LoggingPage.getIndex('database_name')], 
            'query': line[LoggingPage.getIndex('query')], 
            'errline': line[LoggingPage.getIndex('query_pos')], 
            'message': line[LoggingPage.getIndex('message')], 
            'hint': line[LoggingPage.getIndex('hint')]}
    
    frame=QueryFrame(adm.GetCurrentFrame(parent), server, params)
    return frame

    
    
  class LoglineDlg(adm.Dialog):
    def __init__(self, parentWin, server, logline):
      adm.Dialog.__init__(self, parentWin)
      self.logline=logline
      self.server=server
      self.Bind('QueryTool', self.OnQueryTool)
      
    def AddExtraControls(self, res):
      self.browser=wx.html.HtmlWindow(self)
      res.AttachUnknownControl("HtmlWindow", self.browser)
        
    def getVal(self, name):
      return self.logline[LoggingPage.getIndex(name)].decode('utf-8')
    
    def Go(self):
      lines=[]
      lines.append("<html><body><table>")
      def add(name, txt):
        val=self.getVal(name)
        if val != "":
          val=val.replace('\n', '<br/>')
          lines.append("<tr><td><b>%s</b></td><td>%s</td></tr>" % (txt, val))

      self.SetTitle(self.logline[0])
      for name in LoggingPage.logColNames:
        ci=LoggingPage.logColInfo.get(name)
        if not ci or (len(ci) > 2 and ci[2]): 
          continue
        add(name, xlt(ci[0]))
      lines.append("</table></body></html>")
      self.browser.SetPage("\n".join(lines))
      self.query=self.getVal('query')
      self.EnableControls("QueryTool", self.query)
      
    def OnQueryTool(self, evt):
      LoggingPage.ShowQueryTool(self, self.server, self.logline)
      self.Close()
      
    def Execute(self):
      return True
    
  def OnLoglineRightClick(self, evt):
    cm=Menu(adm.GetCurrentFrame(self))
    sel=self.control.GetSelection()
    if not sel:
      sel=[evt.GetIndex()]
      self.control.SetSelection(sel)
    cm.Add(self.OnCopy, xlt("Copy"), xlt("Copy line to clipboard"))
    
    q=self.log[sel[0]][self.getIndex('query')]
    if q:
      cm.Add(self.OnQuery, xlt("Query"), xlt("Execute query"))
    cm.Add(self.OnLoglinesDclick, xlt("Details"), xlt("Show details"))
    cm.Popup(evt)

  def OnQuery(self, evt):
    index=self.control.GetSelection()[0]
    logline=self.log[index]
    LoggingPage.ShowQueryTool(self, self.lastNode, logline)
  
  def OnCopy(self, evt):
    lines=self.control.GetSelection()
    if lines:
      sio=cStringIO.StringIO()
      cwr=csv.writer(sio, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
      
      cwr.writerow(self.logColNames)
      for i in lines:
        cwr.writerow(self.log[i])
      
      data=sio.getvalue().decode('utf-8')
      adm.SetClipboard(data)
      
  def OnLoglinesDclick(self, evt):
    if hasattr(evt, 'GetIndex'):  index=evt.GetIndex()
    else:                         index=self.control.GetSelection()[0]
    
    dlg=self.LoglineDlg(self.owner, self.lastNode, self.log[index])
    dlg.Go()
    dlg.Show()
    
  def OnRotate(self, evt):
    self.lastNode.GetCursor().ExecuteSingle("SELECT pg_rotate_logfile()")
    pass

class SettingsPage(adm.NotebookPanel, ControlledPage):
  name=xlt("Settings")
#  menus=[AlterConfigValue]
  availableOn="Server"
  order=850

  def __init__(self, notebook):
    adm.NotebookPanel.__init__(self, notebook, notebook)
    self.lastNode=None
    self.grid.Bind(wxpg.EVT_PG_DOUBLE_CLICK, self.OnItemDoubleClick)
    self.Bind('Apply', self.OnApply)
    self.Bind('Find', self.OnFind)
    self.grid.Bind(wxpg.EVT_PG_SELECTED, self.OnSelChanging)
    self.lastFindProperty=None

  def AddExtraControls(self, res):
    self.grid=wxpg.PropertyGrid(self)
    res.AttachUnknownControl("ValueGrid", self.grid)
    

  def OnSelChanging(self, evt):
    if self.lastFindProperty:
      self.grid.SetPropertyColoursToDefault(self.lastFindProperty)
      self.grid.RefreshProperty(self.grid.GetProperty(self.lastFindProperty))
      self.lastFindProperty=None
  
  def OnMouseMove(self, evt):
    txt=""
    pos=self.grid.HitTest(evt.GetPosition())
    if pos:
      property=pos.GetProperty()
      if property:
        name=property.GetName()
        cfg=self.currentConfig.get(name)
        if cfg:
          txt=cfg['short_desc']
    self.grid.SetToolTipString(txt)
    evt.Skip()
      
    
  def Display(self, node, _detached):
    
    def valFmt(val, unit):
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
    def setting(row):
      return valFmt(row['setting'], row['unit'])
    def changedSetting(row):
      name=row['name']
      if name in self.changedConfig:
        cv=self.changedConfig[name]
        if cv != row['setting']:
          return valFmt(cv, row['unit'])
    
    
    if node != self.lastNode:
      self.changedConfig={}
      if node.GetValue('postgresql.auto.conf'):
        try:
          cursor=node.GetCursor()
          cursor.SetThrowSqlException(False)
          confFile=cursor.ExecuteSingle("SELECT pg_read_file('postgresql.auto.conf', 0, 999999)")
          for line in confFile.splitlines():
            if line.startswith('#'):
              continue
            i=line.find('=')
            if i<0:
              logger.debug("postgresql.auto.conf format error")
              continue
            name=line[:i].strip()
            val=line[i+1:].strip()
            if val.startswith("'"):
              val=val[1:-1]
            self.changedConfig[name]=val
        except:  pass


      self.grid.Clear()
      self.lastNode=node
      
      sort=[]
      i=1
      
      for cat in self.lastNode.GetPreference('SettingCategorySort').split():
        sort.append("WHEN substr(category,1,%01d)='%s' THEN '%d'" % (len(cat), cat, i))
        i += 1 

      if sort:
        sortCase="CASE %s ELSE '' END || category" % " ".join(sort)
      else:
        sortCase=""
      sort=""
      rowset=node.GetCursor().ExecuteSet("SELECT * FROM pg_settings ORDER BY %s || category, setting" % sortCase)
  
      self.currentConfig={}
      category=None
      stdIcon=GetBitmap('setting', self)
      chgIcon=GetBitmap('settingChanged', self)
      intIcon=GetBitmap('settingInternal', self)
      for row in rowset:
        name=row['name']
        if category != row['category']:
          category = row['category']
          prop=wxpg.PropertyCategory(category)
          self.grid.Append(prop)

        icon=stdIcon
        setting=row['setting']
        self.currentConfig[name]=row.getDict()
        if row['context'] == 'internal':
          icon=intIcon
        if name in self.changedConfig:
          chg=self.changedConfig[name]
          if chg != setting:
            icon=chgIcon
            setting="%s   (->%s)" % (setting, chg)
        prop=wxpg.StringProperty(name)
        self.grid.Append(prop)
        self.grid.SetPropertyImage(name, icon)
        self.grid.SetPropertyValue(name, setting)
        self.grid.SetPropertyReadOnly(prop, True)
      self.grid.SetSplitterLeft() 

  def SetProperty(self, name, value):
    self.changedConfig[name]=value

    setting=self.currentConfig[name]['setting']
    if name in self.changedConfig and self.changedConfig[name] != setting:
      icon=GetBitmap('settingChanged', self)
      setting="%s   (->%s)" % (setting, self.changedConfig[name])
    else:
      icon=GetBitmap('setting', self)
    self.grid.SetPropertyImage(name, icon)
    self.grid.SetPropertyValue(name, setting)

  def DoReload(self):
    lst=[]
    for name, value in self.changedConfig.items():
      if self.currentConfig[name]['setting'] != value:
        s="%s=%s" % (name, value)
        if s != InstrumentConfig.autoconfLine:
          lst.append(s)
    if lst:
      txt=xlt("The following settings have been changed:\n\n   %s\n\nApply?") % "\n  ".join(lst)
    else:
      txt=xlt("Apparently no changes to apply.\nReload server anyway?")
    dlg=wx.MessageDialog(self, txt, xlt("Reload server with new configuration"))
    if dlg.ShowModal() == wx.ID_OK:
      self.lastNode.GetCursor().ExecuteSingle("select pg_reload_conf()")
      node=self.lastNode
      self.lastNode=None
      self.Display(node, False)

  def OnFind(self, evt):
    self.OnSelChanging(None)
    self.grid.SetSelection([])
    name=self.Find
    if not name: return
    
    for prop in self.currentConfig.keys():
      if prop.find(name) >= 0:
        self.lastFindProperty=prop
        self.grid.SetPropertyBackgroundColour(prop, wx.SystemSettings_GetColour(wx.SYS_COLOUR_HIGHLIGHT))
        self.grid.SetPropertyTextColour(prop, wx.SystemSettings_GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT))
        self.grid.EnsureVisible(prop)
        self['Find'].SetForegroundColour(wx.BLACK)
        return
    self['Find'].SetForegroundColour(wx.RED)

    
  def OnApply(self, evt):
    self.DoReload()
    
  def OnItemDoubleClick(self, evt):
    property=evt.GetProperty()
    name=self.grid.GetPropertyLabel(property)
    cfg=self.currentConfig.get(name)
    if cfg:
      dlg=ServerSetting(self.lastNode, self, cfg)
      dlg.GoModal()


class InstrumentConfig:  
  @staticmethod
  def OnExecute(): # never executed
    pass
  
  @staticmethod
  def GetInstrumentQuery(server):
    if server.version >= 8.1 and server.version < 9.4:
      sql="""SELECT 'admin4.instrumentation', 'ok' FROM pg_settings WHERE name='custom_variable_classes' and setting='admin4'
             UNION
             SELECT 'postgresql.auto.conf', CASE WHEN 'postgresql.auto.conf' IN 
                   (SELECT pg_ls_dir(setting) FROM pg_settings where name='data_directory') THEN 'ok' ELSE '' END
             UNION
             SELECT 'adminpack', 'adminpack' FROM pg_proc
              WHERE proname='pg_file_write' AND pronamespace=11"""
      if server.version >= 9.1:
        sql += """UNION
              SELECT 'adminpack-extension', 'adminpack-extension'
                FROM pg_available_extensions
               WHERE name='adminpack'"""
             
      return sql

  @staticmethod
  def GetMissingInstrumentation(server):
    if server.version < 9.4:
      if server.version >= 9.1 and not server.GetValue('adminpack-extension'):
        return 'adminpack-extension'
      for name in ['adminpack', 'postgresql.auto.conf', 'admin4.instrumentation']:
        if not server.GetValue(name):
          return name
  
  autoconfLine="custom_variable_classes='admin4'"
  autoconfHeader="""
# Admin4 configuration additions
# do not edit!
%s
""" % autoconfLine
  @staticmethod
  def DoInstrument(server):
    if server.version >= 8.1 and server.version < 9.4:
      if not server.GetValue('adminpack'):
        if server.GetValue('adminpack-extension'):
          server.GetCursor().ExecuteSingle("CREATE EXTENSION adminpack")
        else:
          cursor=server.GetCursor()
          cursor.ExecuteSingle("""
                CREATE OR REPLACE FUNCTION pg_catalog.pg_file_write(text, text, bool)
                RETURNS bigint
                AS '$libdir/adminpack', 'pg_file_write'
                LANGUAGE C VOLATILE STRICT;
                
                CREATE OR REPLACE FUNCTION pg_catalog.pg_file_rename(text, text, text)
                RETURNS bool
                AS '$libdir/adminpack', 'pg_file_rename'
                LANGUAGE C VOLATILE;
                
                CREATE OR REPLACE FUNCTION pg_catalog.pg_file_unlink(text)
                RETURNS bool
                AS '$libdir/adminpack', 'pg_file_unlink'
                LANGUAGE C VOLATILE STRICT;
                """)
          
      if not server.GetValue('postgresql.auto.conf'):
        cursor=server.GetCursor()
        cursor.ExecuteSingle("SELECT pg_file_write('postgresql.auto.conf', %s, false)" % quoteValue(InstrumentConfig.autoconfHeader, cursor))

      if not server.GetValue('admin4.instrumentation'):
        dataDir=server.GetValue("data_directory")
        autoconfPath="%s/postgresql.auto.conf" % dataDir
        cursor=server.GetCursor()
        
        
        cfgFile=server.GetValue('config_file')
        if cfgFile.startswith(dataDir):
          cfgFile=cfgFile[len(dataDir)+1:]
          cfg=cursor.ExecuteSingle("SELECT pg_read_file('%s', 0, 999999)" % cfgFile)
                                   
          if not cfg.strip().endswith("include '%s'" % autoconfPath):
            cfg += "\n\n# Admin4 config file\ninclude '%s'\n" % autoconfPath
            cursor.ExecuteSingle("""
                SELECT pg_file_unlink('%(cfg)s.bak');
                SELECT pg_file_write('%(cfg)s.tmp', %(content)s, false);
                SELECT pg_file_rename('%(cfg)s.tmp', '%(cfg)s', '%(cfg)s.bak');
                SELECT pg_reload_conf();
                """ % {'cfg': cfgFile, 'content': quoteValue(cfg, cursor) } )
    return True



pageinfo = [StatisticsPage, ConnectionPage, LoggingPage, SettingsPage]
menuinfo=[{"class": InstrumentConfig } ]
