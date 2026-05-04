# Access control models

Xolo supports several authorization styles because real systems often need more than one.

## ACL

**Base path:** `/api/v4/acl`

ACL is the ownership-and-sharing model.

### Best for

- resource ownership
- per-resource grants
- group-based sharing

### Core ideas

- the first claimer becomes owner
- owners grant and revoke permissions
- permissions can be granted to users or groups
- effective access is the union of direct and group permissions

## ABAC Event

**Base path:** `/api/v4/abac`

ABAC Event stores policies in MongoDB and evaluates requests against event tuples:

`(subject, resource, location, time, action)`

### Best for

- context-aware access checks
- wildcard matching
- persistent rule sets

### Evaluation model

- evaluate all matching policies
- **DENY overrides ALLOW**
- no match means deny

## ABAC community policies

**Base path:** `/api/v4/policies`

This subsystem uses in-memory policy communities built around the `xolo.abac` library.

### Best for

- experimentation
- fast in-memory evaluation
- graph/community-based grouping

### Important limitation

Policy communities are **not persisted** across process restarts.

## NGAC

**Base path:** `/api/v4/ngac`

NGAC models the authorization system as a graph of users, objects, attributes, and policy classes.

### Best for

- graph-shaped authorization domains
- multi-domain policy composition
- fine-grained policy traversal

### Important rule

If an object belongs to multiple policy classes, the required permission must be satisfied through **every** governing policy class.

## Supporting IAM modules

### Scopes

Scopes are named permissions/capabilities that power API Keys, user assignments, and licenses.

### Licenses

Licenses bind users to scopes and can expire.

### API Keys

API Keys carry named scopes for service access.

### Users

Users authenticate, receive JWTs, and interact with the access-control subsystems.
