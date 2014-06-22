# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
from tree import DragTreeCtrl, TreeItemData
from wh import xlt, Menu
from adm import images
from _pgsql import pgQuery
 
class Snippet:
  def __init__(self, id, parent, name, text, sort):
    self.id=id
    self.sort=sort
    self.name=name
    self.parent=parent
    self.text=text
    self.treeitem=None
    self.prevText=None
    
  def IsGroup(self):
    return not self.text
    

class SnippetTree(DragTreeCtrl):
  def __init__(self, parentWin, server, editor):
    DragTreeCtrl.__init__(self, parentWin, "Snippets", style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT)
    self.editor=editor
    self.server=server
    self.frame=parentWin
    self.snippets={}

    self.Bind(wx.EVT_RIGHT_DOWN, self.OnTreeRightClick)
    self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelChanged)
    self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnTreeActivate)
    
    rootSnippets=[]
    if self.frame.snippet_table:
      set=self.server.GetCursor().ExecuteSet("SELECT * FROM %s ORDER BY parent, sort" % self.frame.snippet_table)
      for row in set:
        snippet=Snippet(row['id'], row['parent'], row['name'], row['snippet'], row['sort'])
        self.snippets[snippet.id]=snippet
        if not snippet.parent:
          rootSnippets.append(snippet)
          
        
      for snippet in rootSnippets:
        if not snippet.parent:
          self.AppendSnippet(snippet, parentItem=self.GetRootItem())      
          self.checkChildren(snippet)
      for snippet in self.snippets.values():
        if not snippet.treeitem:
          self.AppendSnippet(snippet, parentItem=self.GetRootItem())
    else:
      item=self.AppendItem(self.GetRootItem(), xlt("Snippets not available:"))
      item=self.AppendItem(item, xlt("Server not instrumented."))
      self.ExpandAll()

    
  def updateSnippet(self, snippet):
    query=pgQuery(self.frame.snippet_table, self.server.GetCursor())
    query.AddColVal('parent', snippet.parent)
    query.AddColVal('sort', snippet.sort)
    query.AddColVal('name', snippet.name)
    query.AddColVal('snippet', snippet.text)
    query.AddWhere('id', snippet.id)
    query.Update()


  def insertSnippet(self, snippet):
    query=pgQuery(self.frame.snippet_table, self.server.GetCursor())
    query.AddColVal('parent', snippet.parent)
    query.AddColVal('sort', snippet.sort)
    query.AddColVal('name', snippet.name)
    query.AddColVal('snippet', snippet.text)
    id=query.Insert("id")
    snippet.id=id
    return id
  
  def OnDelSnippet(self, evt):
    snippet=self.GetNode()
    if snippet:
      query=pgQuery(self.frame.snippet_table, self.server.GetCursor())
      query.AddWhere('id', snippet.id)
      query.Delete()
      self.Delete(snippet.treeitem)
      del self.snippets[snippet.id]
      self.frame.SetStatus(xlt("Snippet deleted."))


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
      

  def CanReplace(self):
    if not self.frame.snippet_table:
      return False
    a,e=self.editor.GetSelection()
    if a==e and self.editor.GetLineCount() < 2 and not self.frame.getSql():
      return False

    snippet=self.GetNode()
    return snippet and snippet.text
  
  def ReplaceSnippet(self, text):
    snippet=self.GetNode()
    if snippet:
      snippet.prevText=snippet.text
      snippet.text=text
      self.updateSnippet(snippet)
      self.frame.SetStatus(xlt("Snippet updated."))
    return False

  def OnReplaceSnippet(self, evt):
    sql=self.frame.getSql()
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
        self.frame.SetStatus(xlt("Snippet renamed."))

  def OnRevertSnippet(self, evt):
    snippet=self.GetNode()
    if snippet and snippet.prevText:
      snippet.text=snippet.prevText
      snippet.prevText=None
      self.updateSnippet(snippet)
      self.frame.SetStatus(xlt("Snippet reverted."))
    return False

     
  def OnAddGroup(self, evt):
    dlg=wx.TextEntryDialog(self, xlt("Group name"), xlt("Add group"))
    if dlg.ShowModal() == wx.ID_OK:
      name=dlg.GetValue()
      if name:
        self.AppendSnippet(name, parentItem=self.GetRootItem())
      
  def OnTreeSelChanged(self, evt):
    self.frame.updateMenu()

  def OnTreeRightClick(self, evt):
    item, _flags=self.HitTest(evt.GetPosition())
    if item and item != self.GetSelection():
      self.SelectItem(item)
    
    cm=Menu(self.frame)
    if item:
      snippet=self.GetNode(item)
      if snippet.IsGroup():
        cm.Add(self.OnRenameSnippet, xlt("Rename"), xlt(("Rename group")))
        item=cm.Add(self.OnDelSnippet, xlt("Delete"), xlt(("Delete group")))
        for s in self.snippets.values():
          if s.parent == snippet.id:
            cm.Enable(item, False)
            break;
      else:
        cm.Add(self.OnReplaceSnippet, xlt("Replace"), xlt(("Replace snippet text")))
        cm.Add(self.OnRenameSnippet, xlt("Rename"), xlt(("Rename snippet")))
        item=cm.Add(self.OnRevertSnippet, xlt("Revert"), xlt(("Revert snippet to previous text")))
        cm.Enable(item, snippet.prevText != None)
        cm.Add(self.OnDelSnippet, xlt("Delete"), xlt(("Delete snippet")))
      cm.AppendSeparator()
    cm.Add(self.OnAddGroup, xlt("Add group"), xlt(("Add group")))
    cm.Popup(evt)
  
  def ExecuteDrag(self, targetItem):
    if targetItem:  targetSnippet=self.GetNode(targetItem)
    else:           targetSnippet=None
      
    snippet=self.GetNode(self.currentItem)
    parentItem=self.GetRootItem()
    image=self.GetItemImage(snippet.treeitem)
    if self.currentItem != targetItem and targetSnippet != snippet:
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
      else:
          item=self.AppendItem(parentItem, self.getSnippetName(snippet), image=image, data=TreeItemData(snippet))
          snippet.treeitem = item
          snippet.parent=0
      if targetSnippet:
        self.AppendSnippet(snippet, None, parentItem)
      self.updateSnippet(snippet)
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
      self.frame.updateMenu()
    self.editor.SetFocus()
      