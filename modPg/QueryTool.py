# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.aui, wx.stc, wx.grid
import adm
import xmlres
from wh import xlt, GetBitmap, Menu, modPath, floatToTime, AcceleratorHelper
from _explain import ExplainCanvas


NULLSTRING="(NULL)"

STATUSPOS_MSGS=1
STATUSPOS_POS=2
STATUSPOS_ROWS=3
STATUSPOS_SECS=4

class SqlEditor:
  pass


class SqlResultGrid(wx.grid.Grid):
  HMARGIN=5
  VMARGIN=5
  
  def __init__(self, parent):
    wx.grid.Grid.__init__(self, parent)
    self.CreateGrid(0,0)
    self.SetColLabelSize(0)
    self.SetRowLabelSize(0)
    self.AutoSize()
    
  def SetEmpty(self):
    self.SetTable(wx.grid.GridStringTable(0,0))
    self.SetColLabelSize(0)
    self.SetRowLabelSize(0)
    self.SendSizeEventToParent()

  
  def SetData(self, rowset):
    rowcount=rowset.GetRowcount()
    colcount=len(rowset.colNames)
    
    self.SetTable(wx.grid.GridStringTable(rowcount, colcount))
    w,h=self.GetTextExtent('Colname')
    self.SetColLabelSize(h+self.HMARGIN)
    self.SetRowLabelSize(w+self.VMARGIN)
    self.SetDefaultRowSize(h+self.HMARGIN)
    
    self.previousCols=rowset.colNames
    self.Freeze()
    self.BeginBatch()
    for x in range(colcount):
      colname=rowset.colNames[x]
      if colname == '?column?':
        colname="Col #%d" % (x+1)
      self.SetColLabelValue(x, colname)
    y=0  
    for row in rowset:
      self.SetRowLabelValue(y, "%d" % (y+1))
      for x in range(colcount):
        val=row[x]
        if val == None:
          val=NULLSTRING
        else:
          val=str(val)
        self.SetCellValue(y, x, val)
        self.SetReadOnly(y,x) 
      y = y+1
    self.EndBatch()
    self.AutoSizeColumns()
    self.Thaw()
    self.SendSizeEventToParent()
    
  def Paste(self):
    pass
  
  def Cut(self):
    self.Copy()
  
  def Copy(self):
    vals=self.getCells()
    if vals:
      wx.TheClipboard.Open()
      wx.TheClipboard.SetData(wx.TextDataObject(vals))
      wx.TheClipboard.Close()

  def getCells(self, quoteChar="'", commaChar=', ', lfChar='\n', null='NULL'):
    def quoted(v):
      if v == NULLSTRING:
        return null
      try:
        _=float(v)
        return v
      except:
        return "%s%s%s" % (quoteChar, v, quoteChar) 
    
    vals=[]
    cells=self.GetSelectedCells()
    if cells:
      for row,col in cells:
        vals.append(quoted(self.GetCellValue(row, col)))
        return commaChar.join(vals)
    else:
      rows=self.GetSelectedRows()
      if rows:
        cols=range(self.GetTable().GetColsCount())
      else:
        cols=self.GetSelectedCols()
        if cols:
          rows=range(self.GetTable().GetRowsCount())
        else:
          return None
      for row in rows:
        v=[]
        for col in cols:
          v.append(quoted(self.GetCellValue(row, col)))
        vals.append(commaChar.join(v))
      return lfChar.join(vals)
    
    
class ExplainText(wx.TextCtrl):
  def __init__(self, parent):
    wx.TextCtrl.__init__(self, parent, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP)
  
  def SetData(self, rowset):
    lst=[]
    for row in rowset:
      lst.append(str(row[0]))
    self.SetValue("\n".join(lst))
  
  def SetEmpty(self):
    self.SetValue("")
    
class SqlFrame(adm.Frame):
  def __init__(self, _parentWin, node):
    style=wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX
    adm.Frame.__init__(self, None, xlt("Query Tool"), style, (600,400), None)
    self.SetIcon(wx.Icon(modPath("SqlQuery.ico", self)))

    self.server=node.GetServer()
    self.application="Admin4 Query Tool"
    
    if hasattr(node, "GetDatabase"):
      dbName=node.GetDatabase().name
    else:
      dbName=self.server.maintDb
    self.worker=None
    self.sqlChanged=False
    self.previousCols=[]


    self.toolbar=self.CreateToolBar(wx.TB_FLAT|wx.TB_NODIVIDER)
    self.toolbar.SetToolBitmapSize(wx.Size(16, 16));

    self.toolbar.DoAddTool(self.GetMenuId(self.OnFileOpen), xlt("Load from file"), GetBitmap("file_open", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnFileSave), xlt("Save to file"), GetBitmap("file_save", self))
    self.toolbar.AddSeparator()
    self.toolbar.DoAddTool(self.GetMenuId(self.OnUndo), xlt("Undo"), GetBitmap("edit_undo", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnRedo), xlt("Redo"), GetBitmap("edit_redo", self))
    self.toolbar.AddSeparator()
    
    cbClass=xmlres.getControlClass("whComboBox")
    allDbs=self.server.GetConnectableDbs()
    size=max(map(lambda db: self.toolbar.GetTextExtent(db)[0], allDbs))
    
    BUTTONOFFS=30
    self.databases=cbClass(self.toolbar, size=(size+BUTTONOFFS, -1))
    self.databases.Append(allDbs)

    self.databases.SetStringSelection(dbName)
    self.OnChangeDatabase()
    self.databases.Bind(wx.EVT_COMBOBOX, self.OnChangeDatabase)
    self.toolbar.AddControl(self.databases)
    self.toolbar.DoAddTool(self.GetMenuId(self.OnExecuteQuery), xlt("Execute Query"), GetBitmap("query_execute", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnExplainQuery), xlt("Explain Query"), GetBitmap("query_explain", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnCancelQuery), xlt("Execute Query"), GetBitmap("query_cancel", self))
    self.toolbar.Realize()


    menubar=wx.MenuBar()

    self.filemenu=menu=Menu()

    self.AddMenu(menu, xlt("&Open"), xlt("Open query file"), self.OnFileOpen)
    self.AddMenu(menu, xlt("&Save"), xlt("Save current file"), self.OnFileSave)
    self.AddMenu(menu, xlt("Save &as.."), xlt("Save file under new name"), self.OnFileSaveAs)
    
    if wx.Platform != "__WXMAC__":
      menu.AppendSeparator()
    #self.AddMenu(menu, xlt("Preferences"), xlt("Preferences"), self.OnPreferences, wx.ID_PREFERENCES, adm.app.SetMacPreferencesMenuItemId)
    #self.AddMenu(menu, xlt("Quit"), xlt("Quit Admin3"), self.OnQuit, wx.ID_EXIT, adm.app.SetMacExitMenuItemId)

    menubar.Append(menu, xlt("&File"))

    self.editmenu=menu=Menu()
    self.AddMenu(menu, xlt("&Undo"), xlt("Undo last action"), self.OnUndo)
    self.AddMenu(menu, xlt("&Redo"), xlt("Redo last action"), self.OnRedo)
    menu.AppendSeparator()
    self.AddMenu(menu, xlt("Cu&t"), xlt("Cut selected text to clipboard"), self.OnCut)
    self.AddMenu(menu, xlt("&Copy"), xlt("Copy selected text to clipboard"), self.OnCopy)
    self.AddMenu(menu, xlt("&Paste"), xlt("Paste text from clipboard"), self.OnPaste)
    menubar.Append(menu, xlt("&Edit"))
    
    self.querymenu=menu=Menu()
    self.AddMenu(menu, xlt("Execute"), xlt("Execute query"), self.OnExecuteQuery)
    self.AddMenu(menu, xlt("Explain"), xlt("Explain query"), self.OnExplainQuery)
    self.AddMenu(menu, xlt("Cancel"), xlt("Cancel query execution"), self.OnCancelQuery)
    menubar.Append(menu, xlt("&Query"))
    
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    
    ah=AcceleratorHelper(self)
    if wx.Platform == "__WXMAC__":
      ctl=wx.ACCEL_CMD
    else:
      ctl=wx.ACCEL_CTRL
    ah.Add(ctl, ord('X'), self.OnCut)
    ah.Add(ctl, ord('C'), self.OnCopy)
    ah.Add(ctl, ord('V'), self.OnPaste)
    ah.Add(wx.ACCEL_NORMAL,wx.WXK_F5, self.OnExecuteQuery)
    ah.Add(wx.ACCEL_NORMAL,wx.WXK_F7, self.OnExplainQuery)
    ah.Add(wx.ACCEL_ALT,wx.WXK_PAUSE, self.OnCancelQuery)
    ah.Realize()
    
    self.manager=wx.aui.AuiManager(self)
    self.manager.SetFlags(wx.aui.AUI_MGR_ALLOW_FLOATING|wx.aui.AUI_MGR_TRANSPARENT_HINT | \
         wx.aui.AUI_MGR_HINT_FADE| wx.aui.AUI_MGR_TRANSPARENT_DRAG)

    pt=self.GetFont().GetPointSize()
    font=wx.Font(pt, wx.TELETYPE, wx.NORMAL, wx.NORMAL)

    self.input=wx.stc.StyledTextCtrl(self)
    self.input.StyleSetFont(0, font)
    self.input.MarkerDefineBitmap(0, GetBitmap("badline", self))
    self.input.SetAcceleratorTable(ah.GetTable())
    self.input.Bind(wx.stc.EVT_STC_UPDATEUI, self.OnStatusPos)
    self.input.Bind(wx.stc.EVT_STC_CHANGE, self.OnChangeStc)
    self.manager.AddPane(self.input, wx.aui.AuiPaneInfo().Top().PaneBorder().Resizable().MinSize((200,100)).BestSize((400,200)).CloseButton(False) \
                          .Name("sqlQuery").Caption(xlt("Sql Query")))
    
    
    self.output=wx.Notebook(self)
    self.result=SqlResultGrid(self.output)
    self.explain = ExplainCanvas(self.output)
    self.explain.Hide()
    
    self.messages=wx.TextCtrl(self.output, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP)
    self.msgHistory=wx.TextCtrl(self.output, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP)
    self.messages.SetFont(font)
    self.msgHistory.SetFont(font)

    self.output.AddPage(self.result, xlt("Output"))
    self.output.AddPage(self.messages, xlt("Messages"))
    self.output.AddPage(self.msgHistory, xlt("History"))
        
    self.manager.AddPane(self.output, wx.aui.AuiPaneInfo().Center().MinSize((200,100)).BestSize((400,200)).CloseButton(False) \
                          .Name("Result").Caption(xlt("Result")).CaptionVisible(False))

    self.CreateStatusBar(5, wx.ST_SIZEGRIP)
    w,_h=self.StatusBar.GetTextExtent('Mg')
    self.SetStatusWidths([0, -1, 5*w,6*w,5*w])
    self.SetStatusText(xlt("ready"), STATUSPOS_MSGS)
    
    str=adm.config.GetPerspective(self)
    str=None
    if str:
      self.manager.LoadPerspective(str)

    self.Bind(wx.EVT_CLOSE, self.OnClose)
    self.manager.Update()
    self.updateMenu()

  
  def SetTitle(self, dbName):
    title=xlt("PostGreSQL Query Tool - Database \"%(dbname)s\" on Server \"%(server)s\""  % { 'dbname': dbName, 'server': self.server.name})
    adm.Frame.SetTitle(self, title)


  def OnClose(self, evt):
    for i in range(self.databases.GetCount()):
      conn=self.databases.GetClientData(i)
      if conn:
        conn.disconnect()
    self.Destroy()
      
    
  def OnChangeDatabase(self, evt=None):
    i=self.databases.GetSelection()
    if i >= 0:
      dbName=self.databases.GetString(i)
      self.conn = self.databases.GetClientData(i)
      if not self.conn:
        self.conn = self.server.DoConnect(dbName, True, application=self.application)
        self.databases.SetClientData(i, self.conn)
      self.SetTitle(dbName)
        

  def updateMenu(self, ctl=None):
    if not self.GetToolBar():
      return
    canCut=canPaste=canUndo=canRedo=False
    if not ctl or ctl == self.input:
      canUndo=self.input.CanUndo();
      canRedo=self.input.CanRedo();
      canPaste=self.input.CanPaste();
      canCut = True;
    self.EnableMenu(self.editmenu, self.OnCut, canCut)
    self.EnableMenu(self.editmenu, self.OnPaste, canPaste)
    self.EnableMenu(self.editmenu, self.OnUndo, canUndo)
    self.EnableMenu(self.editmenu, self.OnRedo, canRedo)
    
    
  def executeSql(self, target, sql, _queryOffset=0, resultToMsg=False):
    self.EnableMenu(self.querymenu, self.OnCancelQuery, True)
    self.EnableMenu(self.querymenu, self.OnExecuteQuery, False)
    self.EnableMenu(self.querymenu, self.OnExplainQuery, False)
    
    self.worker=worker=self.conn.ExecuteAsync(sql)
    rowcount=0
    rowset=None
    worker.start()
    
    self.SetStatusText("", STATUSPOS_SECS);
    self.SetStatusText(xlt("Query is running."), STATUSPOS_MSGS);
    self.SetStatusText("", STATUSPOS_ROWS);     
    self.msgHistory.AppendText(xlt("-- Executing query:\n"));
    self.msgHistory.AppendText(sql);
    self.msgHistory.AppendText("\n");
    self.input.MarkerDeleteAll(0)    
    self.messages.Clear()
    
    startTime=wx.GetLocalTimeMillis();
    
    while worker.IsRunning():
      elapsed=wx.GetLocalTimeMillis() - startTime
      self.SetStatusText(floatToTime(elapsed/1000.), STATUSPOS_SECS)
      wx.Yield()
      if elapsed < 200:
        wx.MilliSleep(10);
      elif elapsed < 10000:
        wx.MilliSleep(100);
      else:
        wx.MilliSleep(500)
      wx.Yield()
    
    self.worker=None
    elapsed=wx.GetLocalTimeMillis() - startTime
    if elapsed:
      txt=floatToTime(elapsed/1000.)
    else:
      txt="0 ms"
    self.SetStatusText(txt, STATUSPOS_SECS)
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    self.EnableMenu(self.querymenu, self.OnExecuteQuery, True)
    self.EnableMenu(self.querymenu, self.OnExplainQuery, True)

    errmsg=str(worker.error)
    errlines=errmsg.splitlines()

    if worker.cancelled:
      self.SetStatusText(xlt("Cancelled."), STATUSPOS_MSGS);
    elif worker.error:
      self.SetStatusText(errlines[0], STATUSPOS_MSGS);
    else:
      self.SetStatusText(xlt("OK."), STATUSPOS_MSGS);
      
      rowset=worker.GetResult(autocommit=False)
      rowcount=rowset.GetRowcount()


    if rowcount == 1:
      rowsMsg=xlt("1 row affected")
    elif rowcount < 0:
      rowsMsg=xlt("Executed")
    else:
      rowsMsg= xlt("%d rows affected") % rowcount
    self.SetStatusText(rowsMsg, STATUSPOS_ROWS)
    self.msgHistory.AppendText("-- %s\n" % rowsMsg)
    
    if worker.error:
      self.messages.SetValue(errmsg)
      self.msgHistory.AppendText(errmsg)
      for i in range(1, len(errlines)-2):
        if errlines[i].startswith("LINE "):
          lineinfo=errlines[i].split(':')[0][5:]
          colinfo=errlines[i+1].find('^')
          dummy=colinfo
          self.input.MarkerAdd(0, int(lineinfo))
          break
        
      
    self.msgHistory.AppendText("\n")
    currentPage=self.output.GetPage(0)
    if currentPage != target:
      self.output.RemovePage(0)
      currentPage.Hide()
      target.Show()
      self.output.InsertPage(0, target, xlt("Data output"), True)


    if rowcount>0:
      target.SetData(rowset)
    else:
      target.SetEmpty()

    for notice in self.conn.conn.notices:
      self.messages.AppendText(notice);
      self.messages.AppendText("\n")

    if worker.error:
      self.conn.Rollback()
      self.output.SetSelection(1)
    else:
      self.conn.Commit()
      if resultToMsg:
        self.messages.SetValue("\n".join(target.GetResult()))
      else:
        self.messages.SetValue(rowsMsg)
      self.output.SetSelection(0)
    self.input.SetFocus()


  
  def OnCancelQuery(self, evt):
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    if self.worker:
      self.worker.Cancel()

  def getSql(self):  
    sql=self.input.GetSelectedText()
    if not sql:
      sql=self.input.GetText()
    return sql
  
  
  def OnExecuteQuery(self, evt):
    sql=self.getSql()
    if not sql:
      return
    self.executeSql(self.result, sql)

  def OnExplainQuery(self, evt):
    sql=self.getSql()
    if not sql:
      return
    self.executeSql(self.explain, "EXPLAIN %s" % sql, 8, True)

  
  def OnFileOpen(self, evt):
    pass
  
  def OnFileSave(self, evt):
    pass
  
  def OnFileSaveAs(self, evt):
    pass
  
  def OnUndo(self, evt):
    self.input.Undo()
  
  def OnRedo(self, evt):
    self.input.Redo()
  
  def OnCut(self, evt):
    wnd=wx.Window.FindFocus()
    if wnd:
      wnd.Cut()
  
  def OnCopy(self, evt):
    wnd=wx.Window.FindFocus()
    if wnd:
      wnd.Copy()
  
  def OnPaste(self, evt):
    wnd=wx.Window.FindFocus()
    if wnd:
      wnd.Paste()
  
  def OnChangeStc(self, evt):
    self.sqlChanged=True
    self.updateMenu()
    
  def OnStatusPos(self, evt):

    row=self.input.LineFromPosition(self.input.GetCurrentPos())+1
    col=self.input.GetColumn(self.input.GetCurrentPos())+1
    self.SetStatusText(xlt("Ln %d Col %d") % (row, col), STATUSPOS_POS)
    
    
class QueryTool:
  name=xlt("Query Tool")
  help=xlt("Execute SQL Queries")
  toolbitmap='SqlQuery'
  
  @staticmethod
  def CheckAvailableOn(_node):
    return True
  
  @staticmethod
  def CheckEnabled(_node):
    return True

  @staticmethod
  def OnExecute(parentWin, node):
    frame=SqlFrame(parentWin, node)
    frame.Show()
    return None

nodeinfo=[]
menuinfo=[ {"class": QueryTool, "sort": 30 }, ]

    