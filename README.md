# attest

Checks a firm's insurance application and written information security plan
(WISP) against what its Microsoft 365 and Veeam exports show. Each attestation
comes out **backed**, **gap** or **unchecked**, with the export rows cited.

    py -3.12 -m venv venv
    venv/Scripts/python.exe -m pip install -r requirements.txt
    venv/Scripts/python.exe -m pytest
    venv/Scripts/python.exe -m attest check firm/dev

Design: `docs/superpowers/specs/2026-10-04-attestation-core-design.md`.
How the firm produces each export: `docs/exports.md`.
