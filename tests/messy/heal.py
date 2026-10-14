"""The dev firm healed of every planted gap: the seed the messy-firm suite uses until a real capture replaces it.

Each edit takes a firm's exports folder and changes one file in place. tests/test_dev_firm.py uses the same edits
for its single mutations.
"""
import json

DOMAIN = "harborpine.example"


def edit(file, change):
    """An edit of one export: change(data) alters the parsed JSON in place."""
    def apply(exports):
        path = exports / file
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return apply


def row(rows, key, value):
    (found,) = [r for r in rows if r[key] == value]
    return found


def machine(name, health="Active", aad=None, last_seen="2026-10-01T09:30:00Z"):
    return {"id": name.split(".")[0].ljust(40, "0")[:40], "computerDnsName": f"{name}.{DOMAIN}", "aadDeviceId": aad,
            "osPlatform": "Windows11", "onboardingStatus": "Onboarded", "healthStatus": health, "lastSeen": last_seen}


HEAL = (
    edit("ca-policies.json", lambda ca: ca["value"][0]["conditions"]["users"].update(excludeUsers=[])),  # Dana
    edit("registration.json", lambda reg: row(reg["value"], "id", "a0000000-0000-4000-8000-000000000012").update(
        isMfaRegistered=True)),  # Ivan registered
    edit("defender-machines.json", lambda mde: mde["value"].append(
        machine("hp-lt-12", aad="d0000000-0000-4000-8000-000000000012"))),  # Ivan's laptop onboarded
    edit("veeam-users.json", lambda rows: row(rows, "Email", f"carmen.diaz@{DOMAIN}").update(
        IsMailboxBackedUp=True, MailboxBackedUpTime="2026-10-01T02:10:00Z")),  # Carmen's mailbox backed up
)
