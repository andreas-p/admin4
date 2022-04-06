# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import wx.grid, wx.aui
from wh import xlt, ToolBar, floatToTime, localTimeMillis
from ._pgsql import pgQuery, quoteIdent, quoteValue

HMARGIN=5
VMARGIN=5

if wx.VERSION < (4,1,2):
  class StringTable(wx.grid.GridTableBase):
    def __init__(self, rows, cols):
      super(StringTable, self).__init__()
      self.rows=rows
      self.cols=cols
      self.data={}
      self.colnames={}
    
    def GetNumberCols(self):
      return self.cols
    def GetNumberRows(self):
      return self.rows
    def GetColsCount(self):
      return self.cols
    def GetRowsCount(self):
      return self.rows
    def GetValue(self, row, col):
      return self.data.get((row,col))
    def SetValue(self, row, col, value):
      self.data[(row,col)]=value
    def CanHaveAttributes(self):
      return False
    def SetColLabelValue(self, col, text):
      self.colnames[col]=text
    def GetColLabelValue(self, col):
      return self.colnames[col]
else:
    StringTable=wx.grid.GridStringTable

#################################################################################


class EditTable(wx.grid.GridTableBase):
  def __init__(self, grid, tableSpecs, rowset):
    wx.grid.GridTableBase.__init__(self)
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


  def Delete(self, rows):
    """
    Delete(rows) expects rows in reverse sorted order
    """
    query=pgQuery(self.tableSpecs.tabName, self.tableSpecs.GetCursor())
    allWhere=[]
    for row in rows:
      wh=[]
      for colname in self.tableSpecs.keyCols:
        wh.append("%s=%s" % (quoteIdent(colname), quoteValue(self.rows[row][colname])))
      allWhere.append("(%s)" % " AND ".join(wh))
    query.AddWhere("\n    OR ".join(allWhere))
    rc=query.Delete()
    
    self.grid.Freeze()
    self.grid.BeginBatch()
    for row in rows:
      self.grid.DeleteRows(row, 1, True)

#        msg=wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED)

    self.grid.EndBatch()
    self.grid.ForceRefresh()
    self.grid.Thaw()
    return rc
    
    
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
            query.AddWhere(colname, self.currentRow[colname])
            
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
        
        if self.hasoids:
          returning=None
        else:
          returning=",".join(map(quoteIdent, self.tableSpecs.keyCols))
                             
        returned=query.Insert(returning)
        if returned != None:
          if self.hasoids:
            self.currentRow['oid'] = returned
          else:
            if isinstance(returned, tuple):
              for i in range(len(returned)):
                self.currentRow[self.tableSpecs.keyCols[i]] = returned[i]
            else:
              self.currentRow[self.tableSpecs.keyCols[0]] = returned

        self.rows.append(self.currentRow)
        self.grid.ProcessTableMessage(wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED, 1))

        self.grid.GetParent().SetStatusText(xlt("%d rows") % len(self.rows), SqlFrame.STATUSPOS_ROWS)
      rc=True
    else:
      rc=False
    self.Revert()
    return rc

  
  def GetColDef(self, col):
    return self.tableSpecs.colSpecs.get(self.colNames[col])

  
  def DeleteRows(self, row, count):
    for _ in range(count):
      del self.rows[row]
    self.grid.ProcessTableMessage(wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED, row, count))
    return True
  
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
    self.toolbar=ToolBar(self, 32)
    self.CreateStatusBar(4, wx.STB_SIZEGRIP)
    w,_h=self.StatusBar.GetTextExtent('Mg')
    self.SetStatusWidths([-1, 5*w,6*w,5*w])

  def OnCut(self, _evt):
    wnd=wx.Window.FindFocus()
    if wnd:
      wnd.Cut()
  
  def OnCopy(self, _evt):
    wnd=wx.Window.FindFocus()
    if wnd:
      wnd.Copy()
  
  def OnPaste(self, _evt):
    wnd=wx.Window.FindFocus()
    if wnd:
      wnd.Paste()

  def pollWorker(self):
    while self.worker.IsRunning():
      elapsed=localTimeMillis() - self.startTime
      self.SetStatusText(floatToTime(elapsed/1000.), self.STATUSPOS_SECS)
      wx.Yield()
      if elapsed < 200:
        wx.MilliSleep(10);
      elif elapsed < 10000:
        wx.MilliSleep(100);
      else:
        wx.MilliSleep(500)
      wx.Yield()
    
    elapsed=localTimeMillis() - self.startTime
    if elapsed:
      txt=floatToTime(elapsed/1000.)
    else:
      txt="0 ms"
    self.SetStatusText(txt, self.STATUSPOS_SECS)
    return txt
    
    
  def restorePerspective(self, skipConfig=False):
    if not skipConfig:
      desc=adm.config.GetPerspective(self)
      if desc:
        self.manager.LoadPerspective(desc)

    self.manager.Update()
        