"""One reader per export format, by the name a firm's manifest uses."""
from attest.readers import (
    defender_machines,
    entra_ca_policies,
    entra_registration,
    entra_role_assignments,
    entra_security_defaults,
    entra_users,
    intune_devices,
    veeam_users,
)

READERS = {
    "entra_users": entra_users.read,
    "entra_registration": entra_registration.read,
    "entra_ca_policies": entra_ca_policies.read,
    "entra_security_defaults": entra_security_defaults.read,
    "entra_role_assignments": entra_role_assignments.read,
    "intune_devices": intune_devices.read,
    "defender_machines": defender_machines.read,
    "veeam_users": veeam_users.read,
}
