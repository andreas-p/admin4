# The Admin4 Project
# (c) 2013-2025 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx.xrc as xrc
import os, importlib

xmlControlList={}

def init(loaddir):
  names=os.listdir(loaddir)
  found=[]
  for name in names:
    path="%s/%s" % (loaddir, name)
    if os.path.isdir(path):
      pass
      # do not scan for CTL sources everywhere
      # If necessary, restrict to modXXX 
      #init(path)
    elif name.startswith("ctl_") and name.endswith( (".py", ".pyc")):
      name=name[:name.rfind('.')]
      if name not in found:
        found.append(name)
        mod=importlib.import_module(name, loaddir)
        xmlControlList.update(mod.xmlControlList)
    

def getControlClass(name):
  return xmlControlList.get(name)
  
class XmlResourceHandler(xrc.XmlResourceHandler):
  def DoCreateResource(self):
    cls=xmlControlList.get(self.GetClass())
    ctl=None
    if cls:
#      self.AddStyle("whEXTRAStyle", 4711)
      ctl=cls(self.GetParentAsWindow(), cid=self.GetID(), pos=self.GetPosition(), size=self.GetSize(), style=self.GetStyle())
      self.SetupWindow(ctl)
    return ctl

  def CanHandle(self, node):
    return node.GetAttribute('class', "") in xmlControlList

