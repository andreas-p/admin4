# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


nodeinfo=[]
from SpecificEntry import SpecificEntry
from Entry import Entry
from wh import xlt

class _SambaRidObject:
  def __init__(self):
    self.Bind("RidGen", self.OnRidGen)
    self.Bind("SambaRid", self.OnRidChange)

  def initDomains(self):
    sdn=self.ctl('sambaDomainName')
    sds=self.ctl('sambaDomainSid')

    if (sdn and not sdn.GetCount()) or (sds and not sds.GetCount()):
      res=self.GetServer().SearchSubConverted("(objectClass=sambaDomain)", "sambaDomainName sambaSid")
      for _dn, info in res:
        if sds:
          sds.AppendKey(info['sambasid'][0], info['sambadomainname'][0])
        else:
          id=sdn.Append(info['sambadomainname'][0])
          sdn.SetClientData(id, info['sambasid'][0])


  def generateRid(self, posixAttr, ridbase, domsid, domname):
    posixNumber=self.dialog.GetAttrValue(posixAttr)
    if posixNumber:
      res=self.GetServer().SearchSub("(sambaDomainName=%s)" % domname, "sambaAlgorithmicRidBase")
      if len(res) == 1:
        _dn,info=res
        ridbase=int(info['sambaalgorithmicbase'][0])
        ridbasetext="sambaAlgorithmicRidBase (%d)" % ridbase
      else:
        ridbasetext="RID base %d" % ridbase

      rid=posixNumber*2+ridbase
      self.sambaRid=rid
      self.dialog.SetStatus(xlt("Samba SID generated from posix %s and %s") % (posixAttr, ridbasetext))
    else:
      res=self.GetServer().SearchSubConverted("(sambaSid=*)", "sambaSid")

      maxsid=""
      for _dn, info in res:
        testsid=info['sambasid'][0]
        if testsid.startswith(domsid):
          maxsid=max(maxsid, testsid)

      if maxsid:
        maxrid=int(maxsid.split('-')[7])
        self.sambaRid=maxrid+1
        self.dialog.SetStatus(xlt("Samba SID generated from highest used Samba SID + 1"))
      else:
        self.sambaRid=None
        self.dialog.SetStatus(xlt("No SIDs in Domain %s assigned so far") % domname)


  def OnRidChange(self, ev=None):
    if self.sambaRid:
      sid="%s-%d" % (self.sambaDomainSid, self.sambaRid)
      self.SambaSid=sid
      self.dialog.SetValue("sambaSid", sid, self)
    else:
      self.sambaSid=xlt("<not set>")
      self.dialog.SetValue("sambaSid", None, self)

    if ev:
      self.dialog.OnCheck()


class SambaComputer(SpecificEntry, _SambaRidObject):
  name=xlt("Samba Computer")
  shortname=xlt("Computer")
  canClasses="account sambaSamAccount"
  startClasses="sambaSamAccount posixAccount"

  @classmethod
  def FitLevel(self, node):
    if node.name.endswith("$"):
      return 999
    else:
      return -1

  def __init__(self, dlg, notebook, resname=None):
    SpecificEntry.__init__(self, dlg, notebook, resname)
    _SambaRidObject.__init__(self)
#    self.Bind("sambaDomainName", self.OnChangeDomain)



SpecificEntry.AddClass(SambaComputer)
Entry.addNewEntryClass(SambaComputer)

class SambaAccount(SpecificEntry, _SambaRidObject):
  name=xlt("Samba")

  def __init__(self, dlg, notebook, resname=None):
    SpecificEntry.__init__(self, dlg, notebook, resname)
    _SambaRidObject.__init__(self)
    self.Bind("sambaDomainName", self.OnChangeDomain)
    self.Bind("CantChangePassword PasswordNeverExpires MustChangePassword AccountEnabled", self.OnCheckboxes)


  def Go(self):
    self.initDomains()

    SpecificEntry.Go(self)
    if not self.sambaSamAccount:
      return

    if self.dialog.node and self.sambaDomainName:
      if self.sambaSid:
        ss=self.sambaSid.split('-')
        self.sambaDomainSid="-".join(ss[:1])
        self.sambaRid = ss[7]
      self.EnableControls("sambaDomainName sambaRid ridGen", False)

    self.OnChangeDomain()
    self.updateFlags()


  def OnRidGen(self, evt):
    domsid="%s-" % self.sambaDomainSid
    domname=self.sambaDomainName
    self.generateRid("uidNumber", 1000, domsid, domname)


  def OnChangeDomain(self, ev=None):
    self['sambaPrimaryGroupSID'].Clear()
    self['sambaPrimaryGroupSID'].AppendKey("", "")

    sdn=self.ctl('sambadomainname')
    id=sdn.FindString(self.sambaDomainName)

    if id <0:
      self.sambaDomainSid=None
      return
    else:
      self.sambaDomainSid=sdn.GetClientData(id)

    domsid="%s-" % self.sambaDomainSid

    res=self.GetServer().SearchSubConverted("(objectClass=sambaGroupMapping)", "cn sambaSid")
    for _dn, info in res:
      sid=info['sambasid'][0]
      if sid.startswith(domsid):
        self['sambaPrimaryGroupSID'].AppendKey(sid, info['cn'][0])

    self.dialog.SetValue("sambaDomainName", self.sambaDomainName)
    if self.sambaRid:
      self.OnRidChange(ev)
    elif ev:
      self.dialog.OnCheck()


  def SetValue(self, attrval):
    SpecificEntry.SetValue(self, attrval)
    self.updateFlags()


  def DelValue(self, attrval):
    SpecificEntry.DelValue(self, attrval)
    self.updateFlags()


  def updateFlags(self):
    flags=self.dialog.GetAttrValue("sambaAcctFlags")
    if flags:
      self.AccountEnabled= not "D" in flags
      self.PasswordNeverExpires= "X" in flags

    self.CantChangePassword = (self.dialog.GetAttrValue("sambaPwdCanChange") > 0)
    pwmc=self.dialog.GetAttrValue("sambaPwdMustChange")
    self.MustChangePassword = (pwmc == 0)
    self.OnCheckboxes()


  def OnCheckboxes(self, ev=None):
    if not self.sambaSamAccount:
      return

    if self['CantChangePassword'].IsEnabled():
      self['MustChangePassword'].Enable(not self.CantChangePassword)

    def setFlag(id, how):
      if how:
        if self.flags.find(id) < 0:
          self.flags = self.flags + id
      else:
        self.flags = self.flags.replace(id, '')


    self.flags=self.dialog.GetAttrValue("sambaAcctFlags")
    if self.flags:
      self.flags=self.flags[1:-1]
    else:
      self.flags=""
    setFlag('D', not self.AccountEnabled)
    setFlag('X', self.PasswordNeverExpires)
    self.dialog.SetValue("sambaAcctFlags", "[%s]" % self.flags, self)

    if self.CantChangePassword:
      self.dialog.SetValue("sambaPwdCanChange", 2147480000, self)
    else:
      self.dialog.DelValue("sambaPwdCanChange", self)
      if self.MustChangePassword:
        self.dialog.SetValue("sambaPwdMustChange", 0, self)
      else:
        self.dialog.DelValue("sambaPwdMustChange", self)
    if ev:
      self.dialog.OnCheck()

SpecificEntry.AddClass(SambaAccount)


smbWellKnownGroups={
  # User
  #500 Domain Administrator
  #501 Domain Guest
  #502 Domain KRBTGT
  # Groups
  512: xlt("Domain Admins"),
  513: xlt("Domain Users"),
  514: xlt("Domain Guests"),
  515: xlt("Domain Computers"),
  516: xlt("Domain Controllers"),
  517: xlt("Domain Certificate Admins"),
  518: xlt("Domain Schema Admins"),
  519: xlt("Domain Enterprise Admins"),
  520: xlt("Domain Policy Admins"),
  # Aliases
  544: xlt("Builtin Admins"),
  545: xlt("Builtin Users"),
  546: xlt("Builtin Guests"),
  547: xlt("Builtin Power Users"),
  548: xlt("Builtin Account Operators"),
  549: xlt("Builtin System Operators"),
  550: xlt("Builtin Print Operators"),
  551: xlt("Builtin Backup Operators"),
  552: xlt("Builtin Replicator"),
  553: xlt("Builtin RAS Servers"),
}

smbGroupTypes={
  2: xlt("Domain Group"),
  4: xlt("Local Group"),
  5: xlt("Alias"),
  }

class SambaGroupMapping(SpecificEntry, _SambaRidObject):
  name=xlt("Samba")
  canClasses="sambaGroupMapping"

  def __init__(self, dlg, notebook, resname=None):
    SpecificEntry.__init__(self, dlg, notebook, resname)
    _SambaRidObject.__init__(self)
    self.Bind("sambaDomainSid", self.OnChangeDomain)

  def OnRidGen(self, evt):
    domsid="%s-" % self.sambaDomainSid
    domname=self.sambaDomainName
    self.generateRid("gidNumber", 1001, domsid, domname)


  def Check(self):
    if self.SambaGroupMapping:
      ok=True
      ok=self.dialog.CheckValid(ok, self.sambaDomainSid, xlt("Select Samba Domain first"))
      if not ok:
        return False
    return SpecificEntry.Check(self)

  def Go(self):
    self.initDomains()

    SpecificEntry.Go(self)
    if not self.sambaGroupMapping:
      return

    if self.dialog.node and self.sambaSid:
      ss=self.sambaSid.split('-')
      self.sambaRid = ss[7]
      self.sambaDomainSid='-'.join(ss[:-1])
      self.sambaDomainName = self.sambaDomainSid
      self.EnableControls("sambaDomainSid sambaRid ridGen", False)
      wkg=smbWellKnownGroups.get(self.sambaRid)
      if wkg:
        self.GroupTypeLabel=xlt("Well Known Group")
        self.GroupType=xlt(wkg)
      else:
        sgt=smbGroupTypes.get(self.dialog.GetAttrValue("sambaGroupType"))
        if sgt:
          self.GroupType=xlt(sgt)
        else:
          self.GroupType=xlt("Domain Group")
    else:
      self.dialog.SetValue("sambaGroupType", 2)
      self.GroupType=xlt("Domain Group")

    self.OnChangeDomain()



  def OnChangeDomain(self, ev=None):
    self.sambaDomainName=self['sambadomainsid'].GetValue()

    if self.sambaRid:
      self.OnRidChange(ev)
    elif ev:
      self.dialog.OnCheck()

SpecificEntry.AddClass(SambaGroupMapping)


class SambaDomain(SpecificEntry):
  name=xlt("Samba Domain")
  shortname=xlt("Domain")
  icon="Domain"
  canClasses="sambaDomain"


  def Go(self):
    SpecificEntry.Go(self)
#    self.EnableObjectClassControls(True)


SpecificEntry.AddClass(SambaDomain)
Entry.addNewEntryClass(SambaDomain)

