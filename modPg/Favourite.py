# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import xlt
from Schema import Schema
from Table import Table
from Sequence import Sequence
from View import View
from Function import Function

class Favourites(adm.Node):
  typename=xlt("Favourites")
  shortname=xlt("Favourites")
  defaultname=xlt("unsorted")
  def __init__(self, parentNode):
    super(Favourites, self).__init__(parentNode, xlt(Favourites.defaultname))
    
  @staticmethod
  def GetInstances(parentNode):
    if parentNode.GetServer().fav_table:
      return [Favourites(parentNode)]
    return None

  def DoRefresh(self):
    for treename, fil in self.treeitems.items():
      tree=adm.trees[treename]
      favitem=fil[0] # tree.Collapse(favitem)
      for child in self.childnodes[:]:
        itemlist=child.treeitems.get(treename)
        if itemlist:
          for item in itemlist:
            if tree.IsChild(item, favitem):
              tree.DeleteItem(item)
        self.removeChild(child)
      self.properties=[]
      
  def GetProperties(self):
    self.properties=[]
    self.PopulateChildren()
    for child in self.childnodes:
      self.properties.append( (child.name, child.comment, child.GetIcon()))
    return self.properties
      
    

class Favourite(adm.Node):
  typename=xlt("Favourite")
  shortname=xlt("Favourite")

  def DoRefresh(self):
    for c in self.childnodes:
      for treename, itemlist in c.treeitems.items():
        item=itemlist[0]
        tree=adm.trees[treename]
        itemlist=tree.GetChildItems(item)
    
        tree.Collapse(item)
        for item in itemlist:
          tree.DeleteItem(item)

    self.childnodes=[]
    self.properties=[]
    self.RefreshVolatile(True)


  @staticmethod
  def GetInstances(parentNode):
    instances=[]
    db=parentNode.parentNode
    if db.favourites:
      schemaOids=db.GetCursor().ExecuteList("SELECT DISTINCT relnamespace FROM pg_class WHERE oid IN (%s)" % ",".join(map(str, db.favourites)))
      coll=db.GetCollection(Schema)
      coll.PopulateChildren()
      schemanodes=[]
      schemaOids=db.GetCursor().ExecuteList("SELECT DISTINCT relnamespace FROM pg_class WHERE oid IN (%s)" % ",".join(map(str, db.favourites)))
      for schema in coll.childnodes:
        if schema.GetOid() in schemaOids:
          schemanodes.append(schema)
          schema.PopulateChildren()

      for schema in schemanodes:
        tables=schema.GetCollection(Table)
        for oid in db.favourites:
          t=tables.FindNode(Table, str(oid))
          if t:
            instances.append(t)
        
      for schema in schemanodes:
        views=schema.GetCollection(View)
        if views:
          for oid in db.favourites:
            v=views.FindNode(View, str(oid))
            if v:
              instances.append(v)

      for schema in schemanodes:
        funcs=schema.GetCollection(Function)
        if funcs:
          for oid in db.favourites:
            f=funcs.FindNode(Function, str(oid))
            if f:
              instances.append(f)
      
      for schema in schemanodes:
        sequences=schema.GetCollection(Sequence)
        if sequences:
          for oid in db.favourites:
            s=sequences.FindNode(Sequence, str(oid))
            if s:
              instances.append(s)

    return instances
  
  

nodeinfo= [ 
           { "class" : Favourites, "parents": ["Database"], "sort": 80, },
           { "class" : Favourite, "parents": ["Favourites"], "sort": 80, }
           ]

class AddFavourite:
  name=xlt("Add Favourite")
  help=xlt("Make object a favourite")
  
  @staticmethod
  def CheckAvailableOn(node):
    return hasattr(node, 'favtype') and node.GetOid() not in node.GetDatabase().favourites and node.GetServer().fav_table
  
  @staticmethod
  def OnExecute(_parentwin, node):
    node.GetServer().AddFavourite(node)
    favgroup=xlt(Favourites.defaultname)
    fav=node.GetDatabase().FindNode(Favourites, favgroup)
    if not fav:
      fav=Favourites(node.GetDatabase(), favgroup)
      node.GetDatabase().appendNode(fav)
      
    if fav.childnodes and not node in fav.childnodes:
      fav.appendChild(node)
    return True

class DelFavourite:
  name=xlt("Delete Favourite")
  help=xlt("Delete object from favourite list")
  
  @staticmethod
  def CheckAvailableOn(node):
    return hasattr(node, 'favtype') and node.GetOid() in node.GetDatabase().favourites and node.GetServer().fav_table
  
    
  @staticmethod
  def OnExecute(_parentwin, node):
    node.GetServer().DelFavourite(node)
    return True
 

      
menuinfo = [ 
            { "class" : AddFavourite, "nodeclasses" : Table, 'sort': 40 },
            { "class" : DelFavourite, "nodeclasses" : Table, 'sort': 40 },
            ]
