"""Directory role assignments: Microsoft Graph `GET /roleManagement/directory/roleAssignments?$expand=principal`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/unifiedroleassignment?view=graph-rest-1.0
For built-in roles, `roleDefinitionId` is the role template ID that
Conditional Access lists in `includeRoles` and `excludeRoles`. Both IDs are
stored as canonical lower-case GUIDs. `scope` is the directory scope ("/" is
tenant-wide); `app_scope` is the separate application scope, never mixed into
it. The assignments are the admin population, so a single object is refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.model import AttestError
from attest.readers._json import load_records, object_id, optional_text, require, require_str

_ODATA_PREFIX = "#microsoft.graph."


@dataclass(frozen=True)
class RoleAssignment:
    principal_id: str
    principal_kind: str  # "user", "group", "servicePrincipal", or the raw @odata.type
    principal_name: str
    role_id: str
    scope: str  # directoryScopeId, or "" when the export has none
    cite: str
    app_scope: str = ""  # appScopeId, or "" when the export has none


def read(path: Path) -> tuple[RoleAssignment, ...]:
    file = Path(path).name
    assignments = []
    for row, r in enumerate(load_records(path, allow_single=False), start=1):
        principal = r.get("principal")
        if not isinstance(principal, dict):
            raise AttestError(f"{file}: row {row} has no expanded principal (export with $expand=principal; "
                              "a null principal means its account was deleted)")
        odata_type = require_str(principal, "@odata.type", file, row)
        kind = odata_type[len(_ODATA_PREFIX):] if odata_type.startswith(_ODATA_PREFIX) else odata_type
        upn = optional_text(principal.get("userPrincipalName"), file, row, "principal.userPrincipalName")
        display_name = optional_text(principal.get("displayName"), file, row, "principal.displayName")
        assignments.append(RoleAssignment(
            principal_id=object_id(require(r, "principalId", file, row), file, row, "principalId"),
            principal_kind=kind,
            principal_name=upn or display_name,
            role_id=object_id(require(r, "roleDefinitionId", file, row), file, row, "roleDefinitionId"),
            scope=optional_text(r.get("directoryScopeId"), file, row, "directoryScopeId"),
            cite=f"{file}:{row}",
            app_scope=optional_text(r.get("appScopeId"), file, row, "appScopeId"),
        ))
    return tuple(assignments)
