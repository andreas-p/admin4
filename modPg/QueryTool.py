# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.aui
import adm
import xmlres
from wh import xlt, GetBitmap, Menu, modPath, floatToTime, AcceleratorHelper, FileManager
from _explain import ExplainCanvas
from _snippet import SnippetTree
from _sqlgrid import SqlResultGrid
from _sqledit import SqlEditor


class SqlFrame(adm.Frame):
  STATUSPOS_MSGS=1
  STATUSPOS_POS=2
  STATUSPOS_ROWS=3
  STATUSPOS_SECS=4
  filePatterns=[(xlt("SQL files"), '*.sql'),
                (xlt("Text files"), '*.txt'),
                (xlt("All files"), '*.*')
                ]
  
  def __init__(self, _parentWin, node):
    style=wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX
    adm.Frame.__init__(self, None, xlt("Query Tool"), style, (600,400), None)
    self.SetIcon(wx.Icon(modPath("SqlQuery.ico", self)))

    self.server=node.GetServer()
    self.application="%s Query Tool" % adm.appTitle
    
    if hasattr(node, "GetDatabase"):
      dbName=node.GetDatabase().name
    else:
      dbName=self.server.maintDb
    self.worker=None
    self.sqlChanged=False
    self.previousCols=[]

    self.fileManager=FileManager(self, adm.config)

    self.toolbar=self.CreateToolBar(wx.TB_FLAT|wx.TB_NODIVIDER)
    self.toolbar.SetToolBitmapSize(wx.Size(16, 16));

    self.toolbar.DoAddTool(self.GetMenuId(self.OnFileOpen), xlt("Load from file"), GetBitmap("file_open", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnFileSave), xlt("Save to file"), GetBitmap("file_save", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnShowSnippets), xlt("Show snippets browser"), GetBitmap("snippets", self))
    self.toolbar.AddSeparator()
    self.toolbar.DoAddTool(self.GetMenuId(self.OnCopy), xlt("Copy"), GetBitmap("clip_copy", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnCut), xlt("Cut"), GetBitmap("clip_cut", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnPaste), xlt("Paste"), GetBitmap("clip_paste", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnClear), xlt("Clear"), GetBitmap("edit_clear", self))
    self.toolbar.AddSeparator()
    self.toolbar.DoAddTool(self.GetMenuId(self.OnUndo), xlt("Undo"), GetBitmap("edit_undo", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnRedo), xlt("Redo"), GetBitmap("edit_redo", self))
#    self.toolbar.DoAddTool(self.GetMenuId(self.OnFind), xlt("Find"), GetBitmap("edit_find", self))
    self.toolbar.AddSeparator()
    self.toolbar.DoAddTool(self.GetMenuId(self.OnAddSnippet), xlt("Add snippet"), GetBitmap("snippet_add", self))
    self.toolbar.DoAddTool(self.GetMenuId(self.OnReplaceSnippet), xlt("Replace snippet"), GetBitmap("snippet_replace", self))
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
    menu.AppendMenu(-1, xlt("Open recent..."), self.fileManager.GetRecentFilesMenu())
    self.AddMenu(menu, xlt("&Insert"), xlt("Insert query file"), self.OnFileInsert)
    self.AddMenu(menu, xlt("&Save"), xlt("Save current file"), self.OnFileSave)
    self.AddMenu(menu, xlt("Save &as.."), xlt("Save file under new name"), self.OnFileSaveAs)
    menu.AppendSeparator()
    self.AddMenu(menu, xlt("Show snippets"), xlt("Show snippet browser"), self.OnShowSnippets)
    
    menu.AppendSeparator()
#    self.AddMenu(menu, xlt("Preferences"), xlt("Preferences"), self.OnPreferences)
    self.AddMenu(menu, xlt("Quit SQL"), xlt("Quit Sql"), self.OnClose)

    menubar.Append(menu, xlt("&File"))

    self.editmenu=menu=Menu()
    self.AddMenu(menu, xlt("&Undo"), xlt("Undo last action"), self.OnUndo)
    self.AddMenu(menu, xlt("&Redo"), xlt("Redo last action"), self.OnRedo)
#    self.AddMenu(menu, xlt("&Find"), xlt("Find string"), self.OnFind)
    menu.AppendSeparator()
    self.AddMenu(menu, xlt("Cu&t"), xlt("Cut selected text to clipboard"), self.OnCut)
    self.AddMenu(menu, xlt("&Copy"), xlt("Copy selected text to clipboard"), self.OnCopy)
    self.AddMenu(menu, xlt("&Paste"), xlt("Paste text from clipboard"), self.OnPaste)
    self.AddMenu(menu, xlt("C&lear"), xlt("Clear editor"), self.OnClear)
    menu.AppendSeparator()
    self.AddMenu(menu, xlt("Add snippet"), xlt("Add selected text to snippets"), self.OnAddSnippet)
    self.AddMenu(menu, xlt("Modify snippet"), xlt("Replace snippet with selected text"), self.OnReplaceSnippet)
    menubar.Append(menu, xlt("&Edit"))
    
    self.querymenu=menu=Menu()
    self.AddMenu(menu, xlt("Execute"), xlt("Execute query"), self.OnExecuteQuery)
    self.AddMenu(menu, xlt("Explain"), xlt("Explain query"), self.OnExplainQuery)
    self.AddMenu(menu, xlt("Cancel"), xlt("Cancel query execution"), self.OnCancelQuery)
    menubar.Append(menu, xlt("&Query"))
    
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    self.SetMenuBar(menubar)
    
    ah=AcceleratorHelper(self)
    ah.Add(wx.ACCEL_CTRL, 'X', self.OnCut)
    ah.Add(wx.ACCEL_CTRL, 'C', self.OnCopy)
    ah.Add(wx.ACCEL_CTRL, 'V', self.OnPaste)
    ah.Add(wx.ACCEL_NORMAL,wx.WXK_F5, self.OnExecuteQuery)
    ah.Add(wx.ACCEL_NORMAL,wx.WXK_F7, self.OnExplainQuery)
    ah.Add(wx.ACCEL_ALT,wx.WXK_PAUSE, self.OnCancelQuery)
    ah.Realize()
 
    self.manager=wx.aui.AuiManager(self)
    self.manager.SetFlags(wx.aui.AUI_MGR_ALLOW_FLOATING|wx.aui.AUI_MGR_TRANSPARENT_HINT | \
         wx.aui.AUI_MGR_HINT_FADE| wx.aui.AUI_MGR_TRANSPARENT_DRAG)

    pt=self.GetFont().GetPointSize()
    font=wx.Font(pt, wx.TELETYPE, wx.NORMAL, wx.NORMAL)

    self.input=SqlEditor(self, font)
    self.input.SetFont(font)
    self.input.SetAcceleratorTable(ah.GetTable())
    self.input.SetKeywords(' '.join(self.server.keywords))
    
    self.input.BindProcs(self.OnChangeStc, self.OnStatusPos)
    self.manager.AddPane(self.input, wx.aui.AuiPaneInfo().Top().PaneBorder().Resizable().MinSize((200,100)).BestSize((400,200)).CloseButton(False) \
                          .Name("sqlQuery").Caption(xlt("SQL Query")))
    
    
    self.snippets=SnippetTree(self, self.server, self.input)
    self.manager.AddPane(self.snippets, wx.aui.AuiPaneInfo().Left().Top().PaneBorder().Resizable().MinSize((100,100)).BestSize((100,100)).CloseButton(True) \
                          .Name("snippets").Caption(xlt("SQL Snippets")))

    
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
    self.SetStatus(xlt("ready"))
    
    str=adm.config.GetPerspective(self)
    #str=None
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
    adm.config.storeWindowPositions(self)
    self.Destroy()
      
    
  def OnChangeDatabase(self, evt=None):
    i=self.databases.GetSelection()
    if i >= 0:
      dbName=self.databases.GetString(i)
      self.conn = self.databases.GetClientData(i)
      if not self.conn:
        self.conn = self.server.DoConnect(dbName, application=self.application)
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
    
    a,e=self.input.GetSelection()
    canQuery = ( a!=e or self.input.GetLineCount() >1 or self.getSql() )


    self.EnableMenu(self.editmenu, self.OnAddSnippet, self.server.GetValue('snippet_table'))
    self.EnableMenu(self.editmenu, self.OnReplaceSnippet, self.snippets.CanReplace())
    self.EnableMenu(self.editmenu, self.OnCut, canCut)
    self.EnableMenu(self.editmenu, self.OnPaste, canPaste)
    self.EnableMenu(self.editmenu, self.OnUndo, canUndo)
    self.EnableMenu(self.editmenu, self.OnRedo, canRedo)
    self.EnableMenu(self.editmenu, self.OnClear, canQuery)
#    self.EnableMenu(self.editmenu, self.OnFind, canQuery)
    
    self.EnableMenu(self.filemenu, self.OnFileSave, self.sqlChanged)
    
    self.EnableMenu(self.querymenu, self.OnExecuteQuery, canQuery)
    self.EnableMenu(self.querymenu, self.OnExplainQuery, canQuery)
    
    
  def executeSql(self, targetPage, sql, _queryOffset=0, resultToMsg=False):
    self.EnableMenu(self.querymenu, self.OnCancelQuery, True)
    self.EnableMenu(self.querymenu, self.OnExecuteQuery, False)
    self.EnableMenu(self.querymenu, self.OnExplainQuery, False)
    
    self.worker=worker=self.conn.ExecuteAsync(sql)
    rowcount=0
    rowset=None
    worker.start()
    
    self.SetStatus(xlt("Query is running."));
    self.SetStatusText("", self.STATUSPOS_SECS);
    self.SetStatusText("", self.STATUSPOS_ROWS);     
    self.msgHistory.AppendText(xlt("-- Executing query:\n"));
    self.msgHistory.AppendText(sql);
    self.msgHistory.AppendText("\n");
    self.input.MarkerDelete()   
    self.messages.Clear()
    
    startTime=wx.GetLocalTimeMillis();
    
    while worker.IsRunning():
      elapsed=wx.GetLocalTimeMillis() - startTime
      self.SetStatusText(floatToTime(elapsed/1000.), self.STATUSPOS_SECS)
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
    self.SetStatusText(txt, self.STATUSPOS_SECS)
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    self.EnableMenu(self.querymenu, self.OnExecuteQuery, True)
    self.EnableMenu(self.querymenu, self.OnExplainQuery, True)

    if worker.error:
      errmsg=worker.error.error.decode('utf8')
      errlines=errmsg.splitlines()

      self.messages.SetValue(errmsg)
      self.msgHistory.AppendText(errmsg)
      for i in range(1, len(errlines)):
        if errlines[i].startswith("LINE "):
          lineinfo=errlines[i].split(':')[0][5:]
          colinfo=errlines[i+1].find('^')
          dummy=colinfo
          self.input.MarkerSet(int(lineinfo)-1 + self.input.GetSelectOffset())
          break

    if worker.cancelled:
      self.SetStatus(xlt("Cancelled."));
    elif worker.error:
      self.SetStatus(errlines[0]);
    else:
      self.SetStatus(xlt("OK."));
      
      rowcount=worker.GetRowcount()
      rowset=worker.GetResult()


    if worker.error:
      self.SetStatusText("", self.STATUSPOS_ROWS)
    else:
      if rowcount == 1:
        rowsMsg=xlt("1 row affected")
      elif rowcount < 0:
        rowsMsg=xlt("Executed")
      else:
        rowsMsg= xlt("%d rows affected") % rowcount
      self.SetStatusText(rowsMsg, self.STATUSPOS_ROWS)
      self.msgHistory.AppendText("-- %s\n" % rowsMsg)
    
      
    self.msgHistory.AppendText("\n")
    currentPage=self.output.GetPage(0)
    if currentPage != targetPage:
      self.output.RemovePage(0)
      currentPage.Hide()
      targetPage.Show()
      self.output.InsertPage(0, targetPage, xlt("Data output"), True)

    if rowset:
      self.output.SetSelection(0)
      targetPage.SetData(rowset)
    else:
      self.output.SetSelection(1)
      targetPage.SetEmpty()

    for notice in self.conn.conn.notices:
      self.messages.AppendText(notice);
      self.messages.AppendText("\n")

    if not worker.error:
      if resultToMsg:
        self.messages.SetValue("\n".join(targetPage.GetResult()))
      else:
        self.messages.SetValue(rowsMsg)

    self.input.SetFocus()


  def SetStatus(self, status):
    self.SetStatusText(status, self.STATUSPOS_MSGS)
  
  def getSql(self):  
    sql=self.input.GetSelectedText()
    if not sql:
      sql=self.input.GetText()
    return sql.strip()
  
  
  def OnShowSnippets(self, evt):
    self.manager.GetPane("snippets").Show(True)
    self.manager.Update()    
  
  def OnAddSnippet(self, evt):
    sql=self.getSql()
    if sql:
      dlg=wx.TextEntryDialog(self, xlt("Snippet name"), xlt("Add snippet"))
      if dlg.ShowModal() == wx.ID_OK:
        name=dlg.GetValue()
        self.snippets.AppendSnippet(name, sql)
        self.SetStatus(xlt("Snipped stored."))
    
  def OnReplaceSnippet(self, evt):
    sql=self.getSql()
    if sql:
      self.snippets.ReplaceSnippet(sql)


  def OnCancelQuery(self, evt):
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    if self.worker:
      self.worker.Cancel()

  def OnExecuteQuery(self, evt):
    sql=self.getSql()
    if not sql.strip():
      return
    self.executeSql(self.result, sql)

  def OnExplainQuery(self, evt):
    sql=self.getSql()
    if not sql:
      return
    self.executeSql(self.explain, "EXPLAIN %s" % sql, 8, True)

  
  def readFile(self, message, filename=None):
    if not filename:
      filename=self.fileManager.OpenFile(self, self.filePatterns, message)
    if filename:
      try:
        f=open(filename, 'r')
        sql=f.read()
        f.close()
        return sql
      except:
        self.SetStatus(xlt("Failed to read %s") % filename)
        return None
        
  def fileOpen(self, header, filename=None):
    sql=self.readFile(header, filename)
    if sql:
      self.input.ClearAll()
      self.input.ReplaceSelection(sql)
      self.SetStatus(xlt("%d characters read from %s") % (len(sql), self.fileManager.currentFile))
      self.updateMenu()

  def OnRecentFileOpened(self, filename):
    self.fileOpen(None, filename)
    
  def OnFileOpen(self, evt):
    self.fileOpen(xlt("Open SQL file"))
      
  
  def OnFileInsert(self, evt):
    sql=self.readFile(xlt("Insert SQL from file"))
    if sql:
      self.input.ReplaceSelection(sql)
      self.SetStatus(xlt("%d characters inserted from %s") % (len(sql), self.fileManager.currentFile))
      self.updateMenu()
  
  
  def saveFile(self, proc):    
    try:
      ok=proc(self, self.input.GetText(), self.filePatterns, xlt("Save SQL Query"))
      if ok:
        self.SetStatus(xlt("Saved SQL query to %s") % self.fileManager.filename)
        self.sqlChanged=False
        self.updateMenu() 
      else:
        self.StatusText(xlt("Nothing saved"))
    except:
      self.SetStatus(xlt("Failed to save to %s") % self.fileManager.filename)
      
  def OnFileSave(self, evt):
    self.saveFile(self.fileManager.SaveFile)
    
  def OnFileSaveAs(self, evt):
    self.saveFile(self.fileManager.SaveFileAs)
  
  
  def OnUndo(self, evt):
    self.input.Undo()
  
  def OnClear(self, evt):
    self.input.ClearAll()
    self.updateMenu()
    
  def OnFind(self, evt):
    pass
  
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
    self.SetStatusText(xlt("Ln %d Col %d") % (row, col), self.STATUSPOS_POS)
    
    
    
############################################################
# node menu

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

    