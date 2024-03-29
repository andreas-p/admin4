# Name:         globals.py
# Purpose:      XRC editor, global variables
# Author:       Roman Rolinsky <rolinsky@mema.ucl.ac.be>
# Created:      02.12.2002
# RCS-ID:       $Id: globals.py,v 1.31 2007/03/08 15:49:34 ROL Exp $

import wx


# Global constants
progname = 'XRCed'
version = '0.1.8-4-admin4'
# Minimal wxWidgets version
MinWxVersion = (2,6,0)
if wx.VERSION[:3] < MinWxVersion:
    print ('''\
******************************* WARNING **************************************
  This version of XRCed may not work correctly on your version of wxWidgets.
  Please upgrade wxWidgets to %d.%d.%d or higher.
******************************************************************************''' % MinWxVersion)    



# Global variables

class Globals:
    panel = None
    tree = None
    frame = None
    tools = None
    undoMan = None
    testWin = None
    testWinPos = wx.DefaultPosition
    currentXXX = None

    def _makeFonts(self):
        self._sysFont = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        self._labelFont = wx.Font(self._sysFont.GetPointSize(), wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self._modernFont = wx.Font(self._sysFont.GetPointSize(), wx.MODERN, wx.NORMAL, wx.NORMAL)
        self._smallerFont = wx.Font(self._sysFont.GetPointSize()-2, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
    def sysFont(self):
        if not hasattr(self, "_sysFont"): self._makeFonts()
        return self._sysFont
    def labelFont(self):
        if not hasattr(self, "_labelFont"): self._makeFonts()
        return self._labelFont
    def modernFont(self):
        if not hasattr(self, "_modernFont"): self._makeFonts()
        return self._modernFont
    def smallerFont(self):
        if not hasattr(self, "_smallerFont"): self._makeFonts()
        return self._smallerFont
    

g = Globals()
