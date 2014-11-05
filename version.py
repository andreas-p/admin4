# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import sys
if not hasattr(sys, 'frozen'):
  import wxversion
  import os, platform
  wxversion._EM_DEBUG=True
  
  if platform.system() == "Darwin":
    wxversion.select('2.9.4')
  else:
    wxversion.ensureMinimal("3.0")
  
    if platform.system() == "Windows":
      minVersion="3.0.1.1"
      for iv in wxversion._find_installed():
        ver=os.path.basename(iv.pathname).split('-')[1]
        if ver >= minVersion:
          break
        if ver >= '3.0':
          for f in os.listdir(iv.pathname):
            if f.endswith('.egg-info'):
              ver=f.split('-')[1]
              if ver >= minVersion:
                break
              else:
                raise wxversion.VersionError('wxPython minimum usable version is %s' % minVersion)

try:
  from __version import *
except:
  version="2.x"
  modDate=revDate=tagDate=None
  revLocalChange=True
  revDirty=True
  revOriginChange=True
  requiredAdmVersion="2.0"

libVersion="2.1.9"

description="4th generation\nAdministration Tool\n\nHelp and manual: http://www.admin4.org/docs"
vendor="PSE"
vendorDisplay="PSE Consulting"
copyright="(c) 2013-2014 PSE Consulting Andreas Pflug"
license="Apache License V2.0"
author="PSE Consulting Andreas Pflug"
