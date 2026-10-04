"""Directory role assignments: Microsoft Graph `GET /roleManagement/directory/roleAssignments?$expand=principal`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/unifiedroleassignment?view=graph-rest-1.0
For built-in roles, `roleDefinitionId` is the role template ID that
Conditional Access lists in `includeRoles` and `excludeRoles`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.model import AttestError
from attest.readers._json import load_records, require_str

_ODATA_PREFIX = "#microsoft.graph."


@dataclass(frozen=True)
class RoleAssignment:
    principal_id: str
    principal_kind: str  # "user", "group", "servicePrincipal", or the raw @odata.type
    principal_name: str
    role_id: str
    scope: str
    cite: str


def read(path: Path) -> tuple[RoleAssignment, ...]:
    file = Path(path).name
    assignments = []
    for row, r in enumerate(load_records(path), start=1):
        principal = r.get("principal")
        if not isinstance(principal, dict):
            raise AttestError(f"{file}: row {row} has no expanded principal (export with $expand=principal; a null principal means its account was deleted)")
        odata_type = require_str(principal, "@odata.type", file, row)
        kind = odata_type[len(_ODATA_PREFIX):] if odata_type.startswith(_ODATA_PREFIX) else odata_type
        assignments.append(RoleAssignment(
            principal_id=require_str(r, "principalId", file, row),
            principal_kind=kind,
            principal_name=principal.get("userPrincipalName") or principal.get("displayName") or "",
            role_id=require_str(r, "roleDefinitionId", file, row),
            scope=r.get("directoryScopeId") or r.get("appScopeId") or "",
            cite=f"{file}:{row}",
        ))
    return tuple(assignments)
