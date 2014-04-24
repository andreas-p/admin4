# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


nodeinfo=[]
from SpecificEntry import SpecificEntry
from Entry import Entry
from wh import xlt
import wx, adm


class UserAccount(SpecificEntry):
  name=xlt("Account")
  typename=xlt("LDAP User Account")
  shortname=xlt("User")
  icon="User"
  canClasses="inetorgperson"
  startClasses="inetOrgPerson"

  @classmethod
  def GetClassIconName(self, node):
    if node.HasObjectClass("sambaSAMAccount"):
      return "SamUser"
    elif node.HasObjectClass("posixAccount"):
      return "PosixUser"
    return self.icon

  @staticmethod
  def New(parentWin, parentNode):
    adm.DisplayDialog(Entry.Dlg, parentWin, None, parentNode, UserAccount)

SpecificEntry.AddClass(UserAccount)
Entry.addNewEntryClass(UserAccount)



class ShadowAccount(SpecificEntry):
  name=xlt("Posix/Shadow")
  def __init__(self, dlg, notebook, resname=None):
    SpecificEntry.__init__(self, dlg, notebook, resname)
    self.Bind("Expires", wx.EVT_CHECKBOX, self.OnExpire)
    self.Bind("GenerateUid", self.OnGenerate)

  def Go(self):
    SpecificEntry.Go(self)
    self.OnExpire()

  def OnGenerate(self, evt):
    if self.GetIdFromMax("posixAccount", "uidnumber"):
      self['GenerateUid'].Disable()


  def Check(self):
    ok=SpecificEntry.Check(self)
    
    if self.dialog.HasObjectClass("posixAccount"):
      if not self.uidNumber and self.GetServer().GetIdGeneratorStyle():
        dn=self.GetServer().GetSambaUnixIdPoolDN()
        if not dn:
          if not self.dialog.HasObjectClass("sambaSamAccount"):
            ok=self.dialog.CheckValid(ok, dn, xlt("Need sambaUnixIdPoolDN configured for this server or Samba Account data"))
        
    return ok
  
  
  def OnExpire(self, ev=None):
    if self.shadowAccount:
      self.EnableControls("shadowExpire shadowWarning", self.Expires)
      if not self.Expires:
        self.shadowExpire=99999
        self.shadowWarning=None
    if ev:
      self.dialog.OnCheck()
SpecificEntry.AddClass(ShadowAccount)



class Contact(SpecificEntry):
  name=xlt("Contact")
SpecificEntry.AddClass(Contact)

class Personal(SpecificEntry):
  name=xlt("Personal")
SpecificEntry.AddClass(Personal)

