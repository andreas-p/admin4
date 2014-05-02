# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import os, time, datetime, shutil
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
    if not isinstance(keycode, int):
      keycode=ord(keycode)
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


def copytree(src, dst, symlinks=False, ignore=None, replace=True):
  """
  this is mostly a copy of shutil.copytree, except it will optionally
  not barf if target files/directories already exists.
  """
  names = os.listdir(src)
  if ignore is not None:
      ignored_names = ignore(src, names)
  else:
      ignored_names = set()

  if not replace or not os.path.exists(dst):
    os.makedirs(dst)

  errors = []
  for name in names:
      if name in ignored_names:
          continue
      srcname = os.path.join(src, name)
      dstname = os.path.join(dst, name)
      try:
          if symlinks and os.path.islink(srcname):
              linkto = os.readlink(srcname)
              os.symlink(linkto, dstname)
          elif os.path.isdir(srcname):
              copytree(srcname, dstname, symlinks, ignore, replace)
          else:
              # Will raise a SpecialFileError for unsupported file types
              if replace and os.path.exists(dstname):
                os.unlink(dstname)
              shutil.copy2(srcname, dstname)
      # catch the Error from the recursive copytree so that we can
      # continue with other files
      except shutil.Error, err:
          errors.extend(err.args[0])
      except EnvironmentError, why:
          errors.append((srcname, dstname, str(why)))
  try:
      shutil.copystat(src, dst)
  except OSError, why:
      if shutil.WindowsError is not None and isinstance(why, shutil.WindowsError):
          # Copying file access times may fail on Windows
          pass
      else:
          errors.append((src, dst, str(why)))
  if errors:
      raise shutil.Error, errors

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


  
