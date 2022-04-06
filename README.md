# Admin4


Admin4 is a tool for server maintenance via several plugin modules, running on Windows,
Mac OSX, Linux and many more platforms. Currently, plugins for BIND DNS, LDAP, IMAP 
and PostgreSQL are included. It is designed as a framework, using Python 
for fast development of plugins and custom modifications.


## Features

The **Bind DNS** plugin supports browsing and editing of DNS zones. 
The plugin should be able to query (axfr) any type of server, and 
performs updates via DDNS which insures that it won't interfere with other
DDNS clients (DHCP, SAMBA4). For Bind 9.7 and up, statistics are supported
as well and used to retrieve the server's zones automatically.

The **LDAP** plugin features browsing and generic editing of all types of 
LDAP entries with schema support. In addition, high-level editing of objects
like users, groups and samba domains is supported. Custom objectClasses and attributes
can easily be added. The goal of the plugin was to replace the
windows-only ldapadmin tool with a portable solution.

The **IMAP** plugin supports browsing and maintaining of mailboxes
for standard IMAP4 mail storage servers. In is an everyday replacement
for cyradm for Cyrus IMAPD servers, and should work with other implementations too.

The **PostgreSQL** plugin features a nice query tool, a data modification tool
and an object browser. It's aimed to replace pgAdmin3/pgAdmin4 with a modified feature
set targeted at professionals. It supports gui editing only for common tasks
and objects to keep the GUI lean, and emphasizes on features that increase productivity
like object favorites, sql snippets and filter presets. The PostgreSQL module is still
work-in-progress: object browsing is currently restricted to displaying
the most important objects.

## Implementation

Python3.7+
wxPython 4.1+

## Website

http://admin4.org


