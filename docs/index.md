<!-- # Xolo API -->
<p align="center">
  <img src="./assets/logo.png" alt="Xolo" width="220" />
</p>

<p align="center">
  <a href="https://github.com/muyal-research-group/xolo-api/actions/workflows/ci.yml"><img src="https://github.com/muyal-research-group/xolo/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/muyal-research-group/xolo"><img src="https://codecov.io/gh/muyal-research-group/xolo-api/branch/master/graph/badge.svg" alt="codecov"></a>
  <a href=""><img src="https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmuyal-research-group%2Fxolo-api%2Fmaster%2Fpyproject.toml&query=%24.tool.poetry.version&label=Version&logo=pypi&color=0A7ABC" alt="TestPyPI"></a>
  <a href="https://github.com/muyal-research-group/xolo-api?tab=MIT-1-ov-file"><img src="https://img.shields.io/badge/license-MIT-0A7ABC" alt="License"></a>
  <!-- <a href="https://github.com/muyal-research-group/xolo-api?tab=MIT-1-ov-file"><img src="https://img.shields.io/badge/license-Fair%20Source-0A7ABC" alt="License"></a> -->
</p>

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
