# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from wh import xlt, AcceleratorHelper, Menu, Grid, evalAsPython, localTimeMillis
import wx.aui
import wx.grid
import adm

from _pgsql import pgQuery, pgConnectionPool, quoteValue, quoteIdent
from _sqlgrid import SqlFrame, EditTable, HMARGIN, VMARGIN
from _sqledit import SqlEditor
from Table import Table
import logger


class SqlEditGrid(Grid):
  def __init__(self, parent, tableSpecs):
    Grid.__init__(self, parent)
    self.frame=parent
    self.table=None
    pt=parent.GetFont().GetPointSize()
    if wx.Platform != "__WXMSW__":
      pt *= 0.95  # a little smaller
    font=wx.Font(pt, wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.NORMAL)
    self.SetDefaultCellFont(font)
    self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnChangeColSize)

    self.tableSpecs=tableSpecs
    self.lastRow=-1
#    self.node=node
    self.deferredChange=False
    self.dirty=False

    
    self.dataTypes=[]
    
    for cd in self.tableSpecs.colSpecs.values():
      if cd.category == 'B':
        cd.type = self.RegisterDataType('bool:Null', None, wx.grid.GRID_VALUE_BOOL)
      elif cd.category == 'N':
        if cd.pgtype in ['real', 'double precision']:
          cd.type=wx.grid.GRID_VALUE_FLOAT
        elif cd.pgtype in ['numeric']:
          cd.type=wx.grid.GRID_VALUE_NUMBER
        else:
          cd.type=wx.grid.GRID_VALUE_LONG
      elif cd.category == 'E':
        cd.type="ENUM:%s" % cd.pgtype
        if not cd.notNull:
          cd.type += ":Null"
        if cd.type not in self.dataTypes:
          query=pgQuery("pg_enum", self.tableSpecs.GetCursor())
          query.AddCol("enumlabel")
          if self.tableSpecs.serverVersion > 9.1:
            query.addOrder("enumsortorder")
          query.AddWhere('enumtypid', cd.typoid)
          enum=[]
          if not cd.notNull:
            enum.append("")
          for row in query.Select():
            enum.append(row['enumlabel'])
          editor=wx.grid.GridCellChoiceEditor(enum)
          self.RegisterDataType(cd.type, wx.grid.GRID_VALUE_CHOICE, editor)
      else:
        cd.type= wx.grid.GRID_VALUE_STRING

    self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnSelectCell)
    self.Bind(wx.grid.EVT_GRID_EDITOR_SHOWN, self.OnEditorShown)
    self.Bind(wx.grid.EVT_GRID_EDITOR_HIDDEN, self.OnEditorHidden)
    self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnCellRightClick)
    self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.OnLabelDclick)
    self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnLabelRightClick)
    self.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.OnCellChanged)

  def OnChangeColSize(self, evt):
    adm.config.storeGridPositions(self, self, self.tableSpecs.tabName)

  def RegisterDataType(self, typename, renderer, editor):
    if not typename in self.dataTypes:
      if not renderer:
        renderer=wx.grid.GRID_VALUE_STRING
      if not editor:
        editor=wx.grid.GRID_VALUE_STRING
      if isinstance(renderer, str):
        renderer=self.GetDefaultRendererForType(renderer)
      if isinstance(editor, str):
        editor=self.GetDefaultEditorForType(editor)
      wx.grid.Grid.RegisterDataType(self, typename, renderer, editor)
      self.dataTypes.append(typename)
    return typename

  def Cut(self):
    self.Copy()
  
  def Copy(self):
    vals=self.GetAllSelectedCellValues()
    cellSep=", "
    rowSep="\n"
    if vals:
      txt=rowSep.join(map(lambda row:cellSep.join(row), vals))
      adm.SetClipboard(txt)

      
  def GetQuotedColLabelValue(self, col):
    quoteChar="'"
    val=self.table.colNames[col]
    return self.quoteVal(val, quoteChar)
          
  def GetQuotedCellValue(self, row, col):
    quoteChar="'"
    val=self.table.rows[row][self.table.colNames[col]]
    if val == None:
      return "NULL"
    return self.quoteVal(val, quoteChar)
  
  def RevertEdit(self):
    self.table.Revert()
    self.Refresh()
      
  def RefreshRow(self, row):
    if row < 0:
      return
    for col in range(len(self.table.colNames)):
      self.RefreshAttr(row, col)

  def DoCommit(self):
    if self.IsCellEditControlShown():
      self.SaveEditControlValue()
      self.HideCellEditControl()
    self.RefreshRow(self.table.currentRowNo)
    if self.table.Commit(): # if there was something to save
      self.frame.SetStatus(xlt("Saved."))
    self.dirty=False
    self.deferredChange=False
    self.RefreshRow(self.table.currentRowNo)
    self.frame.updateMenu()
    
  def OnCellChanged(self, evt):
    if self.deferredChange:
      self.DoCommit()
    else:
      if not self.dirty and self.table.colsChanged:
        self.dirty = True
        self.RefreshRow(evt.Row)
      
  def OnSelectCell(self, evt):
    if evt.Row != self.lastRow:
      if self.lastRow >= 0:
        if self.IsCellEditControlShown():
          self.deferredChange=True
        else:
          self.DoCommit()
    self.lastRow = evt.Row
  
  def OnEditorShown(self, evt):
    self.dirty=True
    self.frame.SetStatus()
    self.frame.SetStatusText("", SqlFrame.STATUSPOS_SECS)
    self.frame.updateMenu()
    
  def OnEditorHidden(self, evt):
    pass

  def OnCellRightClick(self, evt):
    self.GoToCell(evt.Row, evt.Col)
    self.cmRow=evt.Row
    self.cmCol=evt.Col
    colname=self.table.colNames[evt.Col]
    cd=self.tableSpecs.colSpecs.get(colname)

    cm=Menu(self.GetParent())
    if cd:
      item=cm.Add(self.OnSetNull, xlt("Set NULL"))
      if cd.notNull:
        cm.Enable(item, False)
    cm.Popup(evt)
    
  def OnLabelRightClick(self, evt):
    if evt.Row >= 0:
      self.SelectRow(evt.Row, evt.ControlDown())
      rows=self.GetAllSelectedRows()
      try:  rows.remove(len(self.table.rows))
      except: pass

      if self.tableSpecs.keyCols and rows:
        cm=Menu(self.GetParent())
        if len(rows) > 1: cm.Add(self.OnDeleteRows, xlt("Delete rows"))
        else:             cm.Add(self.OnDeleteRows, xlt("Delete row"))
        cm.Popup(evt)
        
  def OnDeleteRows(self, evt):
    rows=self.GetAllSelectedRows()
    try:  rows.remove(len(self.table.rows))
    except: pass

    if True: # askDeleteConfirmation
      if len(rows)>1:
        msg=xlt("Delete selected %d rows?") % len(rows)
      else:
        msg=xlt("Delete selected row?")
      dlg=wx.MessageDialog(self, msg, xlt("Delete data"))
      if not dlg.ShowModal() == wx.ID_OK:
        return
    
    rows.sort()
    rows.reverse()
    rc=self.table.Delete(rows)
    if rc != len(rows):
      logger.debug("Rowcount %d after DELETE differs from expected %d", rc, len(rows))
      self.GetParent().OnRefresh()
      return
    self.frame.SetStatusText(xlt("%d rows") % len(self.table.rows), self.frame.STATUSPOS_ROWS)


  def OnSetNull(self, evt):  
    self.SetCellValue(self.cmRow, self.cmCol, "")
    self.table.SetValue(self.cmRow, self.cmCol, None)  
    
  
  def OnLabelDclick(self, evt):
    if evt.Row >= 0:
      if evt.Row < self.table.GetRowsCount():
        data=self.table.rows[evt.Row]
      else:
        data={}
      _editDataHere=data
    elif evt.Col >= 0:
      pass # RefTable here
    
  def SetEmpty(self):
    self.table=None
    self.SetTable(wx.grid.GridStringTable(0,0))
    self.SetColLabelSize(0)
    self.SetRowLabelSize(0)
    self.AutoSize()
    
  def SetData(self, rowset):
    self.table=EditTable(self, self.tableSpecs, rowset)
    self.SetTable(self.table)
    self.Freeze()
    self.BeginBatch()
    w,h=self.GetTextExtent('Colname')
    self.SetColLabelSize(h+HMARGIN)
    self.SetRowLabelSize(w+VMARGIN)
    self.SetDefaultRowSize(h+HMARGIN)

    self.EnableEditing(not self.table.readOnly)
    self.EndBatch()

    self.AutoSizeColumns(False)
    adm.config.restoreGridPositions(self, self, self.tableSpecs.tabName)
    adm.config.storeGridPositions(self, self, self.tableSpecs.tabName)

    self.Thaw()
    self.SendSizeEventToParent()
    
    
class ColSpec:
  def __init__(self, row):
    self.category=row['typcategory']
    self.notNull=row['attnotnull']
    self.length=-1
    self.precision=-1
    self.pgtype=row['formatted']
    self.typoid=row['atttypid']
    fmt=self.pgtype.split('(')
    _typ=fmt[0]
    if len(fmt) > 1:
      p=fmt[1][:-1].split(',')
      self.length=int(p[0])
      if len(p) > 1:
        self.precision=int(p[1])

  def IsNumeric(self):
    return self.category == 'N'

   
  def GetClass(self):
    # http://www.postgresql.org/docs/9.3/static/catalog-pg-type.html#CATALOG-TYPCATEGORY-TABLE
    if self.category == 'B':  # bool
      return bool
    elif self.category == 'N':  # numeric
      return int
    elif self.category == 'S':
      return unicode
    return unicode 


class TableSpecs:
  def __init__(self, connectionPool, name):
    self.tabName=name
    self.connectionPool=connectionPool
    self.serverVersion= connectionPool.ServerVersion()
    for part in self.connectionPool.dsn.split():
      if part.startswith('dbname='):
        self.dbName=part[7:]
    
    cursor=connectionPool.GetCursor()
    row=cursor.ExecuteRow("""
      SELECT c.oid, relhasoids
        FROM pg_class c
       WHERE oid=oid(regclass('%s'))
    """ % self.tabName)
    if not row:
      raise Exception(xlt("No such table: %s") % self.tabName)
    self.oid=row['oid']
    self.hasoids = row['relhasoids']
    
    self.constraints = cursor.ExecuteDictList(Table.getConstraintQuery(self.oid))

    self.colSpecs={}
    self.colNames=[]
    set=cursor.ExecuteSet("""
        SELECT attname, attnotnull, atttypid, atttypmod, t.typcategory, CASE WHEN typbasetype >0 THEN format_type(typbasetype,typtypmod) ELSE format_type(atttypid, atttypmod) END as formatted
         FROM pg_attribute a
         JOIN pg_type t ON t.oid=atttypid
        WHERE attrelid=%d
          AND (attnum>0 OR attnum = -2) AND NOT attisdropped
        ORDER BY attnum
    """ % self.oid)
    for row in set:
      attname=row['attname']
      self.colNames.append(attname)
      self.colSpecs[attname]=ColSpec(row)

    self.primaryConstraint=None
    if self.hasoids:
      self.keyCols=['oid']
    else:
      for c in self.constraints:
        if c.get('indisprimary'):
          self.primaryConstraint=c;
          break;
      if not self.primaryConstraint:
        for c in self.constraints:
          if c.get('isunique'):
            self.primaryConstraint=c;
            break;
      if self.primaryConstraint:
        self.keyCols=self.primaryConstraint.get('colnames')
      else:
        self.keyCols=[]


  def GetCursor(self):
    return self.connectionPool.GetCursor()


class TextDropTarget(wx.TextDropTarget):
  def __init__(self, lb):
    wx.TextDropTarget.__init__(self)
    self.lb=lb
  
  def OnDropText(self, x, y, text):
    target=self.lb.HitTest((x, y))
    if target >= 0:
      source=int(text)
      if target == source:
        return
      if hasattr(self.lb, 'IsChecked'):
        chk=self.lb.IsChecked(source)
      text=self.lb.GetString(source)
      self.lb.Delete(source)
      self.lb.Insert(text, target)
      if hasattr(self.lb, 'IsChecked'):
        self.lb.Check(target, chk)
  
  
class FilterPanel(adm.NotebookPanel):
  def __init__(self, dlg, notebook):
    adm.NotebookPanel.__init__(self, dlg, notebook)
    self.Bind("LimitCheck", self.OnLimitCheck)
    self.Bind("FilterCheck", self.OnFilterCheck)
    self.Bind("FilterValidate", self.OnFilterValidate)
    self.FilterValue.BindProcs(self.OnFilterValueChanged, None)
    self.Bind("FilterPreset", wx.EVT_COMBOBOX, self.OnPresetSelect)
    self.Bind("FilterPreset", wx.EVT_TEXT, self.OnPresetChange)
    self.Bind("FilterSave", self.OnFilterSave)
    self['SortCols'].Bind(wx.EVT_LISTBOX_DCLICK, self.OnDclickSort)
    # TODO unfortunately we need 3.x here
    if True: # wx.Platform == "__WXMAC__" and wx.VERSION < (3,0):
      event=wx.EVT_LEFT_DOWN
    else:
      event=wx.EVT_MOTION
    self['DisplayCols'].Bind(event, self.OnBeginDrag)
    self['SortCols'].Bind(event, self.OnBeginDrag)
    self['DisplayCols'].Bind(wx.EVT_CHECKLISTBOX, self.OnClickCol)
    self.OnLimitCheck()
    self.OnFilterCheck()
    self.valid=True
    self.dialog=dlg
    self.EnableControls("FilterPreset", dlg.querypreset_table)
    self.EnableControls("FilterSave", False)

  def AddExtraControls(self, res):
    self.FilterValue=SqlEditor(self)
    res.AttachUnknownControl("FilterValuePlaceholder", self.FilterValue)
    self.FilterValue.SetMarginWidth(1, 0)

  def OnPresetSelect(self, evt):
    preset=self.FilterPreset.strip()
    if not preset:
      return
    query=pgQuery(self.dialog.querypreset_table, self.dialog.server.GetCursor())
    query.AddCol('querylimit')
    query.AddCol('filter')
    query.AddCol('sort')
    query.AddCol('display')
    query.AddCol('sql')
    query.AddWhere('dbname', self.tableSpecs.dbName)
    query.AddWhere('tabname', self.tableSpecs.tabName)
    query.AddWhere('presetname', preset)
    
    res=query.Select()
    for row in res:
      limit=row['querylimit']
      filter=row['filter']
      sort=evalAsPython(row['sort'])
      display=evalAsPython(row['display'])
      sql=row['sql']
      if limit:
        self.LimitCheck=True
        self.OnLimitCheck()
        self.LimitValue=limit
      else:
        self.LimitCheck=False
      if sql:
        self.dialog.editor.SetText(sql)
      
      if sort:
        sc=self['SortCols']
        sc.Clear()
        cols=self.tableSpecs.colNames[:]
        for col in sort:
          if col.endswith(' DESC'): colpure=col[:-5]
          else:                     colpure=col
          if colpure in cols:
            id=sc.Append(col)
            sc.Check(id, True)
            cols.remove(colpure)
        sc.AppendItems(cols)
      if display:
        dc=self['DisplayCols']
        dc.Clear()
        cols=self.tableSpecs.colNames[:]
        for col in display:
          if col in cols:
            id=dc.Append(col)
            dc.Check(id, True)
            cols.remove(col)
        dc.AppendItems(cols)
          
      if filter:
        self.FilterCheck=True
        self.OnFilterCheck()
        self.FilterValue.SetText(filter)
        self.OnFilterValidate(evt)
      else:
        self.FilterCheck=False

      break # only one row, hopefully
    
    self.OnPresetChange(evt)
    
  def OnPresetChange(self, evt):
    self.EnableControls("FilterSave", self.FilterPreset)
    
  def OnClickCol(self, evt):
    if evt.String in self.dialog.tableSpecs.keyCols:
      # don't un-display key colums; we need them
      evt.EventObject.Check(evt.Selection, True)
    pass
  
  def OnBeginDrag(self, evt):
    if evt.GetPosition().x < 30 or not evt.LeftDown():
      evt.Skip()
      return
    
    lb=evt.EventObject
    i=lb.HitTest(evt.GetPosition())
    if i >= 0:
      lb.SetDropTarget(TextDropTarget(lb))
      data=wx.PyTextDataObject(str(i))
      ds=wx.DropSource(lb)
      ds.SetData(data)
      ds.DoDragDrop(False)
      lb.SetDropTarget(None)
    
  def OnDclickSort(self, evt):
    colname=self['SortCols'].GetString(evt.Selection)
    if colname.endswith(" DESC"):
      colname=colname[:-5]
    else:
      colname = colname+" DESC"
    self['SortCols'].SetString(evt.Selection, colname)
  
  
  def OnFilterSave(self, evt):
    preset=self.FilterPreset
    if self.LimitCheck:   limit=self.LimitValue
    else:                 limit=None
    if self.FilterCheck:  filter=self.FilterValue.GetText()
    else:                 filter=None
    sort=self['SortCols'].GetCheckedStrings()
    display=self['DisplayCols'].GetCheckedStrings()
    sql=self.dialog.editor.GetText()
    
    query=pgQuery(self.dialog.querypreset_table, self.dialog.server.GetCursor())
    query.AddColVal('querylimit', limit)
    query.AddColVal('filter', filter)
    query.AddColVal('sort', unicode(sort))
    query.AddColVal('display', unicode(display))
    query.AddColVal('sql', sql)
    
    fp=self['FilterPreset']
    if fp.FindString(preset) < 0:
      query.AddColVal('dbname', self.tableSpecs.dbName)
      query.AddColVal('tabname', self.tableSpecs.tabName)
      query.AddColVal('presetname', preset)
      query.Insert()
      fp.Append(preset)
    else:
      query.AddWhere('dbname', self.tableSpecs.dbName)
      query.AddWhere('tabname', self.tableSpecs.tabName)
      query.AddWhere('presetname', preset)
      query.Update()
    
  def OnLimitCheck(self, evt=None):
    self.EnableControls("LimitValue", self.LimitCheck)

  def OnFilterCheck(self, evt=None):
    self.EnableControls("FilterValidate", self.FilterCheck)
    self.FilterValue.Enable(self.FilterCheck)
    self.OnFilterValueChanged(evt)

  def OnFilterValueChanged(self, evt):
    self.valid=not self.FilterCheck
    self.dialog.updateMenu()
  
  def OnFilterValidate(self, evt):
    self.valid=False
    
    sql="EXPLAIN " + self.GetQuery()
    cursor=self.tableSpecs.GetCursor()
    cursor.ExecuteSet(sql)  # will throw and show exception if invalid

    self.dialog.SetStatus(xlt("Filter expression valid"))
    self.valid=True
    self.dialog.updateMenu()

  def Go(self, tableSpecs):
    self.tableSpecs=tableSpecs
    dc=self['DisplayCols']
    sc=self['SortCols']
    
    for colName in self.tableSpecs.colNames:
      i=dc.Append(colName)
      dc.Check(i, True)
      i=sc.Append(colName)
      if colName in self.tableSpecs.keyCols:
        sc.Check(i, True)
    if self.dialog.querypreset_table:
      query=pgQuery(self.dialog.querypreset_table, self.dialog.server.GetCursor())
      query.AddCol('presetname')
      query.AddWhere('dbname', self.tableSpecs.dbName)
      query.AddWhere('tabname', self.tableSpecs.tabName)
      query.AddOrder('presetname')
      res=query.Select()
      fp=self['FilterPreset']
      for row in res:
        fp.Append(row[0])
      
      default=fp.FindString('default')
      if id >= 0:
        fp.SetSelection(default)
        self.OnPresetSelect(None)
        
  def GetQuery(self):
    query=pgQuery(self.tableSpecs.tabName)
    for colName in self['DisplayCols'].GetCheckedStrings():
      query.AddCol(colName, True)
    for colName in self['SortCols'].GetCheckedStrings():
      query.AddOrder(colName, True)
    if self.FilterCheck:
      filter=self.FilterValue.GetText().strip()
      query.AddWhere(filter)
    
    sql= query.SelectQueryString()
    if self.LimitCheck:
      sql += "\n LIMIT %d" % self.LimitValue
    return sql


class DataFrame(SqlFrame):
  def __init__(self, parentWin, connectionPool, name, server):
    self.tableSpecs=TableSpecs(connectionPool, name)
    self.connectionPool=connectionPool
    self.worker=None
    self.output=None
    self.server=server
    querypreset_table=self.server.info.get('querypreset_table')
    if self.server.adminspace and querypreset_table:
      self.querypreset_table="%s.%s" % (quoteIdent(self.server.adminspace), quoteIdent(querypreset_table))
    else:
      self.querypreset_table=None
      
          
    title=xlt("%(appTitle)s Data Tool - %(tableName)s") % {
                'appTitle': adm.appTitle, 'tableName': name}
    SqlFrame.__init__(self, parentWin, title, "SqlData")

    toolbar=self.GetToolBar()

    toolbar.Add(self.OnRefresh, xlt("Refresh"), "data_refresh")
    toolbar.Add(self.OnCancelRefresh, xlt("Cancel refresh"), "query_cancel")
    toolbar.Add(self.OnSave, xlt("Save data"), "data_save")
    toolbar.Add(self.OnToggleFilter, xlt("Show filter window"), "filter")
    toolbar.AddSeparator()
    toolbar.Add(self.OnCopy, xlt("Copy"), "clip_copy")
    toolbar.Add(self.OnCut, xlt("Cut"), "clip_cut")
    toolbar.Add(self.OnPaste, xlt("Paste"), "clip_paste")
    toolbar.Add(self.OnUndo, xlt("Undo"), "edit_undo")
    toolbar.AddSeparator()
    toolbar.Add(self.OnDelete, xlt("Delete"), "delete")

    menubar=wx.MenuBar()
    
    self.filemenu=menu=Menu(self)
    menu.Add(self.OnClose, xlt("Quit tool"), xlt("Quit data tool"))

    menubar.Append(menu, xlt("&File"))
    
    self.datamenu=menu=Menu(self)
    menu.Add(self.OnRefresh, xlt("Refresh"), xlt("Refresh data"))
    menu.Add(self.OnCancelRefresh, xlt("Cancel"), xlt("Cancel refresh"))
    menu.Add(self.OnSave, xlt("Save"), xlt("Save data"))
    menu.Add(self.OnDelete, xlt("Delete"), xlt("Delete row(s)"))
    menubar.Append(menu, xlt("&Data"))

    self.viewmenu=menu=Menu(self)
    menu.AddCheck(self.OnToggleFilter, xlt("Filter"), xlt("Show or hide filter window"))
    self.registerToggles(True, True)
    menubar.Append(menu, xlt("&View"))
    
    self.editmenu=menu=Menu(self)
    menu.Add(self.OnCut, xlt("Cu&t"), xlt("Cut selected data to clipboard"))
    menu.Add(self.OnCopy, xlt("&Copy"), xlt("Copy selected data to clipboard"))
    menu.Add(self.OnPaste, xlt("&Paste"), xlt("Paste data from clipboard"))
    menu.Add(self.OnUndo, xlt("&Undo"), xlt("discard last editing"))
    menubar.Append(menu, xlt("&Edit"))

    self.helpmenu=menu=Menu(self)
    menu.Add(self.OnHelp, xlt("Help"), xlt("Show help"), wx.ID_HELP)
    menubar.Append(menu, xlt("&Help"))

    self.EnableMenu(self.datamenu, self.OnCancelRefresh, False)
    self.SetMenuBar(menubar)

    toolbar.Realize()

    ah=AcceleratorHelper(self)
    ah.Add(wx.ACCEL_CTRL, 'X', self.OnCut)
    ah.Add(wx.ACCEL_CTRL, 'C', self.OnCopy)
    ah.Add(wx.ACCEL_CTRL, 'V', self.OnPaste)
    ah.Add(wx.ACCEL_CTRL, 'S', self.OnSave)
    ah.Add(wx.ACCEL_NORMAL,wx.WXK_F5, self.OnRefresh)
    ah.Add(wx.ACCEL_ALT,wx.WXK_PAUSE, self.OnCancelRefresh)
    ah.Realize()
    
    self.notebook=wx.Notebook(self)
    self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnCheck)
    self.filter=FilterPanel(self, self.notebook)
    self.notebook.AddPage(self.filter, xlt("Filter, Order, Limit"))
    self.editor=SqlEditor(self.notebook)
    self.editor.SetAcceleratorTable(ah.GetTable())
    self.notebook.AddPage(self.editor, xlt("Manual SQL"))
    
    self.manager.AddPane(self.notebook, wx.aui.AuiPaneInfo().Top().PaneBorder().Resizable().MinSize((200,200)).BestSize((400,200)).CloseButton(True) \
                          .Name("filter").Caption(xlt("SQL query parameter")).Hide())


    self.output = SqlEditGrid(self, self.tableSpecs)
    self.manager.AddPane(self.output, wx.aui.AuiPaneInfo().Center().MinSize((200,100)).BestSize((400,200)).CloseButton(False) \
                          .Name("Edit Data").Caption(xlt("Edit Data")).CaptionVisible(False))

    self.restorePerspective()
    self.manager.Bind(wx.aui.EVT_AUI_PANE_CLOSE, self.OnAuiCloseEvent)
    self.viewmenu.Check(self.OnToggleFilter, self.manager.GetPane("filter").IsShown())
    self.OnToggleToolBar()
    self.OnToggleStatusBar()

    self.updateMenu()
    self.filter.Go(self.tableSpecs)

    if not self.editor.GetText():    # otherwise set from default preset
      self.editor.SetText("/*\n%s\n*/\n\n%s" % (xlt(
                "Caution: Don't mess with table and column names!\nYou may experience unwanted behaviour or data loss."), 
                                              self.filter.GetQuery()))

  def OnHelp(self, evt):
    wx.LaunchDefaultBrowser("http://www.admin4.org/docs/pgsql/datatool")
    
  def OnAuiCloseEvent(self, evt):
    if evt.GetPane().name == "filter":
      self.datamenu.Check(self.OnToggleFilter, False)

  def OnToggleFilter(self, evt):
    paneInfo=self.manager.GetPane("filter")
    how=self.viewmenu.IsChecked(self.OnToggleFilter)
    if isinstance(evt.EventObject, wx.ToolBar):
      how=not how
      self.viewmenu.Check(self.OnToggleFilter, how)
    paneInfo.Show(how)
    self.manager.Update()    
    

  def OnCheck(self, evt):
    if evt.GetSelection():
      self.editor.Show()
    self.updateMenu(evt.GetSelection())
      
  def updateMenu(self, sel=None):
    if sel == None:
      sel=self.notebook.GetSelection()
    if sel:
      queryOk=True
    else:
      queryOk=self.filter.valid

    if self.output:
      if self.output.table:
        canSave=self.output.dirty
        canUndo=(self.output.table.currentRow!=None)
      else:
        canSave=canUndo=False
    
      self.EnableMenu(self.editmenu, self.OnUndo, canUndo)        
      self.EnableMenu(self.datamenu, self.OnRefresh, queryOk)
      self.EnableMenu(self.datamenu, self.OnSave, canSave)
    
  def OnDelete(self, evt):
    self.output.OnDeleteRows(evt)

  def executeQuery(self, sql):
    self.output.SetEmpty()
    self.worker=None
    
    self.EnableMenu(self.datamenu, self.OnRefresh, False)
    self.EnableMenu(self.datamenu, self.OnCancelRefresh, True)
    
    self.startTime=localTimeMillis();
    self.worker=worker=self.tableSpecs.GetCursor().ExecuteAsync(sql)
    worker.start()
    
    self.SetStatus(xlt("Refreshing data..."));
    self.SetStatusText("", self.STATUSPOS_ROWS)

    self.pollWorker()

    self.EnableMenu(self.datamenu, self.OnCancelRefresh, False)
    self.EnableMenu(self.datamenu, self.OnRefresh, True)
  
    txt=xlt("%d rows") % worker.GetRowcount()
    if not self.notebook.GetSelection() and self.filter.LimitCheck and self.filter.LimitValue == worker.GetRowcount():
      txt += " LIMIT"
    self.SetStatusText(txt, self.STATUSPOS_ROWS)

    if worker.cancelled:
      self.SetStatus(xlt("Cancelled."));
      self.output.SetData(worker.GetResult())
    elif worker.error:
      errlines=worker.error.error.splitlines()
      self.output.SetEmpty()
      self.SetStatus(errlines[0]);
    else:
      self.SetStatus(xlt("OK."));
      
      self.output.SetData(worker.GetResult())
      

  def OnSave(self, evt):
    self.output.DoCommit()
    self.output.Refresh()
    
    
  def OnRefresh(self, evt=None):
    if self.notebook.GetSelection():
      sql=self.editor.GetSelectedText()
      if not sql:
        sql=self.editor.GetText()
      if not sql.strip():
        return
    else:
      sql=self.filter.GetQuery()
    self.executeQuery(sql)
  
  def OnCancelRefresh(self, evt):
    self.EnableMenu(self.datamenu, self.OnCancelRefresh, False)
    if self.worker:
      self.worker.Cancel()
  
  def OnUndo(self, evt):
    self.output.RevertEdit()
    

  def OnClose(self, evt):
    self.OnCancelRefresh(None)
    if self.output.table and self.output.table.currentRow:
      dlg=wx.MessageDialog(self, xlt("Data is changed but not written.\nSave now?"), xlt("Unsaved data"), 
                           wx.YES_NO|wx.CANCEL|wx.CANCEL_DEFAULT|wx.ICON_EXCLAMATION)
      rc=dlg.ShowModal()
      if rc == wx.ID_CANCEL:
        return 
      elif rc == wx.ID_YES:
        self.output.table.Commit()
        
    self.worker = None
    self.connectionPool.Disconnect()
    adm.config.storeWindowPositions(self)
    self.Destroy()

class DataTool:
  name=xlt("Data Tool")
  help=xlt("Show and modify data")
  toolbitmap='SqlData'
  knownClasses=['Table', 'View']
  
  @staticmethod
  def GetInstrumentQuery(server):
    sql="""SELECT 'querypreset_table', relname FROM pg_class JOIN pg_namespace nsp ON nsp.oid=relnamespace 
         WHERE nspname=%(adminspace)s AND relname=%(querypreset_table)s""" % {
         'adminspace': quoteValue(server.GetPreference("AdminNamespace")),
         'querypreset_table': quoteValue("Admin_QueryPreset_%s" % server.user)
          }
    return sql

  @staticmethod
  def GetMissingInstrumentation(server):
    if not server.info.get('querypreset_table'):
      return 'querypreset_table'
  
  @staticmethod
  def DoInstrument(server):
    if not server.info.get('querypreset_table'):
      querypreset_table=quoteIdent("Admin_QueryPreset_%s" % server.user)
      server.GetCursor().ExecuteSingle("""
        CREATE TABLE %(adminspace)s.%(querypreset_table)s 
                  (dbname TEXT NOT NULL, tabname TEXT NOT NULL, presetname TEXT NOT NULL, 
                   querylimit INTEGER, filter TEXT, sort TEXT, display TEXT, sql TEXT,
                   PRIMARY KEY(dbname, tabname, presetname));""" % 
        {'adminspace': quoteIdent(server.adminspace),
        'querypreset_table': querypreset_table })
    return True
  
  
  @staticmethod
  def CheckAvailableOn(node):
    return node.__class__.__name__ in DataTool.knownClasses

  @staticmethod
  def CheckEnabled(node):
    return node.__class__.__name__ in DataTool.knownClasses

  @staticmethod
  def OnExecute(parentWin, node):
    application="%s Data Tool" % adm.appTitle
    server=node.GetServer()
    pool=pgConnectionPool(server, server.GetDsn(node.GetDatabase().name, application))
    frame=DataFrame(parentWin, pool, node.NameSql(), server)
    frame.Show()
    frame.OnRefresh()

  
nodeinfo=[]
menuinfo=[{"class": DataTool, "sort": 30 } ]

