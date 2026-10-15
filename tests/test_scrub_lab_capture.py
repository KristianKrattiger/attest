from scripts.scrub_lab_capture import Scrubber, decode, leaks, main

TENANT = "9f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f"
ARGS = ["--tenant-id", TENANT, "--admin-name", "Pat Example", "--admin-address", "pat@example.net"]


def _scrubber():
    return Scrubber(TENANT, "Pat Example", "pat@example.net")


def test_what_names_the_tenant_or_its_owner_is_replaced():
    text = ('{"userPrincipalName": "admin@contosolab.onmicrosoft.com", "mail": "pat@example.net", '
            '"displayName": "Pat Example", "tenantId": "9F1C2D3E-4B5A-4C6D-8E7F-0A1B2C3D4E5F", '
            '"proxy": "contosolab.mail.onmicrosoft.com"}')
    assert _scrubber().scrub(text) == (
        '{"userPrincipalName": "admin@harborlab.example", "mail": "lab.admin@harborlab.example", '
        '"displayName": "Lab Admin", "tenantId": "11111111-1111-4111-8111-111111111111", '
        '"proxy": "harborlab.example"}')


def test_each_address_becomes_one_documentation_address_and_nothing_else_moves():
    scrubber = _scrubber()
    text = ('{"lastIpAddress": "10.0.0.4", "lastExternalIpAddress": "203.45.67.89", "again": "203.45.67.89", '
            '"v6": "2606:4700::1111", "osVersion": "10.0.22631.4317", "lastSeen": "2026-10-01T09:30:00Z", '
            '"time": "09:30:00"}')
    assert scrubber.scrub(text) == (
        '{"lastIpAddress": "192.0.2.1", "lastExternalIpAddress": "192.0.2.2", "again": "192.0.2.2", '
        '"v6": "2001:db8::3", "osVersion": "10.0.22631.4317", "lastSeen": "2026-10-01T09:30:00Z", '
        '"time": "09:30:00"}')


def test_leaks_name_onmicrosoft_public_addresses_and_denied_values():
    assert leaks('{"a": "x.onmicrosoft.com", "b": "8.8.8.8", "c": "10.1.2.3", "d": "192.0.2.7", "e": "Pat"}',
                 ["pat"]) == ["an onmicrosoft.com domain", "public IP address 8.8.8.8", "denied value 'pat'"]


def test_a_capture_keeps_its_encoding_byte_order_mark_and_line_endings(tmp_path):
    raw = tmp_path / "raw"
    (raw / "exports").mkdir(parents=True)
    utf16 = b"\xff\xfe" + '{\r\n  "upn": "a@contosolab.onmicrosoft.com"\r\n}\r\n'.encode("utf-16-le")
    (raw / "exports" / "users.json").write_bytes(utf16)
    (raw / "exports" / "manifest.yaml").write_bytes(b"exports:\n  - {file: users.json}\n")
    deny = tmp_path / "deny.txt"
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=deny) == 0
    written = (tmp_path / "out" / "exports" / "users.json").read_bytes()
    assert written == b"\xff\xfe" + '{\r\n  "upn": "a@harborlab.example"\r\n}\r\n'.encode("utf-16-le")
    assert decode(written)[1:] == ("utf-16-le", b"\xff\xfe")
    assert (tmp_path / "out" / "exports" / "manifest.yaml").read_bytes() == b"exports:\n  - {file: users.json}\n"
    assert deny.read_text(encoding="utf-8").splitlines() == sorted([TENANT, "Pat Example", "pat@example.net"])


def test_a_capture_still_holding_a_denied_value_is_refused_and_removed(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "users.json").write_text('{"note": "an old tenant: oldlab"}', encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("oldlab\n", encoding="utf-8")
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=deny) == 1
    assert not (tmp_path / "out").exists()
    assert "users.json: denied value 'oldlab'" in capsys.readouterr().err


def test_a_file_that_is_not_an_export_is_refused(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "notes.txt").write_text("hello", encoding="utf-8")
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt") == 1
    assert "notes.txt: not an export or a manifest" in capsys.readouterr().err
