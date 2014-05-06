# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import os

import wx
import wh
from wh import xlt, StringType
import logger


from controlcontainer import ControlContainer, MenuOwner  # @UnusedImport
from node import NodeId, Node, Collection, Group, ServerNode  # @UnusedImport
from page import PropertyPage, NotebookPage, NotebookControlsPage, NotebookPanel, PreferencePanel, getAllPreferencePanelClasses  # @UnusedImport
from controlcontainer import Dialog, CheckedDialog, PropertyDialog, ServerPropertyDialog  # @UnusedImport
from frame import Frame
from AdmDialogs import PasswordDlg


modules={}
mainRevision=0
mainDate=None
availableModules=[]

loaddir=None
trees={}
dialogs={}
app=None
appname=None
appTitle=None
mainframe=None

confirmDeletes=True
monthlyChecks=True
proxy=None

config=None

def getModule(instance):
  if instance.__module__ in modules:
    return instance.__module__
  else:
    dot=instance.__module__.rfind('.')
    if dot > 0:
      return instance.__module__[:dot]
    else:
      return ""


def GetProxies():
    if proxy:
      return { 'http': proxy, 'https': proxy }
    else:
      return None

def TextExtent(text):
  if isinstance(text, StringType):
    w,_h=mainframe.GetTextExtend(text)
    return w
  w,_h=mainframe.GetTextExtent("Mg")
  return int(w*(text+1)/2)

class ImageList(wx.ImageList):
  def __init__(self, w, h):
    wx.ImageList.__init__(self, w, h)
    self.list={}
    data=["%d %d 1 1" % (w,h), "  c None"]
    empty=""
    for _i in range(w):
      empty += " "
    for _i in range(h):
      data.append(empty)
    self.Add(wx.BitmapFromXPMData(data))
    self.list['']=0

    data=["%d %d 1 1" % (w,h), "  c #FFFFFF"]
    empty=""
    for _i in range(w):
      empty += " "
    for _i in range(h):
      data.append(empty)
    self.Add(wx.BitmapFromXPMData(data))
    self.list['white']=1

  def GetModuleId(self, inst, name):
    if hasattr(inst, "module"):
      mod=inst.module
    else:
      mod=getModule(inst)
    return self.GetId(os.path.join(mod, name))

  def GetJoinedId(self, ids):
    if len(ids) < 2:
      return ids[0]

    name="joined:%s" % "+".join(map(str, ids))
    id=self.list.get(name)
    if id:
      return id
    dc=wx.MemoryDC()

    w,h=self.GetSize(0)
    bmp=wx.EmptyBitmap(w,h)
    dc.SelectObject(bmp)

    # TODO should rewrite using wx.GraphicsContext
    if wx.Platform not in ("__WXMAC__"):
      b=self.GetBitmap(1)
      dc.DrawBitmap(b, 0, 0, True)
    
    for id in ids:
      if id > 0:
        b=self.GetBitmap(id)
        dc.DrawBitmap(b, 0, 0, True)
        #self.Draw(id, dc, 0,0)
      dc.DrawBitmap(b, 0, 0, True)
    dc.SelectObject(wx.NullBitmap)

    id=self.Add(bmp)
    self.list[name]=id
    return id

  def GetId(self, name):
    if name == None:
      return -1
    id=self.list.get(name)
    if id:
      return id

    id=-1
    bmp=wh.GetBitmap(name)
    if bmp:
      if bmp.GetSize() != self.GetSize(0):
        dcs=wx.MemoryDC()
        w1,h1=bmp.GetSize()
        dcs.SelectObject(bmp)
        dc=wx.MemoryDC()
        w,h=self.GetSize(0)
        bmpneu=wx.EmptyBitmap(w,h)
        dc.SelectObject(bmpneu)
        if wx.Platform not in ("__WXMAC__"):
          b=self.GetBitmap(1)
          dc.DrawBitmap(b, 0, 0, True)
        dc.StretchBlit(0, 0, w, h, dcs, 0,0,w1,h1)
        dc.SelectObject(wx.NullBitmap)
        dcs.SelectObject(wx.NullBitmap)
        id=self.Add(bmpneu)
        logger.debug("Bitmap has wrong format. Need %s, is %s", self.GetSize(0), bmp.GetSize())
      else:
        id=self.Add(bmp)
    else:
      fn="%s.ico" % name
      if os.path.exists(fn):
        id=self.AddIcon(wx.Icon(fn))
    self.list[name]=id
    return id

  def __getitem__(self, name):
    return self.GetId(name)

images=ImageList(16,16)
images48=ImageList(48,48)



##########################################################################

class admException(Exception):
  def __init__(self, node, txt, error=None):
    if error:
      msg=error
    else:
      msg=txt
    if node and hasattr(node, 'waitingFrame'):
      StopWaiting(node.waitingFrame, msg)
    else:
      StopWaiting(None, msg)
    if error !=  None:
      super(admException, self).__init__(txt, error)
    else:
      super(admException, self).__init__(txt)
    
class NoConnectionException(admException):
  def __init__(self, node, error=None):
    if error:
      txt="still broken connection: %s" % error
    else:
      txt="still broken connection"
    super(NoConnectionException, self).__init__(node, txt)
    self.servernode=node
    self.error=error


class ServerException(admException):
  def __init__(self, node, error):
    self.error=' '.join(error.splitlines())
    self.servernode=node

    txt="%s %s" % (node.shortname, node.name)
    super(ServerException, self).__init__(node, txt, error)


class ConnectionException(admException):
  def __init__(self, node, spot, error):
    self.servernode=node
    self.spot=spot
    self.error=error

    txt="%s connection: %s" % (spot, error)
    super(ConnectionException, self).__init__(node, txt)

    wx.MessageBox("%s: %s" % (spot, error), xlt("%s \"%s\"") % (node.typename, node.name))
    node.GetServer().IconUpdate()




#########################################################################
# global helper functions

def RegisterServer(settings):
  mainframe.servers.RegisterServer(settings)


def DisplayDialog(cls, parentWin, *params):
  id="%s%s" % (cls.__name__, params)
  dlg=dialogs.get(id)
  if dlg:
    dlg.Iconize(False)
    dlg.Raise()
  else:
    dlg=cls(parentWin, *params)
    dlg.dialogId = id
    dialogs[id]=dlg
    dlg.Go()
    dlg.SetUnchanged()
    dlg.OnCheck()
  dlg.Show()
  dlg.SetFocus()
  return dlg


def SetClipboard(data):
  wx.TheClipboard.Open()
  wx.TheClipboard.SetData(wx.TextDataObject(data))
  wx.TheClipboard.Close()
    
def GetCurrentFrame(wnd=None):
  if not wnd:
    wnd=wx.Window.FindFocus()
  while wnd and not isinstance(wnd, Frame):
    wnd=wnd.GetParent()
  return wnd

def SetStatus(text=None):
  GetCurrentFrame().SetStatus(text)

def GetCurrentTree(wnd=None):
  while wnd:
    if isinstance(wnd, wx.TreeCtrl):
      return wnd
    wnd=wnd.GetParent()

  frame=GetCurrentFrame()
  if frame and hasattr(frame, "tree"):
    return frame.tree
  return None


def AskPassword(parentWin, msg, caption, withRememberCheck=False):
#    dlg=wx.PasswordEntryDialog(parentWin, msg, caption)
# We might support "Remember" here
#    dlg=wx.TextEntryDialog(parentWin, msg, caption)
    dlg=PasswordDlg(parentWin, msg, caption)
    if not withRememberCheck:
      dlg['Remember'].Hide()
    passwd=None
    remember=False
    if dlg.ShowModal() == wx.ID_OK:
      passwd=dlg.Password
      remember=dlg.Remember
      
    dlg.Destroy()
    if withRememberCheck:
      return passwd, remember
    else:
      return passwd
  
  
def ConfirmDelete(msg, hdr, force=False):
  if confirmDeletes or force:
    rc=wx.MessageBox(msg, hdr, wx.YES_NO|wx.ICON_EXCLAMATION|wx.YES_DEFAULT)
    return rc == wx.YES
  else:
    return True


def StartWaiting(txt=None, mayAbort=False):
  frame=GetCurrentFrame()
  if frame:
    if hasattr(frame, 'tree') and frame.tree:
      node=frame.tree.GetNode()
      if node:
        node.waitingFrame=frame
    if not txt:
      txt=xlt("working...")
    frame.PushStatus(txt)
    if not mayAbort:
      wx.BeginBusyCursor()
      frame.MakeModal(True)
  try:
    wx.SafeYield()
  except:
    pass
  return frame


def StopWaiting(frame=None, txt=None):
  if not frame:
    frame=GetCurrentFrame()
  if frame:
    try:
      wx.EndBusyCursor()
    except:
      pass
    try:
      frame.PopStatus()
    except:
      pass
    frame.MakeModal(False)
    if txt:
      frame.SetStatus(str(txt).splitlines()[0])
