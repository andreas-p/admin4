# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import wx.grid
NULLSTRING="(NULL)"


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
    
    if rowcount<0:
      rowcount=0
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
          val=unicode(val)
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
          return None
      for row in rows:
        v=[]
        for col in cols:
          v.append(quoted(self.GetCellValue(row, col)))
        vals.append(commaChar.join(v))
      return lfChar.join(vals)
