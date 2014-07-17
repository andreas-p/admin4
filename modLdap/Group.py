# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


nodeinfo=[]
from SpecificEntry import SpecificEntry
from Entry import Entry
from . import AttrVal
from wh import xlt
import wx, adm



class Groups(SpecificEntry):
  name=xlt("Groups")

  def __init__(self, dlg, notebook, resname=None):
    SpecificEntry.__init__(self, dlg, notebook, resname)
    self.Bind("AddGroup", self.OnAddGroup)
    self.Bind("DelGroup", self.OnDelGroup)
    self['MemberList'].Bind(wx.EVT_LIST_COL_END_DRAG, self.OnListColResize)

  class GroupInfo:
    def __init__(self, dn, info):
      self.dn=dn.decode('utf8')
      self.info=info
      displayname=info.get('displayName')
      if displayname:
        self.name=displayname[0].decode('utf8')
      else:
        self.name=info['cn'][0].decode('utf8')

      self.desc=("\n".join(info.get('description', []))).decode('utf8')
      self.objectClass=info['structuralObjectClass'][0].decode('utf8').lower()


    def GetIcon(self):
      return -1

    def GetParamValue(self, name=None):
      if not name:
        name=self.GetParamName()
      return self.info[name]


    def GetParamName(self):
      if not hasattr(self, "paramName"):
        for k in self.info.keys():
          if k.lower() in ['member', 'memberuid', 'uniquemember']:
            self.paramName=k
            break;
      return self.paramName


    def WantUid(self):
      return self.objectClass in ["posixgroup"]


  def addMember(self, dn):
    group=self.allGroups[dn]
    self['MemberList'].AppendItem(group.GetIcon(), [group.name, group.dn, group.desc])


  def Go(self):
    SpecificEntry.Go(self)

    self.allGroups={}
    self.memberOf=[]

    memberList=self['MemberList']
    memberList.AddColumn(xlt("Name"), 20)
    memberList.AddColumn("DN", 40)
    memberList.AddColumn(xlt("Description"))

    adm.config.restoreListviewPositions(memberList, self)


    knownDnGroupClasses=["groupOfNames", "groupOfUniqueNames", "mailGroup", "posixGroup"]
    knownUidGroupClasses=["posixGroup"]

    clsFilter=""
    for kgc in knownDnGroupClasses:
      if clsFilter:
        clsFilter="|(objectClass=%s)(%s)" % (kgc, clsFilter)
      else:
        clsFilter="objectClass=%s" % kgc

    uidVal=self.dialog.GetAttrib("uid")

    if uidVal:
      for kgc in knownUidGroupClasses:
        if kgc not in knownDnGroupClasses:
          clsFilter="|(objectClass=%s)(%s)" % (kgc, clsFilter)

    baseDn=self.GetServer().dn
    for dn, info in self.GetConnection().SearchSub(baseDn, "(%s)" % clsFilter, "* structuralObjectClass"):
      self.allGroups[dn] = Groups.GroupInfo(dn, info)

    if self.dialog.dn:
      userFilter="|(member=%s)(uniquemember=%s)" % (self.dialog.dn, self.dialog.dn)
      if uidVal:
        userFilter="|(%s)(memberuid=%s)" % (userFilter, uidVal.GetValue()[0])
  
      filter="(&(%s)(%s))" % (clsFilter, userFilter)
      for res in self.GetConnection().SearchSub(baseDn, filter, "dn"):
        dn=res[0].decode('utf8')
        self.memberOf.append(dn)
        self.addMember(dn)



  def OnAddGroup(self, evt):
    groupdns=self.allGroups.keys()
    memberList=self['MemberList']
    for row in range(0, memberList.GetItemCount()):
      dn=memberList.GetItemText(row, 1)
      groupdns.remove(dn)

    groups=[]
    for dn in groupdns:
      groups.append(self.allGroups[dn].name)

    dlg=wx.MultiChoiceDialog(self, xlt("Add group"), xlt("Add group membership"), groups)
    if dlg.ShowModal() == wx.ID_OK:
      for i in dlg.GetSelections():
        self.addMember(groupdns[i])

  def OnListColResize(self, evt):
    adm.config.storeListviewPositions(self['MemberList'], self)

  def OnDelGroup(self,evt):
    memberList=self['MemberList']
    lst=memberList.GetSelection()
    lst.reverse()
    for row in lst:
      _dn=memberList.GetItemText(row, 1)
      memberList.DeleteItem(row)

  def Save(self):

    uidval=self.dialog.GetAttrib("uid")
    if uidval:
      uid=uidval.GetValue()[0]
    else:
      uid=None
    addList=[]
    delList=self.memberOf[:]
    memberList=self['MemberList']
    for row in range(0, memberList.GetItemCount()):
      dn=memberList.GetItemText(row, 1)
      if dn in delList:
        delList.remove(dn)
      else:
        addList.append(dn)

    for dn in addList:
      group=self.allGroups[dn]
      n=group.GetParamName()
      chgList=[AttrVal(n, group.GetParamValue(n))]

      if uid and group.WantUid():
        chgList[0].AppendValue(uid)
      else:
        chgList[0].AppendValue(self.dialog.dn)

      self.dialog.GetConnection().Modify(dn, chgList)

    for dn in delList:
      group=self.allGroups[dn]

      n=group.GetParamName()
      chgList=[AttrVal(n, group.GetParamValue(n))]

      if uid and group.WantUid():
        chgList[0].RemoveValue(uid)
      else:
        chgList[0].RemoveValue(self.dialog.dn)

      self.dialog.GetConnection().Modify(dn, chgList)
SpecificEntry.AddClass(Groups)



class Members(SpecificEntry):
  name="Members"
  def Go(self):
    SpecificEntry.Go(self)
SpecificEntry.AddClass(Members)


# TODO
#class GroupOfNames(SpecificEntry):
#  canClasses="groupOfUniqueNames"
#SpecificEntry.AddClass(GroupOfNames)
#Entry.addNewEntryClass(GroupOfNames)

class Group(SpecificEntry):
  name=xlt("Posix Group")
  typename=xlt("Group")
  shortname=xlt("Group")
  icon="Group"
  canClasses="posixGroup"
  startClasses="posixGroup"


  def __init__(self, dlg, notebook, resname=None):
    SpecificEntry.__init__(self, dlg, notebook, resname)
    self.memberUidOid=self.GetServer().GetOid("memberUid")
    self.Bind("AddMember", self.OnAddMember)
    self.Bind("DelMember", self.OnDelMember)
    self.Bind("GenerateGid", self.OnGenerate)
    lv=self['Members']
    lv.AddColumn(xlt("User Id"), 20)
    lv.AddColumn(xlt("Description"))
    lv.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnListColResize)
    lv.Bind(wx.EVT_MOTION, self.OnMouseMove)


  def OnGenerate(self, evt):
    if self.GetIdFromMax("posixAccount", "gidNumber"):
      self['GenerateGid'].Disable()


  def OnListColResize(self, evt):
    adm.config.storeListviewPositions(self['Members'], self)

  def Go(self):
    SpecificEntry.Go(self)
    attrval=self.dialog.attribs.get(self.memberUidOid)
    adm.config.restoreListviewPositions(self['Members'], self)
    if attrval:
      self.SetValue(attrval)
    if self.dialog.node:
      self['cn'].Disable()
      self['GenerateGid'].Disable()

  def DelValue(self, attrval):
    if attrval.GetOid() == self.memberUidOid:
      self['Members'].clear()
    else:
      SpecificEntry.DelValue(self, attrval)


  def SetValue(self, attrval):
    if attrval.GetOid() == self.memberUidOid:
      lv=self['Members']
      uids=attrval.GetValue()[:]
      for row in range(lv.GetItemCount()-1, -1, -1):
        if not lv.GetItemText(row, 0) in uids:
          lv.DeleteItem(row)
      for uid in uids:
        if lv.FindItem(-1, uid) < 0:
          lv.AppendItem(-1, uid)
    else:
      SpecificEntry.SetValue(self, attrval)


  def OnMouseMove(self, ev):
    lv=self['Members']
    row, _=lv.HitTest(ev.GetPosition())
    if row in range(lv.GetItemCount()):
      if lv.GetItemData(row):
        return
      lv.SetItemData(row, -1)
      uid=lv.GetItemText(row, 0)
      res=self.GetServer().SearchSubConverted("(uid=%s)" % uid, "uid cn displayName")
      if len(res) == 1:
        _dn, info=res[0]
        name=info.get("displayName", info.get("cn"))[0]
        lv.SetStringItem(row, 1, name)


  def OnAddMember(self, evt):
    lv=self['Members']

    res=self.GetServer().SearchSubConverted("(uid=*)", "uid cn displayName")

    candidates=[]
    for _dn, info in res:
      name=info.get("displayName", info.get("cn"))[0]
      uid=info['uid'][0]
      if lv.FindItem(-1, uid) < 0:
        candidates.append("%s %s" % (uid, name))
    dlg=wx.MultiChoiceDialog(self, xlt("Add member"), xlt("Add member to group"), candidates)
    if dlg.ShowModal() == wx.ID_OK:
      uids=[]
      for row in range(lv.GetItemCount()):
        uids.append(lv.GetItemText(row, 0))
      for i in dlg.GetSelections():
        cr=candidates[i].split()
        uid=cr[0]
        row=lv.AppendItem(-1, uid)
        lv.SetStringItem(row, 1, " ".join(cr[1:]))
        lv.SetItemData(row, -1)
        uids.append(uid)

      self.dialog.SetValue(self.memberUidOid, uids, self)

  def OnDelMember(self, evt):
    lv=self['Members']
    uids=self.dialog.attribs[self.memberUidOid].GetValue()[:]
    rows=lv.GetSelection()
    rows.reverse()
    for row in rows:
      uid=lv.GetItemText(row, 0)
      uids.remove(uid)
      lv.DeleteItem(row)
    self.dialog.SetValue(self.memberUidOid, uids, self)

  @staticmethod
  def New(parentWin, parentNode):
    adm.DisplayDialog(Entry.Dlg, parentWin, None, parentNode, Group)
SpecificEntry.AddClass(Group)
Entry.addNewEntryClass(Group)


class OrganizationalUnit(SpecificEntry):
  name=xlt("Organizational Unit")
  shortname=xlt("Org Unit")
  icon="OrgUnit"
  canClasses="organizationalUnit"
  startClasses="organizationalUnit"
SpecificEntry.AddClass(OrganizationalUnit)
Entry.addNewEntryClass(OrganizationalUnit)
