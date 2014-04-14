# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import logger
import adm
from wh import xlt, Menu
import wx.propgrid as wxpg
from . import AttrVal, ldapSyntax
import base64, hashlib



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
        self.shortname = self.name
      if hasattr(self.primaryClass, "icon"):
        self.icon=self.primaryClass.icon
      else:
        self.icon = self.shortname

      if hasattr(self.primaryClass, "GetClassIconName"):
        self.icon=self.primaryClass.GetClassIconName(self)


#      elif  ["mailgroup", "posixgroup", "groupofuniquenames"]:
#        self.icon="Group"
#      elif  "device":
#        self.icon="Entry"
#      elif "locality":
#        self.icon="Entry"


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

    array={}
    for dn, attribs in result:
      if not dn:
        logger.debug("Referral: %s", str(attribs))
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
      attrval=AttrVal(name, schemaAttr, value)
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

      for cls, resname in SpecificEntry.GetClasses(self.primaryClass):
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
      attrval=AttrVal('objectClass', self.GetServer().GetAttributeSchema('objectClass'), self.objectClasses)
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
        name = schemaAttr.names[0]
        attrval=AttrVal(name, schemaAttr)
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


from SpecificEntry import SpecificEntry



class GenericEntry(adm.NotebookPanel):
  name=xlt("Generic")
  def __init__(self, dlg, notebook, resname=None):
    adm.NotebookPanel.__init__(self, dlg, notebook, resname)
    self.grid.Bind(wxpg.EVT_PG_CHANGED, self.OnGridChange)
    self.grid.Bind(wx.EVT_RIGHT_DOWN, self.OnGridRightClick)
    self.grid.Bind(wx.EVT_MOTION, self.OnMouseMove)
    self.availableObjectClasses={}
    self.may=[]
    self.lastRdnOid=None
    self.dialog.BindMenuId(self.OnDelAttrs)

    self.Bind("ObjectClass", self.OnClassChange)
    self.Bind("AddObjectClass", self.OnAddObjectClass)
    self.Bind("DelObjectClass", self.OnDelObjectClass)
    self.Bind("RDN", self.OnRDN)


  def AddExtraControls(self, res):
    self.grid=wxpg.PropertyGrid(self)
    res.AttachUnknownControl("ValueGrid", self.grid)
    self.grid.SetMarginColour(wx.Colour(255,255,255))


  def Go(self):
    self.lastRdnOid=self.dialog.rdnOid
    while self['ObjectClass'].GetCount() > 1:
      self['ObjectClass'].Delete(1)
    for cls in self.dialog.objectClasses:
      self['ObjectClass'].Append(cls)
    self['ObjectClass'].SetSelection(0)

    if self.dialog['Notebook'].GetPageCount() > 1:
      self['RDN'].Disable()
    if self.dialog.node:
      self['RDN'].Disable()
      self.RDN=self.dialog.node.name
    self.OnClassChange()


  def addProp(self, oid):
    attr=self.dialog.attribs[oid]
    value=attr.GetValue()
    if oid == self.dialog.rdnOid:
      icon="attribRDN"
    elif oid in self.dialog.mustAttribs:
      icon="attribMust"
    else:
      icon="attribMay"

    if attr.IsBinary():
      property=wxpg.StringProperty(attr.name, "", xlt("<binary data; can't edit>"))
    elif attr.IsSingleValue():
      if attr.IsInteger():
          property=wxpg.IntProperty(attr.name, oid, value)
      else:
        if not value:
          value=""
        property=wxpg.StringProperty(attr.name, oid, value)
    else:
      if not value:
        value=[]
      property=wxpg.ArrayStringProperty(attr.name, oid, value)
    self.grid.Append(property)
    self.grid.SetPropertyImage(property, self.dialog.GetBitmap(icon))

    if not attr.IsBinary():
      attr.items[self.grid]=property
    return property

  def updateRdnOid(self, attr):
    if self.lastRdnOid:
      property=self.dialog.attribs[self.lastRdnOid].items.get(self.grid)
      if property:
        self.grid.SetPropertyImage(property, self.dialog.GetBitmap("attribMust"))
    if self.dialog.rdnOid:
      property=attr.items.get(self.grid)
      if property:
        self.grid.SetPropertyImage(property, self.dialog.GetBitmap("attribRDN"))
    self.lastRdnOid=self.dialog.rdnOid


  def Check(self):
    ok=True
    rdn=self.RDN.split('=')
    oid=self.GetServer().GetOid(rdn[0])
    ok=self.dialog.CheckValid(ok, self.dialog.objectClasses, xlt("Select a structural object class first"))
    if self.RDN:
      ok=self.dialog.CheckValid(ok, len(rdn) == 2 and rdn[0] and rdn[1], xlt("Invalid RDN format: <attr>=<value>"))
      ok=self.dialog.CheckValid(ok, oid in self.dialog.mayAttribs, xlt("RDN must use a valid attribute"))
    else:
      ok=self.dialog.CheckValid(ok, False, xlt("Enter RDN"))
    return ok


  def OnRDN(self, evt):
    rdn=self.RDN.split('=')
    if len(rdn) == 2:
      oid=self.GetServer().GetOid(rdn[0])
      attr=self.dialog.attribs.get(oid)
      if attr:
        if attr.IsSingleValue():
          value=rdn[1]
        else:
          value=attr.GetValue()[:]
          value[0]=rdn[1]
        self.dialog.setRdnOid(self.RDN)
        self.updateRdnOid(attr)
        self.dialog.SetValue(oid, value, None)
    self.dialog.OnCheck()


  def OnClassChange(self, evt=None):
    self.grid.Freeze()
    self.grid.Clear()
    for attr in self.dialog.attribs.values():
      attr.items[self.grid]=None

    if self['ObjectClass'].GetSelection() == 0:
      self.EnableControls("DelObjectClass", False)
      selectedClasses=self.dialog.objectClasses
    else:
      self.EnableControls("DelObjectClass", True)
      selectedClasses=[self.ObjectClass]

    if selectedClasses:
      must, self.may= self.GetServer().GetClassSchemaMustMayOids(selectedClasses)
      ocoid=self.dialog.objectClassOid
      must.remove(ocoid)
      self.may.remove(ocoid)

      oids=self.dialog.attribs.keys()
      oids.remove(ocoid)

      for oid in must:
        if oid not in oids:
          attr=self.GetServer().GetAttributeSchema(oid)
          if attr:
            logger.debug("Need attribute: %s %s", oid, attr.names)
          else:
            logger.debug("Need attribute without schema: %s", oid)

      for oid in oids:
        if oid in self.may:
          self.addProp(oid)

      newOids=[]
      for oid in self.may:
        if oid not in oids:
          newOids.append(self.GetServer().GetName(oid))

      if newOids:
        property=self.grid.Append(wxpg.MultiChoiceProperty(xlt("<new>"), "", newOids, ""))
        self.grid.SetPropertyImage(property, self.dialog.GetBitmap("attribEmpty"))

    self.grid.Thaw()


  def OnAddObjectClass(self, evt=None):
    self.GetServer().AllObjectClasses()

    presentMarker="("
    def addClass(childlist, level, onlyStructural):
      for cls in childlist:
        if onlyStructural and cls.kind != 0:
          continue
        tab="                                                                     "[:level*3]
        if cls.name.lower() in map(lambda x: x.lower(), self.dialog.objectClasses):
          pm=presentMarker
          pme=")"
        else:
          pm=" "
          pme=""
        ocs.append("%s%s%s%s" % (tab, pm, cls.names[0],pme))

        addClass(cls.children, level+1, onlyStructural)


    oldlen=len(self.dialog.objectClasses)

    ocs=[]
    onlyStructural=(oldlen == 0)
    addClass(self.GetServer().GetClassSchema('top').children, 0, onlyStructural)

    if onlyStructural:
      caption= xlt("Available structural objectClasses")
    else:
      caption= xlt("Available objectClasses")

    dlg=wx.MultiChoiceDialog(self, xlt("Add objectClass"), caption, ocs)
    if dlg.ShowModal() == wx.ID_OK:
      for i in dlg.GetSelections():
        cls=ocs[i].strip()
        if cls.startswith(presentMarker):
          continue
        if cls not in self.dialog.objectClasses:
          self.dialog.objectClasses.append(cls)

      self.dialog.UpdateObjectClasses()
      if not oldlen or not len(self.dialog.objectClasses):
        self.dialog.OnCheck()

  def OnDelObjectClass(self, evt):
    self.dialog.objectClasses.remove(self.ObjectClass)
    self.dialog.UpdateObjectClasses()


  def OnMouseMove(self, ev):
    txt=""
    pos=self.grid.HitTest(ev.GetPosition())
    if pos:
      property=pos.GetProperty()
      if property:
        oid=property.GetName()
        if oid:
          attr=self.dialog.attribs[oid]
          syntax=""
          if attr.schema.syntax:
            synSch=self.GetServer().GetSyntaxSchema(attr.schema.syntax)
            if synSch:
              if attr.schema.syntax_len:
                syntax="(%s{%d})" % (synSch.desc, attr.schema.syntax_len)
              else:
                syntax="(%s)" % synSch.desc
          txt="%s %s\nOID: %s\n\n%s"  % (attr.name, syntax, oid, attr.schema.desc)
    self.grid.SetToolTipString(txt)



  def OnDelAttrs(self, evt):
    property=self.grid.GetSelection()
    if property:
      oid=property.GetName()
      if oid:
        self.dialog.DelValue(oid, None)
        self.dialog.OnCheck()

  def OnGridRightClick(self, ev):
    property=self.grid.GetSelection()
    if property:
      oid=property.GetName()
      if oid:
        name=self.dialog.attribs[oid].name
        cm=Menu()
        cm.Append(self.dialog.GetMenuId(self.OnDelAttrs), xlt("Remove %s") % name, xlt("Remove attribute \"%s\"") % name)
        pos=ev.GetPosition() + (0,20)
        self.PopupMenu(cm, pos)


  def OnGridChange(self, ev):
    property=ev.GetProperty()

    if property:
      if property.GetName():
        self.dialog.SetValue(property.GetName(), property.GetValue())
      else: # <new>
        names=property.GetValue()
        if names:
          for name in names:
            self.dialog.SetValue(self.GetServer().GetOid(name), None)
          self.OnClassChange()
    self.dialog.OnCheck()



  def DelValue(self, attrval):
    property=attrval.items.get(self.grid)
    if property:
      self.grid.DeleteProperty(property)


  def SetValue(self, attrval):
    if attrval.GetOid() == self.dialog.rdnOid:
      rdn="%s=%s" % (attrval.name, attrval.value[0].decode('utf8'))
      if rdn != self.RDN:
        self.RDN=rdn
    property=attrval.items.get(self.grid)
    if not property:
      oid=attrval.GetOid()
      if oid in self.may:
        property=self.addProp(oid)
    if property:
      value=attrval.GetValue()
      if property.GetValue() != value:
        property.SetValue(value)


nodeinfo=[
        {"class": Entry, "parents": ["Server", "Entry"], "sort": 10, "new": Entry.newEntryClassList },
        ]


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
#    cls=wx.PasswordEntryDialog
    cls=wx.TextEntryDialog
    dlg=cls(parentWin, xlt("Enter new password:"), xlt("Set password for %s \"%s\"") % (node.typename, node.name))
    if dlg.ShowModal() == wx.ID_OK:
      passwd=dlg.GetValue()

      addList=[]
      chgList=[]


      _must,may=node.GetServer().GetClassSchemaMustMayOids(node.objectClasses)

      userPasswordSchema=node.GetServer().GetAttributeSchema("userPassword")
      if userPasswordSchema.oid in may:
        hash="{SHA}%s" % base64.b64encode(hashlib.sha1(passwd).digest())
        userPassword=AttrVal(None, userPasswordSchema, [hash])

        if userPasswordSchema.oid in node.attribs:
          chgList.append(userPassword)
        else:
          addList.append(userPassword)

      ntPasswordSchema=node.GetServer().GetAttributeSchema("sambaNTpassword")
      if ntPasswordSchema.oid in may:
        md4hash=hashlib.new('md4', passwd.encode('utf-16le')).hexdigest().upper()
        ntPassword=AttrVal(None, ntPasswordSchema, [md4hash])

        if ntPasswordSchema.oid in node.attribs:
          chgList.append(ntPassword)
        else:
          addList.append(ntPassword)

      node.GetConnection().SetPassword(node.dn, passwd)
      if chgList or addList:
        node.GetConnection().Modify(node.dn, chgList, addList, [])
        return True
      return False

    dlg.Destroy()
    return False

menuinfo=[
        {'class': EntryRename, 'nodeclasses': Entry, 'sort': 20 },
        {'class': EntryPassword, 'nodeclasses': Entry, 'sort': 30 },
        ]
