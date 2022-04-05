# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import wx
import time
from wh import prettyDate

class Validator():
  @staticmethod
  def Get(name):
    return Validator.validators.get(name.lower())

  def __init__(self, ctl, unused_params=None):
    self.chars=[]
    self.ctl=ctl

  def OnChar(self, ev):
    keycode = int(ev.GetKeyCode())
    if keycode < 256 and keycode >31:
      if not chr(keycode) in self.chars:
        return
      a,e=self.ctl.GetSelection()
      if a == e:
        l=len(self.ctl.GetValue())
        if l >= self.len:
          return
    ev.Skip()

  def GetValue(self):
    return self.ctl.GetValue()

  def SetValue(self, val):
    self.ctl.SetValue(str(val))


class UIntValidator(Validator):
  def __init__(self, ctl, params):
    Validator.__init__(self, ctl)
    if len(params):
      self.len=int(params[0])
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
      self.ctl.SetValue(str(int(val)))
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

Validator.validators = {
                        'uint' : UIntValidator,
                        'int':   IntValidator,
                        'bool':  BoolValidator,
                        'timestamp': TimestampValidator,
                        'int_ts': IntTimestampValidator,
                        'mac': MacValidator
                        }
