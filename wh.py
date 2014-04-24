# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import os, time, datetime
import logger
loaddir=None

def SetLoaddir(d):
  global loaddir
  loaddir=d

StringType=(str, unicode)

class AcceleratorHelper:
  def __init__(self, frame):
    self.list=[]
    self.frame=frame
    
  def Add(self, flags, keycode, cmd):
    if not isinstance(cmd, int):
      cmd=self.frame.GetMenuId(cmd)
    self.list.append(wx.AcceleratorEntry(flags, keycode, cmd) )
  
  def GetTable(self):
    return wx.AcceleratorTable(self.list)
  
  def Realize(self):
    self.frame.SetAcceleratorTable(self.GetTable())
  
  
    
def modPath(name, mod):
  """
  str modPath(filename, module)
  
  prepend module's path to filename
  """
  if not isinstance(mod, StringType):
    mod=mod.__module__
  ri=mod.rfind('.')
  if ri > 0:
    path=os.path.join(loaddir, mod[0:ri].replace('.', '/'), name)
    return path
  return name
    

def GetBitmap(name, module=None):
  """
  wx.Bitmap GetBitmap(bmpName, module=None)
  
  Get a bitmap from a file, possibly prepending the module's path
  """
  if module:
    name=modPath(name, module)
  else:
    name=os.path.join(loaddir, name)

  for ext in ["png"]:
    fn="%s.%s" % (name, ext)
    if os.path.exists(fn):
      return wx.Bitmap(fn)

  for ext in ["xpm"]:
    fn="%s.%s" % (name, ext)
    if os.path.exists(fn):
      data=[]
      f=open(fn)
      for line in f:
        if line.startswith('"'):
          data.append(line[1:line.rfind('"')])
      f.close()
      return wx.BitmapFromXPMData(data)

  for ext in ["ico"]:
    fn="%s.%s" % (name, ext)
    if os.path.exists(fn):
      return wx.BitmapFromIcon(wx.Icon(fn))
  return None


class Timer(wx.Timer):
  timerId=100
  def __init__(self, wnd, proc):
    wx.Timer.__init__(self, wnd, Timer.timerId)
    wx.EVT_TIMER(wnd, Timer.timerId, proc)
    Timer.timerId += 1

class Menu(wx.Menu):
  def AppendOneMenu(self, menu, txt, help=None):
    if not help:
      help=""
    ic = menu.GetMenuItemCount()
    if ic > 1:
      return self.AppendSubMenu(menu, txt, help)
    if ic == 1:
      i=menu.GetMenuItems()[0]
      item=self.Append(i.GetId(), i.GetItemLabel(), i.GetHelp())
      return item
    return None


  def Dup(self):
    menu=Menu()
    for i in self.GetMenuItems():
      item=menu.Append(i.GetId(), i.GetItemLabel(), i.GetHelp())
      item.SetBitmap(i.GetBitmap())
    return menu

  def getRepr(self, m, indentstr):
    strings=[]
    for i in m.GetMenuItems():
      if i.IsSeparator():
        strings.append("%s---" % indentstr)
      else:
        strings.append("%s%d: %s" % (indentstr, i.GetId(), i.GetItemLabel()))
        if i.IsSubMenu():
          strings.extend(self.getRepr(i.GetSubMenu(), "%s  " & indentstr))
    return strings

  def __str__(self):
    return "\n".join(self.getRepr(self, ""))

class Validator():
  validators={}

  @staticmethod
  def Get(name):
    return Validator.validators.get(name.lower())

  def __init__(self, ctl, unused_params=None):
    self.chars=[]
    self.ctl=ctl

  def OnChar(self, ev):
    if self.ctl.GetInsertionPoint() >= self.len:
      return
    keycode = int(ev.GetKeyCode())
    if keycode < 256 and keycode >31:
      if not chr(keycode) in self.chars:
        return
    ev.Skip()

  def GetValue(self):
    return self.ctl.GetValue()

  def SetValue(self, val):
    self.ctl.SetValue(unicode(val))


class UIntValidator(Validator):
  def __init__(self, ctl, params):
    Validator.__init__(self, ctl)
    if len(params):
      self.len=params[0]
    else:
      self.len=99
    self.chars="0123456789"
    ctl.Bind(wx.EVT_CHAR, self.OnChar)

  def GetValue(self):
    v=self.ctl.GetValue()
    if v:
      return int(v)
    return None

  def SetValue(self, val):
    if val or isinstance(val, int):
      self.ctl.SetValue(unicode(int(val)))
    else:
      self.ctl.SetValue("")

class IntValidator(UIntValidator):
  def __init__(self, ctl, params):
    UIntValidator.__init__(self, ctl, params)

  def OnChar(self, ev):
    keycode = int(ev.GetKeyCode())
    if keycode < 256 and keycode >31:
      if self.ctl.GetInsertionPoint() == 0:
        a,e=self.ctl.GetSelection()
        if e == a:
          if self.ctl.GetValue()[0:1]  == '-':
            return
        if chr(keycode) == '-':
          ev.Skip()
          return
    Validator.OnChar(self, ev)

  def GetValue(self):
    v=self.ctl.GetValue()
    if v and v != "-":
      return int(v)
    return None

Validator.validators['uint']=UIntValidator
Validator.validators['int']=IntValidator


class MacValidator(Validator):
  def __init__(self, ctl, unused_params):
    Validator.__init__(self, ctl)
    self.len=17
    self.chars="0123456789abcdef"
    ctl.Bind(wx.EVT_CHAR, self.OnChar)

  def IsValid(self):
    return len(self.ctl.GetValue() == self.len)

  def GetValue(self):
    v=self.ctl.GetValue()
    if len(v) == self.len:
      return v.lower().replace('.', ':').replace('-', ':')
    return None

  def OnChar(self, ev):
    keycode = int(ev.GetKeyCode())

    if keycode < 256 and keycode >31:
      if self.ctl.GetInsertionPoint() == 17:
        return
      if len(self.ctl.GetValue()) == 17:
        a,e=self.ctl.GetSelection()
        if a == e:
          return
      if self.ctl.GetInsertionPoint() in (2,5,8,11,14):
        if not chr(keycode) in ".-:":
          return
      else:
        if not chr(keycode) in self.chars:
          return

    ev.Skip()

Validator.validators['mac']=MacValidator


class TimestampValidator(Validator):
  def __init__(self, ctl, unused_params):
    Validator.__init__(self, ctl)

  def getFormat(self):
    tmp=self.ctl.GetValue()
    if len(tmp) < 12:
      return "%Y-%m-%d"
    elif len(tmp.split(':')) < 3:
      return "%Y-%m-%d %H:%M"
    else:
      return "%Y-%m-%d %H:%M:%S"

  def IsValid(self):
    value=self.ctl.GetValue()
    if value:
      try:
        time.strptime(value, self.getFormat())
      except:
        return False
    return True


  def GetValue(self):
    try:
      ts=time.strptime(self.ctl.GetValue(), self.getFormat())
      return time.mktime(ts)
    except:
      return None


  def SetValue(self, value):
    if value:
      self.ctl.SetValue(prettyDate(value, True))
    else:
      self.ctl.SetValue("")

class IntTimestampValidator(TimestampValidator):
  def GetValue(self):
    value=TimestampValidator.GetValue(self)
    if value != None:
      return int(value)
    return None

Validator.validators['timestamp']=TimestampValidator
Validator.validators['int_ts']=IntTimestampValidator

class BoolValidator(Validator):
  def __init__(self, ctl, params):
    Validator.__init__(self, ctl)
    self.TrueValue=None
    self.FalseValue=None

    if len(params):
      try:
        self.TrueValue=int(params[0])
      except:
        self.TrueValue=params[0]
      if len(params) > 1:
        try:
          self.FalseValue=int(params[1])
        except:
          self.FalseValue=params[1]


  def GetValue(self):
    if self.TrueValue == self.FalseValue:
      return self.ctl.GetValue()
    elif self.ctl.GetValue():
      return self.TrueValue
    else:
      return self.FalseValue

  def SetValue(self, value):
    if self.TrueValue == self.FalseValue:
      self.ctl.SetValue(value)
    elif self.TrueValue != None:
      self.ctl.SetValue(value == self.TrueValue)
    else:
      self.ctl.SetValue(value != self.FalseValue)


Validator.validators['bool'] = BoolValidator


def YesNo(b):
  if b:
    return xlt("Yes")
  else:
    return xlt("No")


def xlt(s): # translate
  return s
  t=wx.GetTranslation(s)
  # if dict set and t == s: log untranslated
  return t


class ParamDict(dict):
  def __init__(self, str=None):
    dict.__init__(self)
    if str:
      self.setString(str)

  def setString(self, items):
    if not isinstance(items, list):
      items=items.split()
    for item in items:
      s=item.split('=')
      if len(s) == 2:
        self[s[0]] = s[1]
      else:
        logger.debug("ParamString %s invalid: %s", items, item)

  def getList(self):
    l=[]
    for key, val in self.items():
      l.append("%s=%s" % (key, val))
    return l

  def getString(self):
    return " ".join(self.getList())

def restoreSize(unused_name, unused_defSize=None, unused_defPos=None):
  size=(600,400)
  pos=(50,50)
  return size,pos


decimalSeparators=",."

def splitValUnit(value):
  num=""
  unit=""
  canDot=True
  for c in value:
    if  unit:
      unit += c
    else:
      if c in decimalSeparators and canDot:
        num+=c
        canDot=False
      elif c in "1234567890":
        num+=c
      else:
        unit+=c

  return num, unit.strip()


def strToIsoDate(val):
  zpos=val.find('Z')
  if zpos > 0:
    l=zpos
  else:
    l=len(val)
  if l < 8:
    return val
  elif l < 10:
    fmtstr="%Y%m%d"
  elif l < 14:
    fmtstr="%Y%m%d%H%M"
  else:
    l=14
    fmtstr="%Y%m%d%H%M%S"

  try:
    ts=time.strptime(val[:l], fmtstr)
  except Exception as e:
    logger.error("Invalid datetime format %s: %s", val, e)
    return val

  try:
    gmt=time.mktime(ts)
  except Exception as e:
    logger.error("Invalid datetime format %s: %s", val, e)
    return val

  if zpos > 0:
    # adjust time: interpreted as local but actually gmt
    ts=time.localtime(gmt)
    if ts.tm_isdst > 0:
      gmt -= time.altzone
    else:
      gmt -= time.timezone

    zpi=val[zpos+1:]
    if zpi:
      try:
        gmt += 3600*zpi
      except:
        logger.error("Invalid time zone %s", val)
        pass
  return prettyDate(gmt, True)


def utc2local(value):
  ts=time.strptime(value, "%Y-%m-%d %H:%M:%S")
  gmt=time.mktime(ts)
  if time.localtime(gmt).tm_isdst > 0:
    gmt -= time.altzone
  else:
    gmt -= time.timezone
  return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(gmt))

def isoDateToStr(value):
  ts=time.strptime(value, "%Y-%m-%d %H:%M:%S")
  gmt=time.gmtime(time.mktime(ts))
  return time.strftime("%Y%m%d%H%M%SZ", gmt)


def timeToFloat(value):
  factors={ "ms": .001, "us": .001*.001, "ns": .001*.001*.001, "s": 1.,
            "m": 60., "h": 60*60., "d":24*60*60. }
  num, unit=splitValUnit(value)

  if not num:
    return 0.
  val=float(num)
  unit = unit.lower()
  if unit:
    u=unit.split(' ')
    unit=u[0]
    factor=factors.get(unit)
    if not factor:
      logger.debug("Factor for unit %s not found", unit)
      return None
    else:
      val *= factor
    if len(u) > 1:
      add=timeToFloat(" ".join(u[1:]))
      if add == None:
        return None
      val += add
  return val

def floatToTime(value, nk=1):
  if value:
    if hasattr(value, 'total_seconds'):
      val=value.total_seconds()
    else:
      val=float(value)
  else:
    val=0.
  if val < 0:
    val = -val
    vz="-"
  else:
    vz=""

  if val >= 90:
    fmt="%%.0%df" % nk
    sec= val % 60
    val -= sec
    val = int(val+.1)/60
    min = val % 60
    val /= 60
    hour= val % 24
    day=val/24

    if day:
      if nk < 0:
        if not min:
          if not hour:
            return "%dd" % day
          else:
            return "%dd %dh" % (day, hour) 
      return "%dd %dh %dm" % (day, hour, min)
    elif hour:
      if nk < 0:
        if not sec:
          if not min:
            return "%dh" % hour
          else:
            return "%dh %dm" % (hour, min)
      return "%dh %dm %ds" % (hour, min, int(sec))
    elif min:
      if nk < 0 and not sec:
        return "%dm" % min
      return "%dm %ds" % (min, int(sec))
    else:
      return fmt%sec
  elif not val:
    val=0.
    unit="s"
  elif val > .2:
    if val < 90:
      unit="s"
  else:
    val *= 1000.
    if val > .2:
      unit="ms"
    else:
      val *= 1000
      if val > .2:
        unit="us"
      else:
        val *= 1000
        unit="ns"

  if nk < 0:
    nk=0
  fmt="%%s%%.0%df %%s" % nk
  return fmt % (vz, val, unit)


def prettyTime(val, nk=1):
  return floatToTime(timeToFloat(val), nk)

def prettyDate(val, long=True):
  if isinstance(val, datetime.datetime):
    val=val.timetuple()
  if not isinstance(val, time.struct_time):
    val=time.localtime(val)
  if long:
    return time.strftime("%Y-%m-%d %H:%M:%S", val)
  else:
    return time.strftime("%Y-%m-%d", val)


def sizeToFloat(value):
  factors={ "kb":  1000., "mb":  1000*1000, "gb":  1000*1000*1000., "tb":  1000*1000*1000*1000,
            "k":   1024., "m":   1024*1024, "g":   1024*1024*1024.,   "t": 1024*1024*1024*1024,
            "kib": 1024., "mib": 1024*1024, "gib": 1024*1024*1024., "tib": 1024*1024*1024*1024, }

  num,unit=splitValUnit(value)
  if not num:
    return 0.
  val=float(num)
  unit = unit.lower()
  if unit:
    factor=factors.get(unit)
    if not factor:
      logger.debug("Factor for unit %s not found", unit)
      return None
    else:
      val *= factor
  return val


def prettySize(val):
  if not isinstance(val, (int,float)):
    val=sizeToFloat(val)
  return floatToSize(val)

def floatToSize(val):
    if not val:
      return "0"

    unit=""
    val = float(val)/ 1024.
    if val < 2048:
      unit="KiB"
    else:
      val /= 1024.
      if val < 1500:
        unit="MiB"
      else:
        val /= 1024.
        if val < 1500:
          unit="GiB"
        else:
          val /= 1024.
          unit="TiB"
    if val < 15:
      return "%0.02f %s" % (val, unit)
    elif val < 150:
      return "%0.01f %s" % (val, unit)
    else:
      return "%0.0f %s" % (val, unit)


  
