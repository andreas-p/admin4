# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx

try:
  import adm
  import logger
except:
  print ("ctl_adm: XRCED mode")
  adm=None
  
class ComboBox(wx.ComboBox):
  def __init__(self, parentWin, cid=-1, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0):
    wx.ComboBox.__init__(self, parentWin, cid, "", pos, size, style=style | wx.CB_DROPDOWN|wx.CB_READONLY)
    self.keys={}

  def InsertKey(self, pos, key, val):
    wid=wx.ComboBox.Insert(self, val, pos, key)
    self.keys[key] = wid
    return wid

  def AppendKey(self, key, val):
    wid=wx.ComboBox.Append(self, val, key)
    self.keys[key] = wid
    return wid

  def Append(self, stuff):
    """
    Append(stuff)
    
    stuff may be 
    - a dictionary 
    - a list of (key,val) tuples
    - a (key,val) tuple
    - a String
    """ 
    wid=None
    if isinstance(stuff, dict):
      for key in sorted(stuff.keys()):
        wid=self.AppendKey(key, stuff[key])
    elif isinstance(stuff, list):
      for data in stuff:
        if isinstance(data, (tuple, list)):
          wid=self.AppendKey(data[0], data[1])
        elif isinstance(data, str):
          wid=wx.ComboBox.Append(self, data)
          self.SetClientData(wid, None)
        else:
          logger.debug("unknown type to append to combobox: %s %s", type(data), data)
    elif isinstance(stuff, tuple):
      wid=self.AppendKey(stuff[0], stuff[1])
    elif isinstance(stuff, str):
      wid=wx.ComboBox.Append(self, stuff)
      self.SetClientData(wid, None)
    else:
      logger.debug("unknown type to append to combobox: %s %s", type(stuff), stuff)
    return wid

  def SetKeySelection(self, key):
    kid=self.keys.get(key)
    if kid != None:
      return self.SetSelection(kid)
    return -1

  def GetKeySelection(self):
    kid=self.GetSelection()
    if kid >= 0:
      return self.GetClientData(kid)
    return None
  
  
class ListView(wx.ListView):
  MARGIN=10
  ICONWITDH=20
  dlgConstant=None

  def __init__(self, parentWin, defaultImageName="", cid=-1, pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.LC_REPORT):
    _unused=style
    style=wx.LC_REPORT
    wx.ListView.__init__(self, parentWin, cid, pos, size, style)
    if adm:
      self.SetImageList(adm.images, wx.IMAGE_LIST_SMALL)
      self.defaultImageId=adm.images.GetId(defaultImageName)
    self.Bind(wx.EVT_MOTION, self.OnMouseMove)
    self.getToolTipTextProc=None
    self.getToolTipCol=None
    self.colInfos=[]

  def ClearAll(self):
    super(ListView, self).ClearAll()
    self.coldef=[]
    
    
  def GetToolTipText(self, tid):
    if self.getToolTipCol:
      return self.GetItemText(tid, self.getToolTipCol)
    return None

  def GetSelection(self):
    lst=[]
    item=self.GetFirstSelected()
    while item >= 0:
      lst.append(item)
      item=self.GetNextSelected(item)
    return lst


  def GetFocusText(self):
    item=self.GetFocusedItem()
    if item < 0:  return None
    return self.GetItemText(item, 0)
  
  def SetSelectFocus(self, sel):
    if sel == None: return
    if not isinstance(sel, int):
      sel=self.FindItem(0, sel)
    if sel >= 0:
      self.Focus(sel)
      self.Select(sel)

  def GetSelectionKeys(self):
    lst=[]
    item=self.GetFirstSelected()
    while item >= 0:
      lst.append(self.GetItemText(item, 0))
      item=self.GetNextSelected(item)
    return lst

  
  def RegisterToolTipProc(self, proc):
    if isinstance(proc, int):
      self.getToolTipCol=proc
      self.getToolTipTextProc=self.GetToolTipText
    else:
      self.getToolTipTextProc=proc

  def convert(self, x):
    if isinstance(x, str):
      w,_h=self.GetTextExtent(x)
      return w
    if x < 0:
      w,_h=self.GetSize()
      for i in range(self.GetColumnCount()):
        w -= self.GetColumnWidth(i)
      if w<20:
        w=20
      return w

    if not self.dlgConstant:
      w,_h=self.GetTextExtent('Mg')
      self.dlgConstant=w/2.
    return int(float(x)*self.dlgConstant+.9)

  class __ColumnExtractor:
    def __init__(self, proc, colname):
      def string(val):
        if val == None:
          return ""
        return str(val)
      self.colname=colname
      if proc:
        self.proc=proc
      else:
        self.proc=string
      
    def GetVal(self, row):
      if self.colname:
        val=row[self.colname]
        return self.proc(val)
      return self.proc(row)
    
  def AddExtractorInfo(self, colname=None, proc=None):
    self.colInfos.append(ListView.__ColumnExtractor(proc, colname))
    
  def AddColumnInfo(self, text, size=-1, colname=None, fmt=wx.LIST_FORMAT_LEFT, proc=None):
    self.AddColumn(text, size, fmt)
    self.AddExtractorInfo(colname, proc)
  
  def AddColumn(self, text, size=-1, fmt=wx.LIST_FORMAT_LEFT):
    if size in [None, -1, wx.LIST_AUTOSIZE]:
#      size=wx.LIST_AUTOSIZE
      size=self.GetClientSize().GetWidth();
      for i in range(self.GetColumnCount()):
        size -= self.GetColumnWidth(i)
    elif isinstance(size, (str, int)):
      size=self.convert(size) + self.MARGIN
      if not self.GetColumnCount():
        size += self.ICONWITDH
    return self.InsertColumn(self.GetColumnCount(), text, fmt, size);

  def CreateColumns(self, left, right=None, leftSize=-1):
    if right != None:
      if leftSize < 0:
        leftSize=rightSize=self.GetClientSize().GetWidth()/2;
        self.InsertColumn(0, left, wx.LIST_FORMAT_LEFT, leftSize);
        self.InsertColumn(1, right - self.ICONWIDTH, wx.LIST_FORMAT_LEFT, rightSize);
      else:
        self.AddColumn(left, leftSize)
        self.AddColumn(right, -1)
    else:
      self.AddColumn(left, -1)

  
  def AppendRow(self, values, icon=-1):
    vals=[]
    for colInfo in self.colInfos:
      vals.append(colInfo.GetVal(values))
    _row=self.AppendItem(icon, vals)

  
  def UpdateRow(self, row, values, icon=-1):
    vals=[]
    for colInfo in self.colInfos:
      vals.append(colInfo.GetVal(values))
    self.SetItemRow(row, vals)
    self.SetItemImage(row, icon)
      
  
  def Fill(self, valueList, idCol=0):
    """
    Fill(values, idCol=0)
    
    Updates Listview contents with the rows list.
    Each row contains a tuple of (columnValList, iconId) of only the columnValList
    idCol identifies the column index in the columnValList which contains the key
    """
    
    curRows = self.GetKeys()

    for values in valueList:
      if isinstance(values, tuple):
        icon=values[1]
        values=values[0]
      else:
        icon=-1
      key=str(values[idCol])
      if key in curRows:
        curRows.remove(key)
        row=self.FindItem(-1, key)
        self.UpdateRow(row, values, icon)
      else:
        self.AppendRow(values, icon)

    for key in curRows:
      row=self.FindItem(-1, key)
      if row >= 0:
        self.DeleteItem(row)


  def InsertItem(self, row, icon, vals):
    if icon < 0:
      icon=self.defaultImageId
    if isinstance(vals, tuple):
      vals=list(vals)
    elif not isinstance(vals, list):
      vals=[vals]
    if row < 0:
      row=self.GetItemCount()

    row=super(ListView, self).InsertItem(row, str(vals[0]), icon)

    for col in range(1, len(vals)):
      val=vals[col]
      if val == None:
        val=""
      val=str(val)
      super(ListView, self).SetItem(row, col, val)
    return row

  def AppendItem(self, icon, vals):
    return self.InsertItem(self.GetItemCount(), icon, vals)


  def GetKeys(self):
    l=[]
    for i in range(self.GetItemCount()):
      l.append(self.GetItemText(i, 0))
    return l
  
  def GetValue(self):
    l=[]
    for i in range(self.GetItemCount()):
      l.append(self.GetItemTuple(i))
    return l

  def SetItemRow(self, row, val, image=None):
    if isinstance(val, tuple):
      val=list(val)
    for col in range(len(val)):
      self.SetItem(row, col, str(val[col]))
    if image != None:
      self.SetItemImage(row, image)


  def GetItemTuple(self, row):
    if row < 0 or row >= self.GetItemCount():
      return None

    l=[]
    for col in range(self.GetColumnCount()):
      l.append(self.GetItemText(row, col))
    return tuple(l)


  def GetItemText(self, row, col):
    if row < 0 or row >= self.GetItemCount():
      return None
    if col < 0 or col >= self.GetColumnCount():
      return None
    return self.GetItem(row, col).GetText()

  def GetColname(self, col):
    return self.GetColumn(col).GetText()
      
  def OnMouseMove(self, ev):
    if self.getToolTipTextProc:
      cid, _unused_flags=self.HitTest(ev.GetPosition())

      if cid < 0:
        self.SetToolTip("")
      else:
        self.SetToolTip(self.getToolTipTextProc(cid))
  

xmlControlList={ 'whListView': ListView,
                 'whComboBox': ComboBox,
               }
