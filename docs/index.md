# Xolo API

Xolo is a FastAPI-based **Identity and Access Management** platform that combines several authorization models under one API. Instead of forcing every system into one policy style, Xolo lets you mix **ACL**, **ABAC Event**, **ABAC community policies**, and **NGAC** depending on the domain problem.

## Release target

This documentation set is written for the **0.1.0a0** release line.

## What Xolo provides

- account lifecycle and ownership
- user lifecycle and authentication
- JWT-based API access
- scope and license management
- API key management
- an internal super-admin UI
- multiple access-control models in the same service
- configurable email delivery for signup and password reset flows

## Main concepts

| Concept | Meaning in Xolo |
| --- | --- |
| **Account** | the top-level owner for users, scopes, licenses, and API Keys |
| **User** | an authenticated person or system identity inside an account |
| **Scope** | a named capability or domain permission |
| **License** | a time-bounded grant that ties a user to a scope |
| **API key** | a server-to-server credential carrying named scopes |
| **Super admin** | an operator allowed to perform create/list/delete admin actions |

## Access-control systems

### ACL

Use ACL when you want **ownership and sharing** over named resources.

### ABAC Event

Use persisted ABAC Event when you want decisions based on a request tuple like:

`(subject, resource, location, time window, action)`

### ABAC community policies

Use the community-policy subsystem when you want **in-memory** rule grouping and fast evaluation without persistence across restarts.

### NGAC

Use NGAC when you want **graph-modeled authorization** with policy classes, assignments, associations, and AND semantics across policy domains.

## Read this next

- [Getting started](getting-started.md)
- [Authentication and admin](authentication-and-admin.md)
- [Access control models](access-control.md)
- [Architecture overview](architecture.md)
- [Deployment](deployment.md)
