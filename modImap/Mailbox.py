# The Admin4 Project
# (c) 2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import shlexSplit, xlt
import wx

class Mailbox(adm.Node):
  typename="IMAP Mailbox"
  shortname="Mailbox"
  
  
  def __init__(self, parentNode, name, separator, flags):
    super(Mailbox, self).__init__(parentNode, name)
    self.flags=flags
    self.separator=separator
    self.mailboxPath=name
    parts=shlexSplit(name, self.separator)
    if len(parts) > 1:
      self.name=parts[-1]
      if len(parts) == 2 and parts[0] == "user":
        self.GetServer().userList.append(self.name)


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
        parts=shlexSplit(line, ' ')
        separator=parts[-2]
        mailbox=parts[-1]
        flags=parts[:-2]
        flags[0] = flags[0][1:]
        flags[-1] = flags[-1][:-1]
        instances.append(Mailbox(parentNode, mailbox, separator, flags))

    return instances
  

  def RefreshVolatile(self, _force=False):
    self.acl=self.GetConnection().GetAcl(self.mailboxPath)
    self.annotations=self.GetConnection().GetAnnotations(self.mailboxPath)
    self.myrights=self.GetConnection().MyRights(self.mailboxPath)


  def GetProperties(self):
    if not self.properties:
      self.RefreshVolatile(True)
      
      self.properties=[
                       ( xlt("Name"), self.name),
#                       ( xlt("Separator"), self.separator),
                       ( xlt("Flags"), ", ".join(self.flags))
                       ]

      self.AddProperty(xlt("My rights"), self.myrights)
      self.AddProperty(xlt("Comment"), self.annotations.Get('/comment'))
      sz=self.annotations.Get('/size')
      if sz != None:
        self.AddSizeProperty(xlt("Size"), sz)

      self.AddProperty(xlt("Last update"), self.annotations.Get('/lastupdate'))
      chk=(self.annotations.Get('/check') ==  "true")
      self.AddYesNoProperty(xlt("Check"), chk)
      if chk:
        self.AddProperty(xlt("Check period"), self.annotations.Get('/checkperiod'))
      
          
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
                'x': (xlt("delete mailbox"), xlt("delete mailbox or source parent for move operation")),
                't': (xlt("delete message"), xlt("set deleted flag")),
                'e': (xlt("expunge"), xlt("expunge deleted messages from mailbox when closing")),
                'a': (xlt("administer"), xlt("administer mailbox acl")),
                'c': (xlt("create (obsolete)"), xlt("obsolete/implementation dependent for k or kx")),
                'd': (xlt("delete (obsolete)"), xlt("obsolete/implementation dependent for xte or te")),
               }

    rightList="lrswipkxteacd"
    
    def Go(self, user=None, acl=None):
      self.User=user
      if user:  self['User'].Disable()
      else:
        self.Bind('User')
        for user in self.node.GetServer().userList:
          self['User'].Append(user)
      
      self.Bind('RoRights', self.OnRoClick)
      self.Bind('RwRights', self.OnRwClick)
      self.Bind('AllRights', self.OnAllClick)
      self.Bind('NoRights', self.OnNoClick)
      self.Bind(wx.EVT_MOTION, self.OnMouseMoveRights)

      
      for right in self.rightList:
        i=self['Rights'].Append(xlt(self.rightDict[right][0]))
        if acl and right in acl:
          self['Rights'].Check(i)

    def OnMouseMoveRights(self, evt):
      pt=evt.GetPosition() - self['Rights'].GetPosition()
      id=self['Rights'].HitTest(pt)

      if id < 0:txt=""
      else:     txt=xlt(self.rightDict[self.rightList[id]][1])
      self['Rights'].SetToolTipString(txt)

    
    def setAcl(self, acl):
      for i in range(len(self.rightList)):
        self['Rights'].Check(i, self.rightList[i] in acl)
      
    def OnRoClick(self, evt):
      self.setAcl('lr')
    
    def OnRwClick(self, evt):
      self.setAcl('lrswit')
    
    def OnAllClick(self, evt):
      self.setAcl('lrswipkxtea')
    
    def OnNoClick(self, evt):
      self.setAcl('')
    
    
    def Save(self):
      return True
      
    def Check(self):
      user=self.User
      ok=self.CheckValid(True, user, xlt("No user selected"))
      return ok
    
    def GetAcl(self):
      acl=""
      for i in self['Rights'].GetChecked():
        acl +=self.rightList[i]
      return acl



  class Dlg(adm.PropertyDialog):
    def __init__(self, parentWin, node, parentNode=None):
      adm.PropertyDialog.__init__(self, parentWin, node, parentNode)
      self.Bind("MailboxName Comment")
      self['ACL'].Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnClickAcl)
      self.Bind('AddAcl', self.OnClickAdd)
      
    def Go(self):
      self['ACL'].CreateColumns(xlt("User"), xlt("ACL"), 15)
      self.oldAcl={}
      
      if self.node:
        self.node.GetProperties()
        self.MailboxName = self.node.name
        self.FullPath=self.node.mailboxPath
        self.comment = self.node.annotations.Get('/comment')
        for user, acl in self.node.acl.items():
          self.oldAcl[user]=acl
          self['ACL'].AppendItem(-1, [user, acl])
      self.SetUnchanged()


    def OnClickAdd(self, evt):
      self.OnClickAcl(None)
    
    def OnClickAcl(self, evt):
      dlg=Mailbox.MailboxAcl(self, self.parentNode)
      
      lbAcl=self['ACL']
      if evt:
        index=evt.Index
        user=lbAcl.GetItemText(index, 0)
        acl=lbAcl.GetItemText(index, 1)
        dlg.Go(user, acl)
      else:
        dlg.Go()
      if dlg.ShowModal() == wx.ID_OK:
        if index >= 0:
          acl=dlg.GetAcl()
          if acl:
            lbAcl.SetStringItem(index, 1, acl)
          else:
            lbAcl.DeleteItem(index)
        elif acl:
          lbAcl.AppendItem(-1, [dlg.User, acl])

        self.OnCheck(evt)
    
    def Check(self):
      ok=self.CheckValid(True, self.MailboxName, xlt("Name cannot be empty"))
      return ok
    
    
    def Save(self):
      c=self.GetConnection()
      if self.node:
        if self.MailboxName == self.node.name:
          ok=True
          mailboxPath=self.node.mailboxPath
        else:
          if isinstance(self.node.parentNode, Mailbox):
            mailboxPath="%s%s%s" % (self.node.parentNode.mailboxPath, self.parentNode.separator, self.MailboxName)
          else:
            mailboxPath=self.MailboxName
          ok=c.RenameMailbox(self.node.mailboxPath, mailboxPath)  
          
      else:
        if isinstance(self.parentNode, Mailbox):
          mailboxPath="%s%s%s" % (self.parentNode.mailboxPath, self.parentNode.separator, self.MailboxName)
        else:
          mailboxPath=self.MailboxName
        ok=c.CreateMailbox(mailboxPath)
      
      if ok and self['Comment'].unchangedValue != self.Comment:
        ok = c.SetAnnotation(mailboxPath, "/comment", self.Comment)
    
      lbAcl=self['ACL']
      if ok and lbAcl.unchangedValue != self.Acl:
        for row in range(lbAcl.GetItemCount()):
          user=lbAcl.GetItemText(row, 0)
          acl=lbAcl.GetItemText(row, 1)
          if user in self.oldAcl:
            if acl != self.oldAcl[user]:
              # Change ACL
              ok=c.SetAcl(mailboxPath, user, acl)
            del self.oldAcl[user]
          else:
            # add ACL
            ok=c.SetAcl(mailboxPath, user, acl)
          if not ok:  return False
        for user in self.oldAcl:
          # delete remaining acls
          ok=c.DelAcl(mailboxPath, user)
          if not ok:  return False
      return ok
      
  @staticmethod
  def New(parentWin, parentNode):
    adm.DisplayDialog(Mailbox.Dlg, parentWin, None, parentNode)

  def Edit(self, parentWin):
    adm.DisplayDialog(self.Dlg, parentWin, self)

  def Delete(self):
    return self.GetConnection().DeleteMailbox(self.mailboxPath)
      
nodeinfo= [ 
           { "class": Mailbox, "parents": ["Server", "Mailbox"], "sort": 10, "pages": "" },
           ]
