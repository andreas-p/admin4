# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import wx.grid, wx.aui
from wh import xlt, ToolBar, floatToTime, Menu
from _pgsql import pgQuery, quoteIdent

NULLSTRING="(NULL)"
HMARGIN=5
VMARGIN=5




#################################################################################


class EditTable(wx.grid.PyGridTableBase):
  def __init__(self, grid, tableSpecs, rowset):
    wx.grid.PyGridTableBase.__init__(self)
    self.grid=grid
    self.hasoids=self.grid.tableSpecs.hasoids
    self.colNames=rowset.colNames
    self.tableSpecs=tableSpecs
    self.rows=rowset.getDictList()
    self.canUpdate=len(tableSpecs.keyCols)
    self.readOnly=False
    self.attrs=[]
    self.Revert()

  def Revert(self):
    self.currentRow=None
    self.currentRowNo=-1
    self.colsChanged=[]

  def Commit(self):
    if self.currentRowNo >= 0:
      query=pgQuery(self.tableSpecs.tabName, self.tableSpecs.GetCursor())
      if self.currentRowNo < len(self.rows):
        # UPDATE case
        for col in self.colsChanged:
          colname=self.colNames[col]
          val=self.currentRow[colname]
          query.AddColVal(quoteIdent(colname), val)

        r=self.rows[self.currentRowNo]
        if self.hasoids:
          query.AddWhere("oid", r['oid'])
        else:
          for colname in self.tableSpecs.keyCols:
            query.AddWhere(quoteIdent(colname), self.currentRow[colname])
            
        query.Update()
        self.rows[self.currentRowNo] = self.currentRow
      else:
        # INSERT case
        for colname in self.colNames:
          if colname == "oid" and self.hasoids:
            continue
          value=self.currentRow.get(colname)
          if value != None:
            query.AddColVal(quoteIdent(colname), self.currentRow[colname])
        
        returned=query.Insert()
        if returned:
          if self.hasoids:
            self.currentRow['oid'] = returned
          else:
            pass # TODO  update of key cols if we had them returned
        self.rows.append(self.currentRow)
        self.grid.GetParent().SetStatusText(xlt("%d rows") % len(self.rows), SqlFrame.STATUSPOS_ROWS)
        self.grid.AppendRows(1)
      rc=True
    else:
      rc=False
    self.Revert()
    return rc

  
  def GetColDef(self, col):
    return self.tableSpecs.colSpecs.get(self.colNames[col])

  def AppendRows(self, _rowcount):
    return 
  
  def GetNumberRows(self):
    rc=len(self.rows)
    if not self.readOnly:
      rc += 1
    return rc
  
  def GetNumberCols(self):
    return len(self.colNames)
  
  def GetColLabelValue(self, col):
    return self.colNames[col]

  def GetTypeName(self, _row, col):
    cd=self.GetColDef(col)
    if cd:  return cd.type
    return wx.grid.GRID_VALUE_STRING
  
  def GetRowLabelValue(self, row):
    if row >= len(self.rows):
      return "*"
    return str(row+1)
  
  def GetValue(self, row, col):
    val=self.getValue(row, col)
#    if self.GetColDef(col).category == 'B':
#      return bool(val)
      
    if val == None:   return ""
    else:
      if isinstance(val, bool):
        if val: return xlt("true")
        else:   return xlt("false")
      return val

  def getValue(self, row, col):
    val=None
    if row == self.currentRowNo:
      val=self.currentRow.get(self.colNames[col])
    elif row < len(self.rows):
      val= self.rows[row].get(self.colNames[col])
    return val
  
  
  def SetValue(self, row, col, value):
    if row != self.currentRowNo:
      if self.currentRowNo >= 0:
        raise Exception("We dont want that")
      self.currentRowNo=row
      if row == len(self.rows):
        self.currentRow={}
      else:
        self.currentRow = self.rows[row].copy()

    cd=self.GetColDef(col)
    if cd:
      if col not in self.colsChanged:
        self.colsChanged.append(col)
      if cd.category == 'E' and not value:
        value=None
      if value != None:
        cls=cd.GetClass()
        value=cls(value)
      self.currentRow[self.colNames[col]] = value
    
  def GetAttr(self, row, col, _params):
    try:  # When the wxGridCellEditorBool is active, an exception occurs here
      color=None
      alignRight=False
      ro=False
      
      colname=self.colNames[col]
        
      if self.getValue(row, col) == None:
        color=wx.Colour(232,232,232)
      elif colname in self.tableSpecs.keyCols:
        color=wx.Colour(232,255,232)
  
      if row == self.currentRowNo:
        if color:
          color=wx.Colour(color.red, color.green, color.blue-32)
        else:
          color=wx.Colour(255,255,200)

      cd=self.tableSpecs.colSpecs.get(colname)
      if cd:
        if cd.IsNumeric():
          alignRight=True
        if colname == 'oid' and self.tableSpecs.hasoids:
          ro=True
      else:
        color=wx.Colour(232,232,255)
        ro=True
        
      if color or alignRight or ro:
        attr=wx.grid.GridCellAttr()
        if color:
          attr.SetBackgroundColour(color)
        if alignRight:
          attr.SetAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
        if ro:
          attr.SetReadOnly(True)
        return attr
    except:
      pass
    return None
    
  
#################################################################################


  
class SqlEditGrid(wx.grid.Grid):
  def __init__(self, parent, tableSpecs):
    wx.grid.Grid.__init__(self, parent)
    pt=parent.GetFont().GetPointSize()
    if wx.Platform != "__WXMSW__":
      pt *= 0.95  # a little smaller
    font=wx.Font(pt, wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.NORMAL)
    self.SetDefaultCellFont(font)

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
    self.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.OnCellChanged)


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

  def RevertEdit(self):
    self.table.Revert()
    self.Refresh()
      
  def RefreshRow(self, row):
    if row < 0:
      return
    for col in range(len(self.table.colNames)):
      self.RefreshAttr(row, col)

  
  def DoCommit(self):
    self.RefreshRow(self.table.currentRowNo)
    if self.table.Commit():
      self.GetParent().SetStatus(xlt("Saved."))
    self.deferredChange=False
    self.dirty=False
    
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
    self.GetParent().SetStatus()
    self.GetParent().SetStatusText("", SqlFrame.STATUSPOS_SECS)
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
      item=cm.Append(self.OnSetNull, xlt("Set NULL"))
      if cd.notNull:
        cm.Enable(item, False)
    cm.Popup(evt.GetPosition())
    

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
    self.SetTable(wx.grid.GridStringTable(1,1))
    self.SetCellValue(0, 0, xlt("Refreshing data..."))
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
    self.Thaw()
    self.AutoSizeColumns()
    self.SendSizeEventToParent()
    
    
#################################################################################
  
class SqlFrame(adm.Frame):
  STATUSPOS_POS=1
  STATUSPOS_ROWS=2
  STATUSPOS_SECS=3
  filePatterns=[(xlt("SQL files"), '*.sql'),
                (xlt("Text files"), '*.txt'),
                (xlt("All files"), '*.*')
                ]
  
  def __init__(self, _parentWin, name, icon):
    style=wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX
    adm.Frame.__init__(self, None, name, style, (600,400), None)
    
    self.SetIcon(icon, self)
    self.manager=wx.aui.AuiManager(self)
    self.manager.SetFlags(wx.aui.AUI_MGR_ALLOW_FLOATING|wx.aui.AUI_MGR_TRANSPARENT_HINT | \
         wx.aui.AUI_MGR_HINT_FADE| wx.aui.AUI_MGR_TRANSPARENT_DRAG)
    self.Bind(wx.EVT_CLOSE, self.OnClose)
    ToolBar(self, 16)
    self.CreateStatusBar(4, wx.ST_SIZEGRIP)
    w,_h=self.StatusBar.GetTextExtent('Mg')
    self.SetStatusWidths([-1, 5*w,6*w,5*w])

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


  def pollWorker(self):
    while self.worker.IsRunning():
      elapsed=wx.GetLocalTimeMillis() - self.startTime
      self.SetStatusText(floatToTime(elapsed/1000.), self.STATUSPOS_SECS)
      wx.Yield()
      if elapsed < 200:
        wx.MilliSleep(10);
      elif elapsed < 10000:
        wx.MilliSleep(100);
      else:
        wx.MilliSleep(500)
      wx.Yield()
    
    elapsed=wx.GetLocalTimeMillis() - self.startTime
    if elapsed:
      txt=floatToTime(elapsed/1000.)
    else:
      txt="0 ms"
    self.SetStatusText(txt, self.STATUSPOS_SECS)
    
    
  def restorePerspective(self, skipConfig=False):
    if not skipConfig:
      str=adm.config.GetPerspective(self)
      if str:
        self.manager.LoadPerspective(str)

    self.manager.Update()
        