"""Format mess: how PowerShell and the APIs write the same data, and the refusals the docs promise.

Inert operators run after every other operator in a combination (compose.apply), so they reshape whatever the others
wrote.
"""
from __future__ import annotations

import json
from datetime import datetime

from messy.firm import Firm, records
from messy.operators import Operator, take


def _write_all(firm: Firm, encode) -> bool:
    if not take(firm, "format:encoding"):
        return False
    for name in firm.data:
        firm.writers[name] = encode
    return True


def _utf16(data) -> bytes:
    """Windows PowerShell 5.1's Out-File default: UTF-16 LE with a byte-order mark, CRLF."""
    return ("﻿" + json.dumps(data, indent=2).replace("\n", "\r\n") + "\r\n").encode("utf-16-le")


def _utf8_bom_crlf(data) -> bytes:
    """Windows PowerShell 5.1's Out-File -Encoding utf8: UTF-8 with a byte-order mark, CRLF."""
    return ("﻿" + json.dumps(data, indent=4).replace("\n", "\r\n") + "\r\n").encode("utf-8")


def _reordered(firm: Firm) -> bool:
    if not take(firm, "format:order"):
        return False
    for data in firm.data.values():
        rows = records(data)
        rows.reverse()
        rows[:] = [dict(reversed(list(r.items()))) for r in rows]
    return True


UNKNOWN_FIELDS = {
    "entra_users": {"createdDateTime": "2025-01-06T16:00:00Z", "mail": None, "jobTitle": None},
    "entra_registration": {"isSsprRegistered": False, "lastUpdatedDateTime": "2026-10-01T03:00:00Z"},
    # Top-level only: an unknown key inside a policy's conditions narrows it, by design (entra_ca_policies.py).
    "entra_ca_policies": {"templateId": None, "createdDateTime": "2025-01-06T16:00:00Z", "modifiedDateTime": None,
                          "sessionControls": None},
    "intune_devices": {"enrolledDateTime": "2025-01-07T10:00:00Z", "complianceState": "compliant"},
    "defender_machines": {"firstSeen": "2025-01-07T10:05:00.1234567Z", "osProcessor": "x64",
                          "lastIpAddress": "192.0.2.10", "riskScore": "None", "machineTags": []},
    "veeam_users": {"IsArchiveBackedUp": False, "ArchiveBackedUpTime": None},
}


def _unknown_fields(firm: Firm) -> bool:
    if not take(firm, "format:fields"):
        return False
    for reader, fields in UNKNOWN_FIELDS.items():
        for r in firm.rows(reader):
            r.update({k: v for k, v in fields.items() if k not in r})
    return True


def _seven_digit_fractions(firm: Firm) -> bool:
    if not take(firm, "format:defender-times"):
        return False
    for m in firm.rows("defender_machines"):
        if isinstance(m.get("lastSeen"), str) and m["lastSeen"].endswith("Z") and "." not in m["lastSeen"]:
            m["lastSeen"] = m["lastSeen"][:-1] + ".1234567Z"
    return True


def _ps51_dates(firm: Firm) -> bool:
    if not take(firm, "format:veeam-dates"):
        return False
    for r in firm.rows("veeam_users"):
        when = r.get("MailboxBackedUpTime")
        # A time with no offset is left as it is: refusing it is another operator's promise.
        if isinstance(when, str) and datetime.fromisoformat(when).utcoffset() is not None:
            r["MailboxBackedUpTime"] = {"value": f"/Date({int(datetime.fromisoformat(when).timestamp() * 1000)})/",
                                        "DisplayHint": 2}
    return True


def _paged_users(firm: Firm) -> bool:
    page = firm.data[firm.file("entra_users")]
    if not isinstance(page, dict) or not take(firm, "users-page"):
        return False
    page["@odata.nextLink"] = "https://graph.microsoft.com/v1.0/users?$top=5&$skiptoken=X"
    return True


def _veeam_no_offset(firm: Firm) -> bool:
    if not take(firm, "veeam-times"):
        return False
    for r in firm.rows("veeam_users"):
        if isinstance(r.get("MailboxBackedUpTime"), str):
            r["MailboxBackedUpTime"] = r["MailboxBackedUpTime"].replace("Z", "").split("+")[0]
            return True
    return False


OPERATORS = (
    Operator("UTF-16 with CRLF", "inert", lambda firm: _write_all(firm, _utf16)),
    Operator("UTF-8 with a BOM and CRLF", "inert", lambda firm: _write_all(firm, _utf8_bom_crlf)),
    Operator("rows and fields reordered", "inert", _reordered),
    Operator("unknown fields added", "inert", _unknown_fields),
    Operator("Defender times with 7 fractional digits", "inert", _seven_digit_fractions),
    Operator("Veeam times as PowerShell 5.1 DateTimes", "inert", _ps51_dates),
    Operator("users export is one page of several", "stops", _paged_users,
             stop="the export is one page of several", twin="real-messy-paged"),
    Operator("Veeam time with no UTC offset", "stops", _veeam_no_offset, stop="has no UTC offset"),
)
