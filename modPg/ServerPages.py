# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import wx
import wx.propgrid as wxpg
from page import ControlledPage
from wh import xlt, floatToTime, floatToSize, sizeToFloat, timeToFloat, breakLines, GetBitmap
from _pgsql import quoteValue
from Validator import Validator
from LoggingDialog import LogPanel
import logger


  
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

    if node.version < 9.2:
      pidCol="procpid"
    else:
      pidCol="pid"
    rowset=node.GetCursor().ExecuteSet("""
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

    self.Name=name
    self.Category=self.vals['category']
    context=self.vals['context']
    self.Context="%s - %s" % (context, ServerSetting.contextDesc.get(context))
    self.short_desc=breakLines(self.vals['short_desc'], 40)
    self.extra_desc=breakLines(self.vals['extra_desc'], 40)
    
    if name in self.page.changedConfig:
      self.SetVal(self.page.changedConfig[name])
    else:
      self.SetVal(self.vals['setting'])
    if context == 'internal':
      self.EnableControls("VALUE OK Reset Reload", False)

  
  def OnReset(self, evt):
    self.SetVal(self.vals['reset_val'])
    self.OnCheck(evt)

  
  def Check(self):
    ok=True
    minVal=self.vals['min_val']
    self.CheckValid(ok, minVal==None or self.value.GetValue() >=minVal, xlt("Must be %s or more") % minVal)
    maxVal=self.vals['max_val']
    self.CheckValid(ok, maxVal==None or self.value.GetValue() <=maxVal, xlt("Must be %s or less") % maxVal)
    
    return ok

  def Save(self):
    name=self.vals['name']
    val=self.GetVal()
    cursor=self.server.GetCursor()
    self.SetStatus(xlt("Setting value..."))
    cursor.ExecuteSingle("ALTER SYSTEM SET %s=%s" % (name, quoteValue(val, cursor)))
    self.page.SetProperty(name, val)

    if self.Reload:
      self.page.DoReload()
    return True  
  

class SettingsPage(adm.NotebookPanel, ControlledPage):
  name=xlt("Settings")
#  menus=[AlterConfigValue]
  availableOn="Server"
  order=850

  def __init__(self, notebook):
    adm.NotebookPanel.__init__(self, notebook, notebook)
    self.lastNode=None

  def AddExtraControls(self, res):
    self.grid=wxpg.PropertyGrid(self)
    res.AttachUnknownControl("ValueGrid", self.grid)
    self.grid.Bind(wxpg.EVT_PG_DOUBLE_CLICK, self.OnItemDoubleClick)
    self.Bind('Apply', self.OnApply)
    self.Bind('Find', self.OnFind)
    self.grid.Bind(wx.EVT_MOTION, self.OnMouseMove)
    
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
      if node.version >= 9.4:
        try:
          cursor=node.GetCursor()
          cursor.SetThrowSqlException(False)
          confFile=cursor.ExecuteSingle("SELECT pg_read_file('postgresql.auto.conf')")
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
      
      # TODO read preferences
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
        lst.append("%s=%s" % (name, value))
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
    name=self.Find
    if not name: return
    
    for prop in self.currentConfig.keys():
      if prop.find(name) >= 0:
        self.grid.SelectProperty(prop)
        self['Find'].SetForegroundColour(wx.BLACK)
        return
    self['Find'].SetForegroundColour(wx.RED)

    
  def OnApply(self, evt):
    self.DoReload()
    
  def OnItemDoubleClick(self, evt):
    if self.lastNode.version >= 9.4:
      property=evt.GetProperty()
      name=self.grid.GetPropertyLabel(property)
      cfg=self.currentConfig.get(name)
      if cfg:
        dlg=ServerSetting(self.lastNode, self, cfg)
        dlg.GoModal()
    
pageinfo = [StatisticsPage, ConnectionPage, SettingsPage]
  
