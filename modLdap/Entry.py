# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import logger
import adm
from wh import xlt
from . import AttrVal, ldapSyntax
import os, base64, hashlib



class Entry(adm.Node):
  typename=xlt("LDAP Entry")
  shortname=xlt("Entry")
  icon="Entry"
  newEntryClassList=[]

  @classmethod
  def addNewEntryClass(self, cls):
    self.newEntryClassList.append(cls)


  def __init__(self, parentNode, dn, attribs):
    adm.Node.__init__(self, parentNode, dn)
    self.dn=dn
    self.name=self.GetServer().Split_DN(dn)[0]
    self._setAttribs(attribs)

    self.primaryClass=SpecificEntry.GetSpecificClass(self)


    if self.primaryClass:
      self.typename=self.primaryClass.name
      if hasattr(self.primaryClass, "shortname"):
        self.shortname=self.primaryClass.shortname
      else:
        self.shortname = self.typename
      if hasattr(self.primaryClass, "icon"):
        self.icon=self.primaryClass.icon
      else:
        self.icon = self.shortname

      if hasattr(self.primaryClass, "GetClassIconName"):
        self.icon=self.primaryClass.GetClassIconName(self)


  def MayHaveChildren(self):
    try:
      return self.attribs[self.GetServer().GetHasSubordinatesOid()].GetValue()
    except:
      return True

  def HasObjectClass(self, objClsName):
    return objClsName.lower() in map(lambda x: x.lower(), self.objectClasses)



  def GetIcon(self):
    return self.GetImageId(self.icon)


  def GetProperties(self):
    if not self.properties:
      self.properties= [
          ( "dn", self.dn, self.GetIcon() ),
          ( "objectClasses", ",".join(self.objectClasses), self.GetImageId("objectClass") ),
          ]

      oids=self.attribs.keys()
      try:
        oids.remove(self.GetServer().GetObjectClassOid())
      except:
        pass
#      oids.remove(self.GetServer().GetStructuralObjectOid())
      try:
        oids.remove(self.GetServer().GetHasSubordinatesOid())
      except:
        pass

      must, _may= self.GetServer().GetClassSchemaMustMayOids(self.objectClasses)

      rdnOid=self.GetServer().GetOid(self.name.split('=')[0])

      def checkUC(v):
        
        return unicode(v)
      
      def addSingle(oid):
        if oid in oids:
          attrval=self.attribs[oid]
          if oid == rdnOid:
            icon="attribRDN"
          elif oid in self.GetServer().GetSystemAttrOids():
            icon="attribEmpty"
          elif oid in must:
            icon="attribMust"
          else:
            icon="attribMay"
          if attrval.IsBinary() and not attrval.IsOctet():
            val=xlt("<binary data>")
          else:
            try:
              val=attrval.GetValue()
            except:
              val=attrval.value
          if isinstance(val, list):
            try:
              map(unicode, val)
            except:
              val = " ".join(map(lambda y: "".join(map(lambda x: "%02x" % ord(x), y)), val))
          else:
            try:
              unicode(val)
            except:
              val = "".join(map(lambda x: "%02x" % ord(x), val))

          self.AddChildrenProperty(val, attrval.name, self.GetImageId(icon))
          oids.remove(oid)

      map(addSingle, self.GetServer().GetSystemAttrOids())
      map(addSingle, self.GetServer().GetAttrOrder())
      map(addSingle, oids[:])

    return self.properties


  def DoRefresh(self):
    attrs=["*"]
    attrs.extend(self.GetServer().systemAttrs)
    result=self.GetConnection().SearchOne(self.parentNode.dn, "(%s)" % self.name, attrs)
    if len(result) == 1:
      self._setAttribs(result[0][1])
      adm.Node.DoRefresh(self)
    else:
      self.parentNode.DoRefresh()


  @staticmethod
  def GetInstances(parentNode):
    attrs=["*"]
    attrs.extend(parentNode.GetServer().systemAttrs)
    result=parentNode.GetConnection().SearchOne(parentNode.dn, "(objectClass=*)", attrs)
    if not result:
      return None
    objects=[]
    adminLdapDn=parentNode.GetServer().adminLdapDn
    array={}
    for dn, attribs in result:
      if not dn:
        logger.debug("Referral: %s", str(attribs))
        continue
      if False: # We could suppress the admin config entry here
        if dn == adminLdapDn:
          continue
      array[dn.decode('utf8')]=attribs
    dns=array.keys()
    dns.sort()

    for dn in dns:
      attribs=array[dn]
      objects.append(Entry(parentNode, dn, attribs))
    return objects





  def _setAttribs(self, attribs):
    self.attribs={}
    for name, value in attribs.items():
      if name == 'objectClass':
        self.objectClasses=value
        self.objectClasses.sort()
      schemaAttr=self.GetServer().GetAttributeSchema(name)
      attrval=AttrVal(name, value, schemaAttr)
      oid=attrval.GetOid()
      if not oid:
        oid=name
#       logger.debug("No Oid for %s", name)
      if self.attribs.get(oid):
        logger.debug("Attribute %s already set", attrval)

      self.attribs[oid] = attrval


  def Edit(self, parentWin):
    adm.DisplayDialog(self.Dlg, parentWin, self, None, self.primaryClass)

  def Delete(self):
    return self.GetConnection().Delete(self.dn)

  @staticmethod
  def New(parentWin, parentNode):
    adm.DisplayDialog(Entry.Dlg, parentWin, None, parentNode, None)




  class Dlg(adm.PropertyDialog):
    def __init__(self, parentWin, node, parentNode, primaryClass):
      adm.PropertyDialog.__init__(self, parentWin, node, parentNode)

      self.rdnOid=None
      self.must=[]
      self.primaryClass=primaryClass


    def Go(self):
      self.panels=[]
      notebook=self['Notebook']
      def addPanel(panel, name):
        self.panels.append(panel)
        notebook.AddPage(panel, name)

      for cls, resname in SpecificEntry.GetClasses(self.parentNode.GetServer(), self.primaryClass):
        panel=cls(self, notebook, resname)
        addPanel(panel, panel.name)

      panel=GenericEntry(self, notebook)
      addPanel(panel, panel.name)

      self.objectClassOid=self.GetServer().GetObjectClassOid()
      self.attribs={}
      if self.node:
        for oid, attr in self.node.attribs.items():
          attrval=AttrVal(attr)
          self.attribs[oid] = attrval
        self.dn=self.node.dn
        self.rdn=self.node.name
        self.setRdnOid(self.rdn)
        self.objectClasses=self.attribs[self.objectClassOid].value
      else:
        self.dn=None
        self.rdn=None
        if self.primaryClass:
          self.objectClasses=self.primaryClass.startClasses.split()
        else:
          self.objectClasses=[]
      self.UpdateObjectClasses()


    def GetAttrib(self, name):
      attr=self.attribs.get(name)
      if not attr:
        attr=self.attribs.get(self.GetServer().GetOid(name))
      return attr

    def GetAttrValue(self, name):
      attr=self.attribs.get(name)
      if not attr:
        attr=self.attribs.get(self.GetServer().GetOid(name))
      if attr:
        return attr.GetValue()
      return None

    def setRdnOid(self, rdn):
      self.rdnOid=self.GetServer().GetOid(rdn.split('=')[0])

    def HasObjectClass(self, objClsName):
      return objClsName.lower() in map(lambda x: x.lower(), self.objectClasses)

    def RemoveObjectClass(self, objClsName):
      for n in self.objectClasses:
        if n.lower() == objClsName.lower():
          self.objectClasses.remove(n)
          return True
      return False

    def UpdateObjectClasses(self):
      self.objectClasses.sort()
      attrval=AttrVal('objectClass', self.objectClasses, self.GetServer().GetAttributeSchema('objectClass'))
      self.attribs[self.objectClassOid] = attrval

      self.mustAttribs, self.mayAttribs= self.GetServer().GetClassSchemaMustMayOids(self.objectClasses)

      for oid in self.attribs.keys():
        if oid not in self.mayAttribs:
          del self.attribs[oid]

      for oid in self.mustAttribs:
        if oid not in self.attribs:
          self.SetValue(oid, None)
      for panel in self.panels:
        panel.Go()


    def DelValue(self, oid, originPanel=None):
      attrval=self.attribs.get(oid)
      if not attrval:
        noid=self.GetServer().GetOid(oid)
        if noid:
          oid=noid
          attrval=self.attribs.get(oid)

      if attrval:
        if oid in self.mustAttribs:
          self.SetStatus(xlt("attribute \"%s\" may not be removed") % attrval.name)
          return
        for panel in self.panels:
          if panel != originPanel:
            panel.DelValue(attrval)
        del self.attribs[oid]


    def SetValue(self, oid, value, originPanel=None):
      attrval=self.attribs.get(oid)
      if not attrval:
        noid=self.GetServer().GetOid(oid)
        if noid:
          oid=noid
          attrval=self.attribs.get(oid)

      if not oid in self.mayAttribs:
        return

      if not attrval:
        schemaAttr=self.GetServer().GetAttributeSchema(oid)
        if not schemaAttr:
          logger.debug("No Schema for %s", oid)
          return
        attrval=AttrVal(None, None, schemaAttr)
        self.attribs[oid] = attrval
      if value != None and not attrval.IsSingleValue() and not isinstance(value, list):
        attrval.SetValue([value])
      else:
        attrval.SetValue(value)
      if oid == self.rdnOid:
        self.rdn="%s=%s" % (attrval.name, attrval.value[0].decode('utf8'))
      for panel in self.panels:
        if panel != originPanel:
          panel.SetValue(attrval)


    def Check(self):
      for panel in self.panels:
        if hasattr(panel, "Check"):
          if not panel.Check():
            return False

      ok=True
      ok=self.CheckValid(ok, len(self.objectClasses), xlt("At least one objectClass needed."))
      if not self.node:
        rdn=self.rdn
        ok=self.CheckValid(ok, rdn, xlt("RDN needs to be given"))
        if rdn:
          ok=self.CheckValid(ok, len(rdn.split('=')) == 2, xlt("Invalid RDN format: attr=value"))

      for attr in self.attribs.values():
        ok=self.CheckValid(ok, not attr.empty or attr.schema.syntax in ldapSyntax.EmptyAllowed, xlt("Attribute \"%s\" may not be empty") % attr.name)
        if not ok:
#          logger.debug("non-empty: %s", attr.schema.syntax)
          return False
      return ok


    def GetChanged(self):
      if self.node:
        if self.objectClasses != self.node.objectClasses:
          return True
        if len(self.attribs) != len(self.node.attribs):
          return True

        for attr in self.node.attribs.values():
          attr.processed=False
        for oid, attr in self.attribs.items():
          if oid in self.node.attribs:
            ao=self.node.attribs[oid]
            ao.processed=True
            if str(attr.value) != str(ao.value):
              return True
          else:
            return True
        for attr in self.node.attribs.values():
          if not attr.processed:
            return True
        return False
      else:
        return True


    def Save(self):
      addList=[]
      chgList=[]
      delList=[]

      if self.node:
        for attr in self.node.attribs.values():
          attr.processed=False

        # ignore SystemAttrs
        for oid in self.GetServer().GetSystemAttrOids():
          attr=self.node.attribs.get(oid)
          if attr:
            attr.processed=True

        # Check added and modified
        for oid, attr in self.attribs.items():
          if oid in self.node.attribs:
            ao=self.node.attribs[oid]
            ao.processed=True
            if str(attr.value) != str(ao.value):
              chgList.append(attr)
          else:
            addList.append(attr)

        # check deleted
        for attr in self.node.attribs.values():
          if not attr.processed:
            delList.append(attr)

        self.GetConnection().Modify(self.node.dn, chgList, addList, delList)

      else:
        self.dn="%s,%s" % (self.rdn, self.parentNode.dn)
        self.GetConnection().Add(self.dn, self.attribs.values())

        # check if objectClasses changed

      for panel in self.panels:
        if hasattr(panel, "Save"):
          panel.Save()

      return True



#===========================================================
# general entry menus
#===========================================================


class EntryRename:
  name="Rename"
  help="Rename Entry"

  @staticmethod
  def OnExecute(parentWin, node):
    rdn=node.name.split('=')
    dlg=wx.TextEntryDialog(parentWin, xlt("rename to %s=") % rdn[0], xlt("Rename %s \"%s\"") % (node.typename, rdn[1]))
    dlg.SetValue(rdn[1])
    if dlg.ShowModal() == wx.ID_OK:
      newname=dlg.GetValue()
      if newname != rdn[1]:
        newrdn="%s=%s" % (rdn[0], newname)
        node.GetConnection().Rename(node.dn, newrdn)
        node.name=newrdn
        return True
    return False


class EntryPassword:
  name=xlt("Password")
  help=xlt("Set Password")

  @staticmethod
  def CheckEnabled(node):
    _must,may=node.GetServer().GetClassSchemaMustMayOids(node.objectClasses)
    for pwd in ['userPassword', "sambaNTpassword"]: # "sambaLMpassword"
      oid=node.GetServer().GetOid(pwd)
      if oid in may:
        return True
    return False

  
  @staticmethod
  def OnExecute(parentWin, node):
    passwd=adm.AskPassword(parentWin, xlt("Enter new password:"), xlt("Set password for %s \"%s\"") % (node.typename, node.name))
    if passwd != None:
      addList=[]
      chgList=[]

      def EncryptPassword(passwd, hash):
        if hash == "CLEARTEXT":
          return passwd
        salt=""
        if hash == "SHA":
          alg="SHA1"
        elif hash == "SSHA":
          salt=os.urandom(4)
          alg="SHA1"
        elif hash == "MD5":
          alg="MD5"
        elif hash == "SMD5":
          salt=os.urandom(4)
          alg="MD5"
        else:
          return None
        hl=hashlib.new(alg, passwd.encode('utf8'))
        if salt:
          hl.update(salt)
        crypted=base64.b64encode(hl.digest() + salt)
        return str("{%s}%s" % (hash, crypted))


      _must,may=node.GetServer().GetClassSchemaMustMayOids(node.objectClasses)

      userPasswordSchema=node.GetServer().GetAttributeSchema("userPassword")
      if userPasswordSchema.oid in may:
        hash=EncryptPassword(passwd, node.GetServer().GetPreference("PasswordHash"))
        userPassword=AttrVal(None, hash, userPasswordSchema)

        if userPasswordSchema.oid in node.attribs:
          chgList.append(userPassword)
        else:
          addList.append(userPassword)
      else:
        node.GetConnection().SetPassword(node.dn, passwd)
  
      ntPasswordSchema=node.GetServer().GetAttributeSchema("sambaNTpassword")
      if ntPasswordSchema.oid in may:
        md4hash=hashlib.new('md4', passwd.encode('utf-16le')).hexdigest().upper()
        ntPassword=AttrVal(None, md4hash, ntPasswordSchema)

        if ntPasswordSchema.oid in node.attribs:
          chgList.append(ntPassword)
        else:
          addList.append(ntPassword)

      if chgList or addList:
        node.GetConnection().Modify(node.dn, chgList, addList)
        return True
      return False
    return False

nodeinfo=[
        {"class": Entry, "parents": ["Server", "Entry"], "sort": 10, "new": Entry.newEntryClassList },
        ]

menuinfo=[
        {'class': EntryRename, 'nodeclasses': Entry, 'sort': 20 },
        {'class': EntryPassword, 'nodeclasses': Entry, 'sort': 30 },
        ]


from SpecificEntry import SpecificEntry
from GenericEntry import GenericEntry
