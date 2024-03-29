# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

nodeinfo=[]

import adm, logger
import wx
from wh import xlt
from . import ConvertResult

class SpecificEntry(adm.NotebookPanel):
  name=xlt("Specific")
  canClasses=""

  def __init__(self, dlg, notebook, resname=None):
    adm.NotebookPanel.__init__(self, dlg, notebook, resname)

    for ctl in self._ctls.values():
      if "objectclass" in ctl.flags:
        if self.GetServer().GetClassOid(ctl.name):
          self.Bind(ctl, self.OnCheckObjectClass)
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
          self.Bind(ctl, self.OnChangeLdapValue)
        else:
          if "modLdap" in ctl.flags:
            ctl.ldapOid=None
            logger.debug("No OID found for %s", ctl.name)
    self.smbDomains={}


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
              if "ldap" in ctl.flags:
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
          hasClass=self.dialog.HasObjectClass(ctl.name)
          ctl.SetValue(hasClass)
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
        for flag in ctl.flags:
          if flag.startswith('copy='):
            var=flag[5:]
            if not self[var] or not self.dialog.node:
              self.dialog.SetValue(var, value, self)
      else:
        self.dialog.DelValue(ctl.ldapOid, self)
      

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
      val=self._getattr(ctl)
      if val:
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
    if node.dn == node.GetServer().adminLdapDn:
      return AdminConfigEntry
    candidates=[]

    for cls in self.allSpecificClasses.values():
      if isinstance(cls.canClasses, str):
        cls.canClasses=cls.canClasses.split()
      for clsCand in cls.canClasses:
        if node.HasObjectClass(clsCand):
          candidates.append(cls)
    if not candidates:
      logger.debug("No specific class for objectClass %s", node.objectClasses)
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
  def GetClasses(self, server, primaryClass):
    classes=[]
    if primaryClass:
      pcn=primaryClass.__name__

      clList=server.GetPanelClasses(pcn)
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


  def GetIdFromMax(self, objectClass, attrName):
    if self.GetServer().GetIdGeneratorStyle():
      # using SambaUnixIdPool
      dn=self.GetServer().GetSambaUnixIdPoolDN()
      if not dn:
        if hasattr(self.dialog, "sambaDomainName"):
          dn=self.smbDomains.get(self.dialog.sambaDomainName)
          if not dn:
            res=self.GetServer().SearchSubConverted(["objectClass=sambaDomain", "sambaDomainName=%s" % self.dialog.sambaDomainName ])
            if res:
              dn=res[0][0]
              self.smbDomains[self.dialog.sambaDomainName] = dn
        else:
          self.dialog.SetStatus(xlt("Either sambaUnixIdPoolDN must be configured or a samba domain specified."))
          return
      if dn:
        res=ConvertResult(self.GetConnection().SearchBase(dn, "(objectClass=sambaUnixIdPool)", attrName))
        if res:
          sid=int(res[0][1].get(attrName.lower())[0])
          self.dialog.SetValue(attrName, sid)
          self.GetConnection().Modify(dn, {attrName: sid+1})
          return True
        else:
          self.dialog.SetStatus(xlt("Couldn't read %s from %s") % (attrName, dn))
          return False
    else:
      # using max+1 method
      maxId=0
      res=self.GetServer().SearchSubConverted(["objectClass=%s" % objectClass, "%s=*" % attrName], attrName)
      for _dn, info in res:
        uid=int(info[attrName][0])
        maxId = max(maxId, uid)
      self.dialog.SetValue(attrName, maxId+1)
      self.dialog.SetStatus("Generated %(attr)s from highest used %(attr)s" % {"attr": attrName})
    return False

    
class AdminConfigEntry(SpecificEntry):
  name="Admin4 Configuration Data"
  shortname="Admin4Config"
  icon="Server"
