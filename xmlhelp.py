# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import xml.dom.minidom as minidom


class Element(minidom.Element):
  def addElement(self, name):
    e=self.ownerDocument.createElement(name)
    self.appendChild(e)
    return e

  def addElementIfText(self, name, val):
    if val != None:
      return self.addElementText(name, val)
    return None

  def addElementText(self, name, val):
    t=minidom.Text()
    if val:
      t.data=str(val)
    else:
      t.data=""
    t.ownerDocument=self.ownerDocument

    e=self.addElement(name)
    e.appendChild(t)
    return e

  def addElementTree(self, el):
    if isinstance(el, str):
      doc=minidom.parseString(el)
      el=doc.documentElement
    e=self.ownerDocument.importNode(el, True)
    self.appendChild(e)
    return e

  def setAttribute(self, name, val):
    minidom.Element.setAttribute(self, name, val)
    return self

  def setAttributes(self, attribs):
    for key, val in attribs.items():
      self.setAttribute(key, str(val))
    return self

  def getText(self):
    pt=[]
    for node in self.childNodes:
      if node.nodeType == node.TEXT_NODE:
        pt.append(node.data)
    return "".join(pt)

  def getElements(self, name):
    return self.getElementsByTagName(name)

  def getElement(self, name):
    es=self.getElementsByTagName(name)
    if es:
      return es[0]
    return None

  def getElementText(self, name, default=None):
    n=self.getElement(name)
    if n:
      return n.getText()
    return default

  def prettyXml(self):
    lines=self.toprettyxml().splitlines(1)
    out=[]
    for line in lines:
      if line.strip():
        out.append(line)
    return "".join(out)



class DOMImplementation(minidom.DOMImplementation):
  def _create_document(self):
    return Document()

class Document(minidom.Document):
  implementation=DOMImplementation()

  @staticmethod
  def create(rootName):
    doc=Document.implementation.createDocument(None, rootName, None)
    return doc.documentElement

  @staticmethod
  def parseRaw(txt):
    doc=minidom.parseString(txt)
    return doc.documentElement

  @staticmethod
  def parse(txt):
    doc=Document.implementation.createDocument(None, "none", None)
    rootRaw=Document.parseRaw(txt)
    root=doc.importNode(rootRaw, True)
    doc.rootElement=root
    return root

  @staticmethod
  def parseFile(filename):
    doc=Document.implementation.createDocument(None, "none", None)
    raw=minidom.parse(filename)
    root=doc.importNode(raw.documentElement, True)
    doc.rootElement=root
    return root

  def createElement(self, tagName):
    e=Element(tagName)
    e.ownerDocument=self
    return e

  def createElementNS(self, namespaceURI, qualifiedName):
    prefix, _localName = minidom._nssplit(qualifiedName)
    e = Element(qualifiedName, namespaceURI, prefix)
    e.ownerDocument = self
    return e
