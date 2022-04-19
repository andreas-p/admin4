# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.lib.ogl as wxOgl
import math
import wx
from wh import GetBitmap

BMP_BORDER=3
ARROWMARGIN=5

wxOgl.OGLInitialize()


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
   
   
class ExplainShape(wxOgl.BitmapShape):
  def __init__(self, bmpname, desc, tokenNo=-1, detailNo=-1):
    wxOgl.BitmapShape.__init__(self)
    self.kidCount=0
    self.totalShapes=0
    self.usedShapes=0
    self.upperShape=None
    self.description=desc
    self.condition=""
    self.detail=""
    self.SetBitmap(GetBitmap(bmpname, self))

    if tokenNo < 0:
      self.label=desc
    else:
      strList=desc.split(' ')
      self.label = strList[tokenNo]
      if detailNo < 0:
        self.description = desc
          
#      if detailNo > 0:
#        self.description=(self.description + " ".join(strList[0:detailNo])).lstrip()
#        self.detail=strList[detailNo]

  def __str__(self):
    return "%s(%d) %d" % (self.label, self.level, self.totalShapes)
  
  def GetLevel(self):
    return self.level
  
  def GetAverageCost(self):
    return (self.costHigh - self.costLow) / 2 + self.costLow
  
    
  def OnDraw(self, dc):
    bmp=self.GetBitmap()
    if not bmp.IsOk():
      return
    x=int(self.GetX() - bmp.GetWidth()/2)
    y=int(self.GetY() - bmp.GetHeight()/2)
    dc.DrawBitmap(bmp, x, y, True)
    dc.SetFont(self.GetCanvas().GetFont())
    w,_h=dc.GetTextExtent(self.label)
    x=self.GetX() - w/2
    y += bmp.GetHeight() + BMP_BORDER
    dc.DrawText(self.label, x, y)
      
  def GetStartPoint(self):
    pt=wx.RealPoint(self.GetX() + self.GetBitmap().GetWidth() / 2.0 + ARROWMARGIN, self.GetY())
    return pt
   
  def GetEndPoint(self, kidNo):
    if self.kidCount>1:
      koffs=round(self.GetBitmap().GetHeight() * 2. /3. * kidNo / (2*self.kidCount-2))
    else:
      koffs=0;
    _sh=self.GetHeight()
    _bh=self.GetBitmap().GetHeight()
    pt=wx.RealPoint(self.GetX() - self.GetBitmap().GetWidth() / 2.0 - ARROWMARGIN, self.GetY()+koffs)
    return pt
                        
  
  def OnLeftClick(self, _x, _y, _keys, _attachment):
    self.GetCanvas().ShowPopup(self)
  
  @staticmethod
  def Create(level, last, desc):
    costPos=desc.find("(cost=");
    if costPos>0:
      descr=desc[0:costPos]
    else:
      descr=desc
    strList=desc.split(' ')
    token=strList[0]
    if len(strList) > 1:
      token2=strList[1]
      if len(strList) > 2:
        token3=strList[2]
    if token == "Total":
      return None

    bmp={ "Result":        "ex_result",
          "Append":        "ex_append",
          "Nested":        "ex_nested",
          "Merge":         "ex_merge",
          "Materialize":   "ex_materialize",
          "Sort":          "ex_sort",
          "Group":         "ex_group",
          "Aggregate":     "ex_aggregate",
          "GroupAggregate":"ex_aggregate",
          "HashAggregate": "ex_aggregate",
          "Unique":        "ex_unique",
          "SetOp":         "ex_setop",
          "Limit":         "ex_limit",
          "Seek":          "ex_seek",
          }.get(token)
    if bmp:
      s= ExplainShape(bmp, descr)
    elif token == "Hash":
      if token2 == "Join":
        s= ExplainShape("ex_join", descr)
      else:
        if token3 == "Join":
          s= ExplainShape("ex_join", descr)
        else:
          s= ExplainShape("ex_hash", descr)

    elif token == "Subquery":
      s= ExplainShape("ex_subplan", descr, 0, 2)
    elif token == "Function" :
      s= ExplainShape("ex_result", descr, 0, 2)

    elif token == "Bitmap":
      if token2 == "Index":
        s= ExplainShape("ex_bmp_index", descr, 4, 3)
      else:
        s= ExplainShape("ex_bmp_heap", descr, 4, 3)
    elif token2 == "Scan":
      if token == "Index":
        s= ExplainShape("ex_index_scan", descr, 3, 2)
      elif token == "Tid":
        s= ExplainShape("ex_tid_scan", descr, 3, 2)
      else:
        s= ExplainShape("ex_scan", descr, 3, 2);
    else:
      s=ExplainShape("ex_unknown", descr)
    s.SetDraggable(False)
    s.level = level

    if costPos > 0:
      actPos = desc.find("(actual")
      if actPos > 0:
        s.actual = desc[actPos:]
        s.cost = desc[costPos:actPos-costPos]
      else:
        s.cost = desc[costPos:]
        
    w=50
    h=20

    bmp=s.GetBitmap();
    if w < bmp.GetWidth():
      w = bmp.GetWidth()

    s.SetHeight(bmp.GetHeight() + BMP_BORDER + h)
    s.SetWidth(w);

    s.upperShape = last;
    if last:
      s.kidNo = last.kidCount
      last.kidCount = last.kidCount+1
    else:
      s.kidNo = 0

    if costPos > 0:
      cl=desc[costPos+6:-1].split(' ')
      costs=cl[0].split('..')
      s.costLow=float(costs[0])
      s.costHigh=float(costs[1])
      s.width=int(cl[1].split('=')[1])
      s.rows=int(cl[2].split('=')[1])
    return s


class ExplainLine(wxOgl.LineShape):
  def __init__(self, fromShape, toShape):
    wxOgl.LineShape.__init__(self)
    self.SetCanvas(fromShape)
    self.width = int(math.log(fromShape.GetAverageCost()))
    if self.width > 10:
      self.width = 10
 
    self.startPoint=fromShape.GetStartPoint()
    self.endPoint=toShape.GetEndPoint(fromShape.kidNo)
    self.MakeLineControlPoints(2)
    self._lineControlPoints[0]=fromShape.GetStartPoint()
    self._lineControlPoints[1]=toShape.GetEndPoint(fromShape.kidNo)
    self.name="%s -> %s" %(fromShape.label, toShape.label)
    self.Initialise()
    
    fromShape.AddLine(self, toShape)


  def OnDraw(self, dc):
    if self._lineControlPoints:
      dc.SetPen(wx.BLACK_PEN)
      dc.SetBrush(wx.LIGHT_GREY_BRUSH)
      p0x,p0y=self.startPoint
      p3x,p3y=self.endPoint
      
      xd=(p3x-p0x)/3.
      p1x = p0x + xd-8
      p2x = p3x - xd+8

      width=self.width
      phi = math.atan2(p3y - p0y, p2x - p1x)
      offs = -width * math.tan(phi/2)
      arrow=4
      
      points=[]
      def append(x, y):
        points.append( (round(x), round(y)))

      append(p0x,              p0y-width)
      append(p1x-offs,         p0y-width)
      append(p2x-offs-arrow,   p3y-width)
      append(p3x-width-arrow,  p3y-width)
      append(p3x-width-arrow,  p3y-width-arrow)
      append(p3x,              p3y)
      append(p3x-width-arrow,  p3y+width+arrow)
      append(p3x-width-arrow,  p3y+width)
      append(p2x+offs-arrow,   p3y+width)
      append(p1x+offs,         p0y+width)
      append(p0x,              p0y+width)

      dc.DrawPolygon(points, 0, 0)
 
      
class ExplainCanvas(wxOgl.ShapeCanvas):
  def __init__(self, parent):
    wxOgl.ShapeCanvas.__init__(self, parent)
    self.SetDiagram(wxOgl.Diagram())
    self.GetDiagram().SetCanvas(self)
    self.SetBackgroundColour(wx.WHITE)
    self.lastShape=None
    self.Bind(wx.EVT_MOTION, self.OnMouseMove)

  def SetEmpty(self):
    self.GetDiagram().DeleteAllShapes()
    self.lastShape=None
    self.result=[]

  def GetResult(self):
    return self.result

  def SetData(self, rowset):
    self.SetEmpty()
    last=None
    maxLevel=0
    
    while rowset.HasMore():
      row1=rowset.Next()[0]
      self.result.append(row1)
      line=row1.strip()
      
      while True:
        if line.count('(') > line.count(')') and rowset.HasMore():
          row=rowset.Next()[0]
          self.result.append(row)
          line = "%s %s" % (line, row)
        else:
          break
      
      level = int((len(row1) - len(line) +4) / 6)

      if last:
        if level:
          if line.startswith("->  "):
            line=line[4:]
          else:
            last.condition=line
            continue
          
        while last and level <= last.GetLevel():
          last = last.upperShape   

      s=ExplainShape.Create(level, last, line)
      if not s:
        continue
      
      s.SetCanvas(self)
      self.InsertShape(s)
      s.Show(True)

      if level > maxLevel:
        maxLevel = level
      
      if not last:
        self.rootShape = s
      last=s

    x0 = int(self.rootShape.GetWidth()*1.5)
    y0 = int(self.rootShape.GetHeight()*0.6)
    xoffs = int(self.rootShape.GetWidth()*2.6)
    yoffs = int(self.rootShape.GetHeight()*1.2)

    lst=self.GetDiagram().GetShapeList()[:]
    for s in lst:
      if not s.totalShapes:
          s.totalShapes = 1
      if s.upperShape:
          s.upperShape.totalShapes += s.totalShapes
  
    lst.reverse()
    for s in lst:
      level=s.GetLevel()
      s.SetX(x0 + (maxLevel - level) * xoffs)
      upper = s.upperShape
      if upper:
        s.SetY(upper.GetY() + upper.usedShapes * yoffs)
        upper.usedShapes += s.totalShapes

        l=ExplainLine(s, upper)
        l.Show(True)
        self.AddShape(l)
      else:
        s.SetY(y0)

    PIXPERUNIT=20
    w=(maxLevel * xoffs + x0*2 + PIXPERUNIT - 1) / PIXPERUNIT
    h=(self.rootShape.totalShapes * yoffs + y0*2 + PIXPERUNIT - 1) / PIXPERUNIT

    self.SetScrollbars(PIXPERUNIT, PIXPERUNIT, w, h)
    self.SendSizeEvent()


  def OnMouseMove(self, evt):
    sx,sy=self.CalcUnscrolledPosition(evt.GetX(), evt.GetY())
    shape, _=self.FindShape(sx, sy)
    if shape and isinstance(shape, ExplainShape):
      if shape.costHigh == shape.costLow:
        cost="cost=%.2f" % shape.costLow
      else:
        cost="cost=%.2f .. %.2f" % (shape.costLow, shape.costHigh)
      lines=[]
      lines.append(shape.description)
      if shape.condition:
        lines.append(shape.condition)
      lines.append(cost)
      lines.append("rows=%d, size=%d" % (shape.width, shape.rows))
      self.SetToolTip("\n".join(lines))
    else:
      self.SetToolTip("")
    
