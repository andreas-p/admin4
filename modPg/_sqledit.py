# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# http://www.scintilla.org/
import wx
import wx.stc as stc
from wh import modPath


class SqlEditor(stc.StyledTextCtrl):
  keywords=[]
  
  def __init__(self, parent, font):
    stc.StyledTextCtrl.__init__(self, parent)
    self.MarkerDefine(0, stc.STC_MARK_ARROW)
    self.MarkerSetBackground(0, wx.Colour(255,0,0))
#    self.SetMarginWidth(0,0)
    self.SetIndent(2)

    if font:
      for i in range(24):
        self.StyleSetFont(i, font)

    # STC_SQL_DEFAULT
    # STC_SQL_COMMENT, STC_SQL_COMMENTLINE, STC_SQL_COMMENTDOC          - comments
    # STC_SQL_WORD, STC_SQL_USER1 STC_SQL_USER2 STC_SQL_USER3 STC_SQL_USER4   - keywordlists 0,4,5,6,7
   
    # STC_SQL_NUMBER, STC_SQL_CHARACTER, STC_SQL_STRING, STC_SQL_OPERATOR   - num, '', "", +-()*/
    # STC_SQL_SQLPLUS, STC_SQL_SQLPLUS_PROMPT, STC_SQL_SQLPLUS_COMMENT
    # STC_SQL_COMMENTLINEDOC STC_SQL_COMMENTDOCKEYWORD STC_SQL_COMMENTDOCKEYWORDERROR
    # STC_SQL_WORD2 
    # STC_SQL_QUOTEDIDENTIFIER STC_SQL_IDENTIFIER

    if not self.keywords:
      self.fillKeywords()
      if not self.keywords:
        return
      
    commentColor=wx.Colour(128,128,128)
    keywordColor=wx.Colour(0, 0, 128)
    constColor=wx.Colour(0,128,0)

    self.SetLexer(stc.STC_LEX_SQL)

    self.StyleSetForeground(stc.STC_SQL_DEFAULT, wx.BLACK)

    self.StyleSetForeground(stc.STC_SQL_WORD, keywordColor)
    self.StyleSetBold(stc.STC_SQL_WORD, True)
    self.SetKeyWords(0, self.keywords)
    
    self.StyleSetForeground(stc.STC_SQL_COMMENT, commentColor)
    self.StyleSetForeground(stc.STC_SQL_COMMENTLINE, commentColor)
    self.StyleSetForeground(stc.STC_SQL_COMMENTDOC, commentColor)
    
    self.StyleSetForeground(stc.STC_SQL_NUMBER, constColor)
    self.StyleSetForeground(stc.STC_SQL_CHARACTER, constColor)
    

  def fillKeywords(self):
    f=open(modPath("kwlist.h", self))
    lines=f.read()
    f.close()
    
    keywords=[]
    for line in lines.splitlines():
      if line.startswith("PG_KEYWORD("):
        tokens=line.split(',')
        keyword=tokens[0][12:-1].lower()
        keywords.append(keyword)
        # if tokens[2].lstrip().startswith("RESERVED")
        # RESERVED, UNRESERVED, TYPE_FUNC_NAME, COL_NAME
    self.keywords=" ".join(keywords)
        
  def BindProcs(self, changeProc, updateUiProc):
    if changeProc:
      self.Bind(stc.EVT_STC_CHANGE, changeProc)
    if updateUiProc:
      self.Bind(stc.EVT_STC_UPDATEUI, updateUiProc)
    
  def MarkerDelete(self):
    self.MarkerDeleteAll(-1)


  def GetSelectOffset(self):
      a,e=self.GetSelection()
      if a == e:
        return 0
      else:
        return self.LineFromPosition(a)

  def MarkerSet(self, line):
    self.MarkerAdd(line, 0)
    
          
    