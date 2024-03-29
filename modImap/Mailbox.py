# The Admin4 Project
# (c) 2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import shlexSplit, xlt, Menu, floatToSize, prettyDate, prettySize, sizeToFloat
import wx
import re
from ._imap import GetImapDate, decodeUtf7, encodeUtf7

squatAnnotation='/vendor/cmu/cyrus-imapd/squat'


class Mailbox(adm.Node):
  typename="IMAP Mailbox"
  shortname="Mailbox"
  deleteDisable=False
  

  def splitMbInfo(self, line):
    parts=shlexSplit(line, ' ')
    separator=parts[-2]
    mailbox=parts[-1]
    flags=parts[:-2]
    flags[0] = flags[0][1:]
    flags[-1] = flags[-1][:-1]
    return (mailbox, separator, flags)
  
  def __init__(self, parentNode, line):
    name, self.separator, self.flags = self.splitMbInfo(line)
    self.mailboxPath=name
    parts=shlexSplit(self.mailboxPath, self.separator)
    if len(parts) > 1:
      name=parts[-1]
    name=decodeUtf7(name)
    super(Mailbox, self).__init__(parentNode, name)
    if len(parts) == 2 and parts[0] == "user":
      self.GetServer().userList.append(name)


  def GetIcon(self):
    if self.CanSelect():  icon="Mailbox"
    else:                 icon="MailboxNoselect"
    return self.GetImageId(icon)
    
  def MayHaveChildren(self):
    return not self.flags or 'HasChildren' in self.flags
  
  def CanDelete(self):
    return self.myrights and ('x' in self.myrights or 'c' in self.myrights())
  
  def CanAdmin(self):
    return self.myrights and ('a' in self.myrights)
  
  def CanSelect(self):
    return not self.flags or not "Noselect" in self.flags

  @staticmethod 
  def GetInstances(parentNode):
    instances=[]
    
    if isinstance(parentNode, Mailbox):
      pattern="%s%s%%" % (parentNode.mailboxPath, parentNode.separator)
    else:
      pattern="%%"
    mblist=parentNode.GetConnection().List("", pattern)
    if mblist:
      for line in mblist:
        instances.append(Mailbox(parentNode, line))

    return instances
  

  def RefreshVolatile(self, force=False):
    self.acl=self.GetConnection().GetAcl(self.mailboxPath)
    self.annotations=self.GetConnection().GetAnnotations(self.mailboxPath)
    self.myrights=self.GetConnection().MyRights(self.mailboxPath)
    self.quota = self.GetConnection().GetQuota(self.mailboxPath)
    if force:
      mblist=self.GetConnection().List("", self.mailboxPath)
      if mblist:
        _, self.separator, self.flags = self.splitMbInfo(mblist[0])
    self.deleteDisable = not self.CanSelect or not (self.CanAdmin() or self.CanDelete())


  def GetProperties(self):
    if not self.properties:
      self.RefreshVolatile(True)
      
      self.properties=[
                       ( xlt("Name"), self.name),
                       ( xlt("Mailbox path"), self.mailboxPath),
                       ( xlt("Flags"), ", ".join(self.flags))
                       ]

      if self.CanSelect():
        self.AddProperty(xlt("My rights"), self.myrights)
      if self.annotations:
        self.AddProperty(xlt("Comment"), self.annotations.Get('/comment'))
        lu=self.annotations.Get('/lastupdate')
        if lu:
          self.AddProperty(xlt("Last update"), prettyDate(GetImapDate(lu)))
# need that?
#      chk=(self.annotations.Get('/check') ==  "true")
#      self.AddYesNoProperty(xlt("Check"), chk)
#      if chk:
#        self.AddProperty(xlt("Check period"), self.annotations.Get('/checkperiod'))

        sz=self.annotations.Get('/size')
        if sz != None:
          self.AddSizeProperty(xlt("Size"), sz)
          
        squat=self.annotations.Get(squatAnnotation)
        if squat != None:
          self.AddProperty(xlt("Squat"), squat)
        if self.quota:
          items=[]
          for resource, quota in self.quota.items():
            root, filled, total = quota
            if root == self.mailboxPath:
              items.append(xlt("%s: %s of %s") % (resource, floatToSize(filled, 1024), floatToSize(total, 1024)))
            else:
              items.append(xlt("%s: %s of %s  (root=%s)") % (resource, floatToSize(filled, 1024), floatToSize(total, 1024), root) )
          self.AddChildrenProperty(items, xlt("Quota"), -1)
        else:
          self.AddProperty(xlt("Quota"), xlt("none"))

      if self.acl:
        imageid=self.GetImageId("User")
        for user, acl in self.acl.items():
          self.properties.append((user, acl, imageid))

    return self.properties


  class MailboxAcl(adm.CheckedDialog):
    # http://tools.ietf.org/html/rfc4314
    
    rightDict={ 'l': (xlt("lookup"), xlt("mailbox is visible to list and subscribe")),
                'r': (xlt("read"), xlt("mailbox contents may be read")),
                's': (xlt("seen"), xlt("may set seen flag on mailbox")),
                'w': (xlt("write"), xlt("may set other flags on mailbox")),
                'i': (xlt("insert"), xlt("add messages to mailbox")),
                'p': (xlt("post"), xlt("send mail to submission address")),
                'k': (xlt("create mailbox"), xlt("create mailbox or use as move mailbox target parent mailbox")),
                'x': (xlt("delete mailbox"), xlt("delete or move mailbox")),
                't': (xlt("delete message"), xlt("set deleted flag")),
                'e': (xlt("expunge"), xlt("expunge deleted messages from mailbox when closing")),
                'a': (xlt("administer"), xlt("administer mailbox acl")),
                'c': (xlt("    create (obsolete)"), xlt("obsolete/implementation dependent for k or kx")),
                'd': (xlt("    delete (obsolete)"), xlt("obsolete/implementation dependent for xte or te")),
#                'n': (xlt("annotation"), xlt("manage annotations")),
               }

    rightList="lrswipkxteacd"
    
    def Go(self, user=None, acl=None, knownUsers=None):
      self.User=user
      self.knownUsers=knownUsers
      self.statusbar.Show()
      
      if user:
        self['User'].Disable()
        self['Rights'].GetValue = self['Rights'].GetChecked
      else:
        sv=self.node.GetServer()
        if sv.user not in sv.userList:
          self['User'].Append(sv.user)
        self['User'].Append("anyone")
          
           
        for user in sv.userList:
          if self.nameValid(user):
            self['User'].Append(user)
      
      self.Bind('User Rights')
      self.Bind('RoRights', self.OnRoClick)
      self.Bind('RwRights', self.OnRwClick)
      self.Bind('AllRights', self.OnAllClick)
      self.Bind('NoRights', self.OnNoClick)
      self.Bind(wx.EVT_MOTION, self.OnMouseMoveRights)
      
      for right in self.rightList:
        i=self['Rights'].Append("%s   %s" % (right, xlt(self.rightDict[right][0])))
        if acl and right in acl:
          self['Rights'].Check(i)

      self.SetUnchanged()
      self.OnCheck()

    def OnMouseMoveRights(self, evt):
      pt=evt.GetPosition() - self['Rights'].GetPosition()
      mid=self['Rights'].HitTest(pt)

      if mid < 0:txt=""
      else:     txt=xlt(self.rightDict[self.rightList[mid]][1])
      self['Rights'].SetToolTip(txt)

    
    def setAcl(self, acl):
      for i in range(len(self.rightList)):
        self['Rights'].Check(i, self.rightList[i] in acl)
      self.OnCheck()
      
    def OnRoClick(self, _evt):
      self.setAcl('lr')
    
    def OnRwClick(self, _evt):
      self.setAcl('lrswit')
    
    def OnAllClick(self, _evt):
      self.setAcl('lrswipkxteacd')
    
    def OnNoClick(self, _evt):
      self.setAcl('')
    
    
    def Save(self):
      return True
    
    validName=re.compile('^[a-z_][a-z_0-9.-]*$')
    def nameValid(self, name):
      return  self.validName.match(name) != None
      
    def Check(self):
      user=self.User
      ok=True
      if self['User'].IsEnabled():
        if not user.startswith('group:'):
          ok=self.CheckValid(ok, user, xlt("No user selected"))
          ok=self.CheckValid(ok, self.nameValid(user), xlt("User name contains invalid characters"))
        else:
          grp=user[6:]
          ok=self.CheckValid(ok, grp, xlt("No group selected"))
          ok=self.CheckValid(ok, self.nameValid(grp), xlt("Group name contains invalid characters"))
        
        ok=self.CheckValid(ok, user not in self.knownUsers, xlt("User already has an acl"))
        ok = self.CheckValid(ok, self['Rights'].GetChecked(), xlt("Select at least one right"))
      return ok
    
    def GetAcl(self):
      acl=""
      for i in self['Rights'].GetChecked():
        acl +=self.rightList[i]
      return acl



  class Dlg(adm.PropertyDialog):
    def __init__(self, parentWin, node, parentNode=None):
      adm.PropertyDialog.__init__(self, parentWin, node, parentNode)
      self.Bind("MailboxName Comment Squat StorageQuota AclRecursive")
      if node and node.CanSelect():
        self['ACL'].Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnClickAcl)
        self['ACL'].Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClickAcl)
        self.Bind('AddAcl', self.OnAddAcl)
      else:
        self.EnableControls("AddAcl ACL", False)
      if node and node.GetServer().flavor != "cyrus":
        self.EnableControls("Squat", False)
      
    def Go(self):
      self['ACL'].CreateColumns(xlt("User"), xlt("ACL"), 15)
      self.oldAcl={}
      
      if self.node:
        self.node.GetProperties()
        self.MailboxName = self.node.name
        self.FullPath=self.node.mailboxPath
        if self.node.annotations:
          self.comment = self.node.annotations.Get('/comment')
          self.squat = self.node.annotations.Get(squatAnnotation, 'false' ) == 'true'
        else:
          self.comment=""
          self.squat=False
        
        if self.node.acl:
          for user, acl in self.node.acl.items():
            self.oldAcl[user]=acl
            self['ACL'].AppendItem(-1, [user, acl])
        if self.node.quota:
          sq=self.node.quota.get('STORAGE')
          if sq:
            if self.node.mailboxPath == sq[0]:
              self.StorageQuota = prettySize(sq[2])
            else:
              self.RootStorageQuota = "%s (root=%s)" % (prettySize(sq[2]), sq[0])
        
      self.SetUnchanged()


    def OnRightClickAcl(self, evt):
      cm=Menu(self)
      cm.Add(self.OnAddAcl, xlt("Add"), xlt("Add user with rights"))
      sel=self['ACL'].GetSelection()
      if len(sel) == 1:
        cm.Add(self.OnEditAcl, xlt("Edit"), xlt("Edit user's acl"))
      if len(sel):
        cm.Add(self.OnDelAcl, xlt("Remove"), xlt("Remove user acl"))
      cm.Popup(evt)
    
    
    def OnDelAcl(self, _evt):
      sel=self['ACL'].GetSelection()
      sel.sort(reverse=True)
      
      for index in sel:
        self['ACL'].DeleteItem(index)
      self.OnCheck()
        
    
    def OnEditAcl(self, _evt):
      sel=self['ACL'].GetSelection()
      if len(sel) == 1:
        self.editAcl(sel[0])
      
    def OnAddAcl(self, _evt):
      self.editAcl()
    
    def OnClickAcl(self, evt):
        index=evt.Index
        self.editAcl(index)

    def editAcl(self, index=-1):
      dlg=Mailbox.MailboxAcl(self, self.parentNode)
      
      lbAcl=self['ACL']
      if index >= 0:
        user=lbAcl.GetItemText(index, 0)
        acl=lbAcl.GetItemText(index, 1)
        dlg.Go(user, acl)
      else:
        lst=[]
        for i in range(lbAcl.GetItemCount()):
          lst.append(lbAcl.GetItemText(i, 0))
        dlg.Go(None, None, lst)
        
      if dlg.ShowModal() == wx.ID_OK:
        acl=dlg.GetAcl()
        if index >= 0:
          if acl:
            lbAcl.SetItem(index, 1, acl)
          else:
            lbAcl.DeleteItem(index)
        elif acl:
          lbAcl.AppendItem(-1, [dlg.User, acl])

        self.OnCheck()
    
    def Check(self):
      ok=self.CheckValid(True, self.MailboxName, xlt("Name cannot be empty"))
      ok=self.CheckValid(ok, self.MailboxName.find('@')<0, xlt("Name may not include the @ character"))
      return ok
    
    
    def Save(self):
      c=self.GetConnection()
      mailboxName=encodeUtf7(self.MailboxName)
      if self.node:
        if self.MailboxName == self.node.name:
          ok=True
          mailboxPath=self.node.mailboxPath
        else:
          if isinstance(self.node.parentNode, Mailbox):
            mailboxPath="%s%s%s" % (self.node.parentNode.mailboxPath, self.parentNode.separator, mailboxName)
          else:
            mailboxPath=mailboxName
          ok=c.RenameMailbox(self.node.mailboxPath, mailboxPath)  
          if ok:
            self.refreshNode = self.node.parentNode
      else:
        if isinstance(self.parentNode, Mailbox):
          mailboxPath="%s%s%s" % (self.parentNode.mailboxPath, self.parentNode.separator, mailboxName)
        else:
          mailboxPath=mailboxName
        ok=c.CreateMailbox(mailboxPath)
      
      if ok and self.HasChanged('Comment'):
        ok = c.SetAnnotation(mailboxPath, "/comment", self.Comment)
      if ok and self.HasChanged('Squat'):
        if self.Squat: squat='true'
        else:          squat='false'
        ok = c.SetAnnotation(mailboxPath, squatAnnotation, squat)

        
      if ok and self.HasChanged('StorageQuota'):
        if self.StorageQuota != "":
          ok=c.SetQuota(mailboxPath, { 'STORAGE': sizeToFloat(self.StorageQuota) } )
        else:
          ok=c.SetQuota(mailboxPath, None)
    
      lbAcl=self['ACL']
      if ok and lbAcl.unchangedValue != self.Acl or self.AclRecursive:
        subMbList=[mailboxPath]
        setAclList=[]

        if self.AclRecursive:
          mbList=c.List(mailboxPath, "*")
          for line in mbList:
            name, _,_ = self.node.splitMbInfo(line)
            if name != mailboxPath:
              subMbList.append(name)

        for row in range(lbAcl.GetItemCount()):
          user=lbAcl.GetItemText(row, 0)
          acl=lbAcl.GetItemText(row, 1)
          if user in self.oldAcl:
            if acl != self.oldAcl[user]:
              # Change ACL
              setAclList.append( (user, acl))
            del self.oldAcl[user]
          else:
            # add ACL
            setAclList.append( (user, acl))
        
        for mb in subMbList:
          self.SetStatus(xlt("Setting ACL on %s") % mb)
          if setAclList:
            ok=c.SetAcl(mb, setAclList)
          else:
            ok=True
          if ok and self.oldAcl:
            ok=c.DelAcl(mb, self.oldAcl.keys())
    
          if not ok:
            self.SetStatus("Save error: %s" % self.GetServer().GetLastError())
            return False
        
      if not self.node:
        self.parentNode.Refresh()
      return ok
      
  @staticmethod
  def New(parentWin, parentNode):
    adm.DisplayDialog(Mailbox.Dlg, parentWin, None, parentNode)

  def Edit(self, parentWin):
    adm.DisplayDialog(self.Dlg, parentWin, self)

  def Delete(self):
    if not 'x' in self.myrights and not 'c' in self.myrights:
      dlg=wx.MessageDialog(adm.GetCurrentFrame(), xlt("Add missing right and delete?"), xlt("Missing rights on mailbox %s") % self.name, wx.YES_NO|wx.NO_DEFAULT)
      if dlg.ShowModal() != wx.ID_YES:
        return False
      rc=self.GetConnection().SetAcl(self.mailboxPath, self.GetServer().user, self.myrights + 'xcd')
      if not rc:
        return False
       
    rc=self.GetConnection().DeleteMailbox(self.mailboxPath)
    return rc != None

class MailboxReconstruct:
  name=xlt("Reconstruct")
  help=xlt("Reconstruct mailbox")
  
  @staticmethod
  def CheckEnabled(node):
    return 'Noselect' not in node.flags
  
  @staticmethod
  def OnExecute(_parentWin, node):
    recursive=True # TODO ask
    return node.GetConnection().Reconstruct(node.mailboxPath, recursive) != None

class MailboxMove:
  name=xlt("Move")
  help=xlt("Move mailbox to a different path")
  
  @staticmethod
  def OnExecute(parentWin, node):
    dlg=wx.TextEntryDialog(parentWin, xlt("New mailbox path"), xlt("Move mailbox %s") % node.mailboxPath)
    dlg.SetValue(node.mailboxPath)
    if dlg.ShowModal() == wx.ID_OK:
      newPath=dlg.GetValue()
      rc=node.GetConnection().RenameMailbox(node.mailboxPath, newPath)
      if rc:
        node.parentNode.Refresh()
    return False
  
  
menuinfo=[
# TODO not working?        {'class': MailboxReconstruct, 'nodeclasses': Mailbox, 'sort': 20 },
           {'class': MailboxMove, 'nodeclasses': Mailbox, 'sort': 10 },
        ]
  
nodeinfo= [ 
           { "class": Mailbox, "parents": ["Server", "Mailbox"], "sort": 10, "pages": "" },
           ]
