# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

nodeinfo=[]

import adm, logger
import wx
from wh import xlt

class SpecificEntry(adm.NotebookPanel):
  name=xlt("Specific")
  canClasses=""

  def __init__(self, dlg, notebook, resname=None):
    adm.NotebookPanel.__init__(self, dlg, notebook, resname)

    for ctl in self._ctls.values():
      if "objectclass" in ctl.flags:
        if self.GetServer().GetClassOid(ctl.name):
          self.Bind(ctl.name, self.OnCheckObjectClass)
        else:
          ctl.Disable()
      else:
        oid=self.GetServer().GetOid(ctl.name)
        if oid:
          if "rdn" in ctl.flags:
            if self.dialog.rdnOid:
              ctl.Disable()
            else:
              self.dialog.rdnOid=oid
          ctl.ldapOid=oid
          self.Bind(ctl.name, self.OnChangeLdapValue)
        else:
          if "modLdap" in ctl.flags:
            ctl.ldapOid=None
            logger.debug("No OID found for %s", ctl.name)


  def OnCheckObjectClass(self, ev):
    if isinstance(ev, wx.Window):
      ctlCheck=ev
    else:
      ctlCheck=ev.GetEventObject()
    if ctlCheck:
      how=ctlCheck.GetValue()
      name=ctlCheck.name
      _objectClass=ctlCheck.name

      self.Freeze()
      skip=True
      for cname in self._ctlList:
        ctl=self.ctl(cname)
        if skip:
          if ctl == ctlCheck:
            skip=False
        else:
          if hasattr(ctl, "flags"):
            if "objectclass" in ctl.flags:
              break;
            if how:
              how2=how
              if "modLdap" in ctl.flags:
                if not hasattr(ctl, "ldapOid") or not ctl.ldapOid in self.dialog.mayAttribs:
                  how2=False
              ctl.Enable(how2)
              if hasattr(ctl, "labelCtl"):
                ctl.labelCtl.Enable(how2)
          ctl.Enable(how)

      needObjectClassUpdate=False
      if how:
        if not self.dialog.HasObjectClass(name):
          self.dialog.objectClasses.append(str(name))
          needObjectClassUpdate=True
      else:
        needObjectClassUpdate=self.dialog.RemoveObjectClass(name)


      if needObjectClassUpdate:
        self.dialog.UpdateObjectClasses()
        for ctl in self._ctls.values():
          if hasattr(ctl, "ldapOid"):
            self.OnChangeLdapValue(ctl)
      self.Thaw()


  def Go(self):
    for ctl in self._ctls.values():
      if hasattr(ctl, "flags"):
        if hasattr(ctl, "ldapOid"):
          attrval=self.dialog.attribs.get(ctl.ldapOid)
          if attrval:
            attrval.items[self]=ctl
            self.SetValue(attrval)
          else:
            if not ctl.ldapOid in self.dialog.mayAttribs:
              logger.debug("Ignoring Control %s: not available in mayAttribs", ctl.name)
              ctl.Disable()
              if hasattr(ctl, "labelCtl"):
                ctl.labelCtl.Disable()

        elif "objectclass" in ctl.flags:
          ctl.SetValue(self.dialog.HasObjectClass(ctl.name))
          self.OnCheckObjectClass(ctl)


  def Check(self):
    ok=True
    for ctlname in self._ctlList:
      ctl=self.ctl(ctlname)
      if not ctl.IsEnabled():
        continue
      if hasattr(ctl, "flags"):
        if hasattr(ctl, "labelCtl"):
          labeltext=ctl.labelCtl.GetLabel()
        else:
          labeltext=ctl.name

        if "must" in ctl.flags:
          ok=self.dialog.CheckValid(ok, self._getattr(ctl), xlt("%s needs to be filled") % labeltext)
        ok=self.dialog.CheckValid(ok, self._isvalid(ctl), xlt("%s has invalid format") % labeltext)
        if not ok:
          return False
    return ok


  def OnChangeLdapValue(self, ev):
    if isinstance(ev, wx.Window):
      ctl=ev
    else:
      ctl=ev.GetEventObject()
    if ctl:

      value=self._getattr(ctl)
      if "rdn" in ctl.flags:
        rdn="%s=%s" % (self.GetServer().GetName(ctl.ldapOid), value)
        self.dialog.rdn=rdn
      if value or "null" in ctl.flags:
        if "multi" in ctl.flags:
          value = value.splitlines()
        self.dialog.SetValue(ctl.ldapOid, value, self)
      else:
        self.dialog.DelValue(ctl.ldapOid, self)
      if "cn" in ctl.flags:
        self.dialog.SetValue("cn", value, self)

      self.dialog.OnCheck()


  def SetValue(self, attrVal):
    ctl=attrVal.items.get(self)
    if not ctl:
      for c in self._ctls.values():
        if hasattr(c, "ldapOid"):
          if c.ldapOid == attrVal.GetOid():
            attrVal.items[self]=c
            ctl=c
            break;
    if ctl:
      if "multi" in ctl.flags:
        value = "\n".join(attrVal.GetValue())
      elif attrVal.IsSingleValue():
        value=attrVal.GetValue()
      else:
        value=attrVal.GetValue()[0]
      if value != self._getattr(ctl):
        self._setattr(ctl, value)


  def DelValue(self, attrVal):
    ctl=attrVal.items.get(self)
    if ctl:
      self._setattr(ctl, None)

  allSpecificClasses={}

  @classmethod
  def AddClass(self, panelClass):
    self.allSpecificClasses[panelClass.__name__.lower()] = panelClass


  @classmethod
  def FitLevel(self, _node):
    return 1 # if cbjectClass already matched

  @classmethod
  def GetSpecificClass(self, node):
    candidates=[]

    for cls in self.allSpecificClasses.values():
      if isinstance(cls.canClasses, str):
        cls.canClasses=cls.canClasses.split()
      for clsCand in cls.canClasses:
        if node.HasObjectClass(clsCand):
          candidates.append(cls)
    if not candidates:
      logger.debug("No Candidates for %s", node.objectClasses)
      return None
    if len(candidates) == 1:
      return candidates[0]

    fitLevel=0
    bestFitClass=None
    for cls in candidates:
      fl=cls.FitLevel(node)
      if fl > fitLevel:
        fitLevel=fl
        bestFitClass=cls

    return bestFitClass


  @classmethod
  def GetClasses(self, primaryClass):
    classes=[]
    if primaryClass:
#      if isinstance(primaryClass, StringType):
#       pcn=primaryClass.lower()
  #    else:
      pcn=primaryClass.__name__.lower()

      clList=panelClassDef.get(pcn)
      if clList:
        if isinstance(clList, str):
          clList=clList.split()
        for panelClass in clList:
          resname=None
          if isinstance(panelClass, str):
            pstr=panelClass.split(":")
            pc=self.allSpecificClasses.get(pstr[0].lower())
            if pc:
              panelClass=pc
            else:
              logger.debug("PanelClass %s not found", panelClass)
              continue
            if len(pstr) > 1:
              resname=pstr[1]
          classes.append((panelClass, resname))
    return classes

#import Posix, Samba, Group
#dummy=Posix
#dummy=Samba
#dummy=Group

panelClassDef={
  'useraccount': "UserAccount:UserAccountItw Personal Contact Groups ShadowAccount SambaAccount",
  'group': "Group SambaGroupMapping",
  'sambadomain': "SambaDomain",
  }