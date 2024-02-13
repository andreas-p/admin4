# TODO

## core

- hide password preference

- SSL certificate management

## modImap

- check mailbox move target name
- get/set other annotations for mailbox and server (no plans)


## modLdap

#### New Object
- default values preferences

ignoreCert:
ldap.OPT_X_TLS_ALLOW

checkCert:
- ldap.set_option(ldap.OPT_X_TLS_NEWCTX,ldap.OPT_X_TLS_DEMAND)
- ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT,ldap.OPT_X_TLS_DEMAND)
- ldap.set_option(ldap.OPT_X_TLS_CACERTFILE,certfile)

#### objectClasses 

- mailGroup/member
- groupOfUniqueNames/uniqueMember

#### ToFix

- PrimaryGroupSid
- Group add description/displayname in list
- deleteObjClass: remove attribs
- nach rename refresh (2nd rename fails)
- user.scs doppelt

## modPg

####Browser

- update Favorites when deleting on
- Triggers
- Edit Table: Table, Column

#### DataGrid

- Drag/drop not from MouseDown for wx>3.0
- OnFilterValidate and executeQuery catch error w/o logging
- FK drilldown
- float edit

ShowBusy abort enable

ResetPerspective

## modBind

Check sanity of PTR data
