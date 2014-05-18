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
    if self.grid.IsEditorFocused():
      self.grid.CommitChangesFromEditor()
    ok=True
    ok=self.dialog.CheckValid(ok, self.dialog.objectClasses, xlt("Select a structural object class first"))
    if self.RDN:
      rdn=self.RDN.split('=')
      ok=self.dialog.CheckValid(ok, len(rdn) == 2 and rdn[0] and rdn[1], xlt("Invalid RDN format: <attr>=<value>"))
      oid=self.GetServer().GetOid(rdn[0])
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

      class MultiChoiceProperty(wxpg.PGProperty):
        pass
                                
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
        cm=Menu(self)
        cm.Add(self.OnDelAttrs, xlt("Remove %s") % name, xlt("Remove attribute \"%s\"") % name)
        pos=ev.GetPosition() # + (0,20)
        cm.Popup(pos)


  def OnGridChange(self, ev):
    if not self.IsShown():
      return
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
        self.GrandParent.Raise()
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

nodeinfo=[]