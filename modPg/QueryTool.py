# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.aui
import adm
import xmlres
import wx.grid
from wh import xlt, Menu, AcceleratorHelper, FileManager
from _pgsql import pgConnection
from _explain import ExplainCanvas
from _snippet import SnippetTree
from _sqlgrid import SqlFrame, HMARGIN, VMARGIN
from _sqledit import SqlEditor


NULLSTRING="(NULL)"


class SqlResultGrid(wx.grid.Grid):
  def __init__(self, parent):
    wx.grid.Grid.__init__(self, parent)
    self.CreateGrid(0,0)
    self.SetColLabelSize(0)
    self.SetRowLabelSize(0)
    pt=parent.GetFont().GetPointSize()
    if wx.Platform != "__WXMSW__":
      pt *= 0.95  # a little smaller
    font=wx.Font(pt, wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.NORMAL)
    self.SetDefaultCellFont(font)
    self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnChangeColSize)
    self.AutoSize()

  def OnChangeColSize(self, evt):
    adm.config.storeGridPositions(self)

    
  def SetEmpty(self):
    self.SetTable(wx.grid.GridStringTable(0,0))
    self.SetColLabelSize(0)
    self.SetRowLabelSize(0)
    self.SendSizeEventToParent()

  
  def SetData(self, rowset):
    rowcount=rowset.GetRowcount()
    colcount=len(rowset.colNames)
    
    if rowcount<0:
      rowcount=0
    self.SetTable(wx.grid.GridStringTable(rowcount, colcount))
    w,h=self.GetTextExtent('Colname')
    self.SetColLabelSize(h+HMARGIN)
    self.SetRowLabelSize(w+VMARGIN)
    self.SetDefaultRowSize(h+HMARGIN)
    
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
          val=unicode(val)
        self.SetCellValue(y, x, val)
        self.SetReadOnly(y,x) 
      y = y+1
    self.EndBatch()
    self.AutoSizeColumns(False)
    
    adm.config.restoreGridPositions(self)
    adm.config.storeGridPositions(self)
    self.Thaw()
    self.SendSizeEventToParent()
    
  def Paste(self):
    pass
  
  def Cut(self):
    self.Copy()
  
  def Copy(self):
    vals=self.getCells()
    if vals:
      adm.SetClipboard(vals)


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
          return quoted(self.GetCellValue(self.GetGridCursorRow(), self.GetGridCursorCol()))
      for row in rows:
        v=[]
        for col in cols:
          v.append(quoted(self.GetCellValue(row, col)))
        vals.append(commaChar.join(v))
      return lfChar.join(vals)


class QueryFrame(SqlFrame):
  def __init__(self, parentWin, node):
    SqlFrame.__init__(self, parentWin, xlt("Query Tool"), "SqlQuery")

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

    toolbar=self.toolbar
    toolbar.Add(self.OnFileOpen, xlt("Load from file"),"file_open")
    toolbar.Add(self.OnFileSave, xlt("Save to file"), "file_save")
    toolbar.Add(self.OnToggleSnippets, xlt("Show snippets browser"), "snippets")
    
    toolbar.AddSeparator()
    toolbar.Add(self.OnCopy, xlt("Copy"), "clip_copy")
    toolbar.Add(self.OnCut, xlt("Cut"), "clip_cut")
    toolbar.Add(self.OnPaste, xlt("Paste"), "clip_paste")
    toolbar.Add(self.OnClear, xlt("Clear"), "edit_clear")
    toolbar.AddSeparator()
    toolbar.Add(self.OnUndo, xlt("Undo"), "edit_undo")
    toolbar.Add(self.OnRedo, xlt("Redo"), "edit_redo")
#    toolbar.Add((self.OnFind, xlt("Find"), "edit_find")
    toolbar.AddSeparator()
    
    cbClass=xmlres.getControlClass("whComboBox")
    allDbs=self.server.GetConnectableDbs()
    size=max(map(lambda db: toolbar.GetTextExtent(db)[0], allDbs))
    
    BUTTONOFFS=30
    self.databases=cbClass(toolbar, size=(size+BUTTONOFFS, -1))
    self.databases.Append(allDbs)

    self.databases.SetStringSelection(dbName)
    self.OnChangeDatabase()
    self.databases.Bind(wx.EVT_COMBOBOX, self.OnChangeDatabase)

    toolbar.Add(self.OnExecuteQuery, xlt("Execute Query"), "query_execute")
    toolbar.Add(self.OnExplainQuery, xlt("Explain Query"), "query_explain")
    toolbar.Add(self.OnCancelQuery, xlt("Execute Query"), "query_cancel")
    toolbar.AddControl(self.databases)
    toolbar.AddSeparator()
    toolbar.Add(self.OnAddSnippet, xlt("Add snippet"), "snippet_add")
    toolbar.Add(self.OnReplaceSnippet, xlt("Replace snippet"), "snippet_replace")
    toolbar.Realize()

    menubar=wx.MenuBar()
    self.filemenu=menu=Menu(self)

    menu.Add(self.OnFileOpen, xlt("&Open"), xlt("Open query file"))
    menu.AppendMenu(-1, xlt("Open recent..."), self.fileManager.GetRecentFilesMenu())
    menu.Add(self.OnFileInsert, xlt("&Insert"), xlt("Insert query file"))
    menu.Add(self.OnFileSave, xlt("&Save"), xlt("Save current file"))
    menu.Add(self.OnFileSaveAs, xlt("Save &as.."), xlt("Save file under new name"))
    menu.AppendSeparator()
    
#    menu.Add(xlt("Preferences"), xlt("Preferences"), self.OnPreferences)
    menu.Add(self.OnClose, xlt("Quit SQL"), xlt("Quit Sql"))

    menubar.Append(menu, xlt("&File"))
    
    self.viewmenu=menu=Menu(self)
    menu.AddCheck(self.OnToggleSnippets, xlt("Snippets"), xlt("Show or hide snippet browser"))
    self.registerToggles(True, True)
    menubar.Append(self.viewmenu, xlt("&View"))
    
    self.editmenu=menu=Menu(self)
    menu.Add(self.OnUndo, xlt("&Undo"), xlt("Undo last action"))
    menu.Add(self.OnRedo, xlt("&Redo"), xlt("Redo last action"))
#    menu.Add(xlt("&Find"), xlt("Find string"), self.OnFind)
    menu.AppendSeparator()
    menu.Add(self.OnCut, xlt("Cu&t"), xlt("Cut selected text to clipboard"))
    menu.Add(self.OnCopy, xlt("&Copy"), xlt("Copy selected text to clipboard"))
    menu.Add(self.OnPaste, xlt("&Paste"), xlt("Paste text from clipboard"))
    menu.Add(self.OnClear, xlt("C&lear"), xlt("Clear editor"))
    menu.AppendSeparator()
    menu.Add(self.OnAddSnippet, xlt("Add snippet"), xlt("Add selected text to snippets"))
    menu.Add(self.OnReplaceSnippet, xlt("Modify snippet"), xlt("Replace snippet with selected text"))
    menubar.Append(menu, xlt("&Edit"))
    
    self.querymenu=menu=Menu(self)
    menu.Add(self.OnExecuteQuery, xlt("Execute"), xlt("Execute query"))
    menu.Add(self.OnExplainQuery, xlt("Explain"), xlt("Explain query"))
    menu.Add(self.OnCancelQuery, xlt("Cancel"), xlt("Cancel query execution"))
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

    self.editor=SqlEditor(self)
    self.editor.SetAcceleratorTable(ah.GetTable())
    
    self.editor.BindProcs(self.OnChangeStc, self.OnStatusPos)
    self.manager.AddPane(self.editor, wx.aui.AuiPaneInfo().Top().PaneBorder().Resizable().MinSize((200,100)).BestSize((400,200)).CloseButton(False) \
                          .Name("sqlQuery").Caption(xlt("SQL Query")))
    
    
    self.snippets=SnippetTree(self, self.server, self.editor)
    self.manager.AddPane(self.snippets, wx.aui.AuiPaneInfo().Left().Top().PaneBorder().Resizable().MinSize((100,100)).BestSize((100,100)).CloseButton(True) \
                          .Name("snippets").Caption(xlt("SQL Snippets")))

    if not self.server.snippet_table:
      self.manager.GetPane("snippets").Show(False)

    
    self.output=wx.Notebook(self)
    self.result=SqlResultGrid(self.output)
    self.explain = ExplainCanvas(self.output)
    self.explain.Hide()
    
    font=self.editor.GetFont()
    self.messages=wx.TextCtrl(self.output, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP)
    self.msgHistory=wx.TextCtrl(self.output, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP)
    self.messages.SetFont(font)
    self.msgHistory.SetFont(font)

    self.output.AddPage(self.result, xlt("Output"))
    self.output.AddPage(self.messages, xlt("Messages"))
    self.output.AddPage(self.msgHistory, xlt("History"))
        
    self.manager.AddPane(self.output, wx.aui.AuiPaneInfo().Center().MinSize((200,100)).BestSize((400,200)).CloseButton(False) \
                          .Name("Result").Caption(xlt("Result")).CaptionVisible(False))

    self.manager.Bind(wx.aui.EVT_AUI_PANE_CLOSE, self.OnAuiCloseEvent)

    self.SetStatus(xlt("ready"))
    self.restorePerspective()

    self.viewmenu.Check(self.OnToggleSnippets, self.manager.GetPane("snippets").IsShown())
    self.OnToggleToolBar()
    self.OnToggleStatusBar()
    self.updateMenu()


  def SetTitle(self, dbName):
    title=xlt("PostGreSQL Query Tool - Database \"%(dbname)s\" on Server \"%(server)s\""  % { 'dbname': dbName, 'server': self.server.name})
    adm.Frame.SetTitle(self, title)


  def OnClose(self, evt):
    self.OnCancelQuery(None)
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
        try:
          self.conn = pgConnection(self.server.GetDsn(dbName, self.application))
        except Exception as e:
          print str(e)
        self.databases.SetClientData(i, self.conn)
      self.SetTitle(dbName)
        

  def updateMenu(self, ctl=None):
    if not self.GetToolBar():
      return
    canCut=canPaste=canUndo=canRedo=False
    if not ctl or ctl == self.editor:
      canUndo=self.editor.CanUndo();
      canRedo=self.editor.CanRedo();
      canPaste=self.editor.CanPaste();
      canCut = True;
    a,e=self.editor.GetSelection()
    canQuery = ( a!=e or self.editor.GetLineCount() >1 or self.getSql() )


    self.EnableMenu(self.editmenu, self.OnAddSnippet, self.server.snippet_table)
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
    
    self.startTime=wx.GetLocalTimeMillis();
    self.worker=worker=self.conn.GetCursor().ExecuteAsync(sql)
    rowcount=0
    rowset=None
    worker.start()
    
    self.SetStatus(xlt("Query is running."));
    self.SetStatusText("", self.STATUSPOS_SECS);
    self.SetStatusText("", self.STATUSPOS_ROWS);     
    self.msgHistory.AppendText(xlt("-- Executing query:\n"));
    self.msgHistory.AppendText(sql);
    self.msgHistory.AppendText("\n");
    self.editor.MarkerDelete()   
    self.messages.Clear()
    
    durationTxt=self.pollWorker()

    self.worker=None
    self.EnableMenu(self.querymenu, self.OnCancelQuery, False)
    self.EnableMenu(self.querymenu, self.OnExecuteQuery, True)
    self.EnableMenu(self.querymenu, self.OnExplainQuery, True)

    if worker.error:
      errmsg=worker.error.error
      errlines=errmsg.splitlines()

      self.messages.SetValue(errmsg)
      self.msgHistory.AppendText(errmsg)
      for i in range(1, len(errlines)):
        if errlines[i].startswith("LINE "):
          lineinfo=errlines[i].split(':')[0][5:]
          colinfo=errlines[i+1].find('^')
          dummy=colinfo
          self.editor.MarkerSet(int(lineinfo)-1 + self.editor.GetSelectOffset())
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
    
      rowsMsg += xlt("; %s execution time.") % durationTxt 
      
    self.msgHistory.AppendText("\n")
    currentPage=self.output.GetPage(0)
    if currentPage != targetPage:
      self.output.RemovePage(0)
      currentPage.Hide()
      targetPage.Show()
      self.output.InsertPage(0, targetPage, xlt("Data output"), True)

    if rowset and rowset.colNames:
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

    self.editor.SetFocus()

 
  def getSql(self):  
    sql=self.editor.GetSelectedText()
    if not sql:
      sql=self.editor.GetText()
    return sql.strip()
  
  
  def OnAuiCloseEvent(self, evt):
    if evt.GetPane().name == "snippets":
      self.filemenu.Check(self.OnToggleSnippets, False)

  
  def OnToggleSnippets(self, evt):
    paneInfo=self.manager.GetPane("snippets")
    how=self.viewmenu.IsChecked(self.OnToggleSnippets)
    if isinstance(evt.EventObject, wx.ToolBar):
      how=not how
      self.viewmenu.Check(self.OnToggleSnippets, how)
    paneInfo.Show(how)
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
      self.editor.ClearAll()
      self.editor.ReplaceSelection(sql)
      self.SetStatus(xlt("%d characters read from %s") % (len(sql), self.fileManager.currentFile))
      self.updateMenu()

  def OnRecentFileOpened(self, filename):
    self.fileOpen(None, filename)
    
  def OnFileOpen(self, evt):
    self.fileOpen(xlt("Open SQL file"))
      
  
  def OnFileInsert(self, evt):
    sql=self.readFile(xlt("Insert SQL from file"))
    if sql:
      self.editor.ReplaceSelection(sql)
      self.SetStatus(xlt("%d characters inserted from %s") % (len(sql), self.fileManager.currentFile))
      self.updateMenu()
  
  
  def saveFile(self, proc):    
    try:
      ok=proc(self, self.editor.GetText(), self.filePatterns, xlt("Save SQL Query"))
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
    self.editor.Undo()
  
  def OnClear(self, evt):
    self.editor.ClearAll()
    self.updateMenu()
    
  def OnFind(self, evt):
    pass
  
  def OnRedo(self, evt):
    self.editor.Redo()
  
  def OnChangeStc(self, evt):
    self.sqlChanged=True
    self.updateMenu()
    
  def OnStatusPos(self, evt):
    row=self.editor.LineFromPosition(self.editor.GetCurrentPos())+1
    col=self.editor.GetColumn(self.editor.GetCurrentPos())+1
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
  def OnExecute(parentWin, node):
    frame=QueryFrame(parentWin, node)
    frame.Show()


nodeinfo=[]
menuinfo=[ {"class": QueryTool, "sort": 35 } ]
