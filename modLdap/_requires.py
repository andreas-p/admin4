# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# Mac OSX 10.8, 10.9:
# xcode-select --install
# sudo easy_install pip
# sudo pip install python-ldap
#
# Debian:
# apt-get install python-ldap
#
# Windows:
# https://pypi.python.org/pypi/python-ldap
# current: 
# https://pypi.python.org/packages/2.7/p/python-ldap/python-ldap-2.4.12.win32-py2.7.msi
# alternate:
# http://www.lfd.uci.edu/~gohlke/pythonlibs/
#
# other OS:
# http://www.python-ldap.org/download.shtml
 
def GetPrerequisites(info=False):
  try:
    import ldap
    if ldap.__version__ < "3.1.":
      if info:
        print ("ldap too old")
      return None
    import wx
    if wx.VERSION < (4,1):
      if info:
        print ("wxPython too old")
      return None
    
    return "ldap"
  except:
    if info:
      print ("ldap missing")
    pass
  return None
