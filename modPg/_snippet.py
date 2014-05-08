# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
from tree import DragTreeCtrl, TreeItemData
from wh import xlt, Menu
from adm import images
 
class Snippet:
  def __init__(self, id, parent, name, text, sort):
    self.id=id
    self.sort=sort
    self.name=name
    self.parent=parent
    self.text=text
    self.treeitem=None
    
  def IsGroup(self):
    return not self.text
    

class SnippetTree(DragTreeCtrl):
  def __init__(self, parentWin, server, editor):
    DragTreeCtrl.__init__(self, parentWin, "Snippets", style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT)
    self.editor=editor
    self.server=server
    self.snippets={}

    self.Bind(wx.EVT_RIGHT_DOWN, self.OnTreeRightClick)
    self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnTreeActivate)
    
    rootSnippets=[]
    set=self.server.GetConnection().ExecuteSet("SELECT * FROM %s ORDER BY parent, sort" % server.snippet_table)
    for row in set:
      snippet=Snippet(row['id'], row['parent'], row['name'], row['snippet'], row['sort'])
      self.snippets[snippet.id]=snippet
      if not snippet.parent:
        rootSnippets.append(snippet)
        
    for snippet in rootSnippets:
      if not snippet.parent:
        self.AppendSnippet(snippet, None, self.GetRootItem())      
        self.checkChildren(snippet)

  def getSnippetDict(self, snippet):
    dict= { 'table': self.server.snippet_table,
             'id': snippet.id, 'parent': snippet.parent, 'sort': snippet.sort,
             'name': self.server.quoteString(snippet.name),
             'text': self.server.quoteString(snippet.text)
           }
    return dict
  
    
  def updateSnippet(self, snippet):
    self.server.GetConnection().ExecuteSingle("""
UPDATE %(table)s
   SET name=%(name)s, sort=%(sort)f, parent=%(parent)d, snippet=%(text)s
 WHERE id=%(id)d""" % self.getSnippetDict(snippet))

  def insertSnippet(self, snippet):
                                                 
    sql="""
INSERT INTO %(table)s(name, parent, sort, snippet)
 VALUES ( %(name)s, %(parent)d, %(sort)f, %(text)s )
 RETURNING id""" % self.getSnippetDict(snippet)

    id=self.server.GetConnection().ExecuteSingle(sql)
    snippet.id=id
    return id
  
  def getSnippetName(self, snippet):
    if snippet.name:
      return snippet.name
    else:
      maxtextlen=80
      if len(snippet.text) < maxtextlen:
        return snippet.text
      else:
        return snippet.text[:maxtextlen] + "..."
  
  def AppendSnippet(self, snippet, text=None, parentItem=None):
    if not parentItem:
      parent=self.GetNode()
      if parent:
        parentItem=parent.treeitem
        if parent.text:
          group=self.snippets.get(parent.parent)
          if group:
            parentItem=group.treeitem
          else:
            parentItem=self.GetRootItem()
      else:
        parentItem=self.GetRootItem()

    if not isinstance(snippet, Snippet):
      parent=0
      if parentItem:
        p=self.GetNode(parentItem)
        if p:
          parent=p.id
      maxSort=1
      for s in self.snippets.values():
        if s.parent == parent and s.sort > maxSort:
          maxSort=s.sort
          
      snippet=Snippet(None, parent, snippet, text, maxSort+1)
      self.insertSnippet(snippet)

    if snippet.IsGroup():
      image= images.GetModuleId(self, 'snippets')
    else:
      image= images.GetModuleId(self, 'snippet')
    item=self.AppendItem(parentItem, self.getSnippetName(snippet), image=image, selectedImage=image, data=TreeItemData(snippet))
    self.snippets[snippet.id] = snippet
    snippet.treeitem=item
    return True
      

  def ReplaceSnippet(self, text):
    snippet=self.GetNode()
    if snippet:
      snippet.text=text
      self.updateSnippet(snippet)
      self.GetParent().SetStatus(xlt("Snipped updated."))
    return False

  def OnUpdateSnippet(self, evt):
    sql=self.GetParent().getSql()
    if sql:
      self.ReplaceSnippet(sql)
      
  def OnRenameSnippet(self, evt):
    snippet=self.GetNode()
    if snippet:
      dlg=wx.TextEntryDialog(self, xlt("Name"), xlt("Rename snippet"), snippet.name)
      if dlg.ShowModal() == wx.ID_OK:
        snippet.name = dlg.GetValue()
        self.updateSnippet(snippet)
        self.SetItemText(snippet.treeitem, self.getSnippetName(snippet))
        self.GetParent().SetStatus(xlt("Snippet renamed."))

  def OnDelSnippet(self, evt):
    snippet=self.GetNode()
    if snippet:
      self.server.GetConnection().ExecuteSingle("DELETE FROM %(table)s WHERE id=%(id)d" % self.getSnippetDict(snippet))
      self.Delete(snippet.treeitem)
      del self.snippets[snippet.id]
      self.GetParent().SetStatus(xlt("Snippet deleted."))
      
  def OnAddGroup(self, evt):
    dlg=wx.TextEntryDialog(self, xlt("Group name"), xlt("Add group"))
    if dlg.ShowModal() == wx.ID_OK:
      name=dlg.GetValue()
      if name:
        self.AppendSnippet(name)
      
  def OnTreeRightClick(self, evt):
    item, _flags=self.HitTest(evt.GetPosition())
    if item and item != self.GetSelection():
      self.SelectItem(item)
    
    cm=Menu()
    if item:
      snippet=self.GetNode(item)
      if snippet.IsGroup():
        cm.Append(self.GetParent().BindMenuId(self.OnRenameSnippet), xlt("Rename"), xlt(("Rename group")))
        id=self.GetParent().BindMenuId(self.OnDelSnippet)
        cm.Append(id, xlt("Delete"), xlt(("Delete group")))
        for s in self.snippets.values():
          if s.parent == snippet.id:
            cm.Enable(id, False)
            break;
      else:
        cm.Append(self.GetParent().BindMenuId(self.OnUpdateSnippet), xlt("Update"), xlt(("Update snippet")))
        cm.Append(self.GetParent().BindMenuId(self.OnRenameSnippet), xlt("Rename"), xlt(("Rename snippet")))
        cm.Append(self.GetParent().BindMenuId(self.OnDelSnippet), xlt("Delete"), xlt(("Delete snippet")))
      cm.AppendSeparator()
    cm.Append(self.GetParent().BindMenuId(self.OnAddGroup), xlt("Add group"), xlt(("Add group")))
    self.PopupMenu(cm, evt.GetPosition())
  
  def ExecuteDrag(self, targetItem):
    targetSnippet=self.GetNode(targetItem)
    snippet=self.GetNode(self.currentItem)
    if self.currentItem != targetItem and targetSnippet != snippet:
      parentItem=self.GetRootItem()
      image=self.GetItemImage(snippet.treeitem)
      self.Delete(snippet.treeitem)
      if targetSnippet:
        if targetSnippet.IsGroup():
          parentItem=targetSnippet.treeitem
          snippet.parent=targetSnippet.id
        else:
          group=self.snippets.get(targetSnippet.parent)
          snippet.parent=targetSnippet.parent
          if group:
            parentItem=group.treeitem
          snippet.sort=targetSnippet.sort+1
          nextItem=self.GetNextSibling(targetItem)
          if nextItem:
            nextSnippet=self.GetNode(nextItem)
            if nextSnippet and nextSnippet.parent == targetSnippet:
              snippet.sort=(nextSnippet.sort + targetSnippet.sort)/2
          item=self.InsertItem(parentItem, targetItem, self.getSnippetName(snippet), image=image, data=TreeItemData(snippet))
          snippet.treeitem = item
          targetSnippet=None

      if targetSnippet:
        self.AppendSnippet(snippet, None, parentItem)
      self.checkChildren(snippet)


  def checkChildren(self, snippet):
    for child in self.snippets.values():
      if child.parent == snippet.id:
        self.AppendSnippet(child, None, snippet.treeitem)
        self.checkChildren(child)     


  def OnTreeActivate(self, evt):
    snippet= self.GetNode()
    if snippet:
      self.editor.ReplaceSelection(snippet.text)
    self.editor.SetFocus()
      