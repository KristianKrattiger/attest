import base64
import time

import pytest

from scripts.scrub_lab_capture import Scrubber, decode, leaks, main

TENANT = "9f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f"
ARGS = ["--tenant-id", TENANT, "--admin-name", "Pat Example", "--admin-address", "pat@example.net"]


def _scrubber():
    return Scrubber(TENANT, "Pat Example", "pat@example.net")


def _raw(tmp_path, files):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, data in files.items():
        (raw / name).parent.mkdir(parents=True, exist_ok=True)
        (raw / name).write_bytes(data)
    return raw


def _scrub(tmp_path, files, *extra):
    """Run the script on a capture made of these files; the exit code."""
    raw = _raw(tmp_path, files)
    return main([str(raw), str(tmp_path / "out"), *ARGS, *extra], deny_file=tmp_path / "deny.txt")


def _written(tmp_path, name):
    return (tmp_path / "out" / name).read_bytes().decode("utf-8")


def _nothing_but(tmp_path, *names):
    return sorted(p.name for p in tmp_path.iterdir()) == sorted(names)


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


ADDRESS_FORMS = [
    ("Sign-in from 203.45.67.89. Blocked.", "Sign-in from 192.0.2.1. Blocked."),
    ("Sign-in from 203.45.67.89.", "Sign-in from 192.0.2.1."),
    ('{"range": "203.45.67.0/24"}', '{"range": "192.0.2.1/24"}'),
    ('{"url": "http://203.45.67.89:8080/x"}', '{"url": "http://192.0.2.1:8080/x"}'),
    ("ip=203.45.67.89;", "ip=192.0.2.1;"),
    ('{"range": "2606:4700::/32"}', '{"range": "2001:db8::1/32"}'),
    ('{"url": "https://[2606:4700::1111]:443/x"}', '{"url": "https://[2001:db8::1]:443/x"}'),
    ("ip=2606:4700::1111", "ip=2001:db8::1"),
    ("ip: 2606:4700::1111, 2606:4700::1111", "ip: 2001:db8::1, 2001:db8::1"),
    ("Sign-in from 2606:4700::1111. Blocked.", "Sign-in from 2001:db8::1. Blocked."),
    ("Sign-in from 2606:4700::1111: blocked", "Sign-in from 2001:db8::1: blocked"),
    ("ip:2606:4700::1111", "ip:2001:db8::1"),
    ("via ::ffff:203.45.67.89 only", "via 2001:db8::1 only"),
    ("full 2606:4700:0:0:0:0:0:1111 form", "full 2001:db8::1 form"),
    ("v=spf1 ip6:2606:4700::/32 -all", "v=spf1 ip6:2001:db8::1/32 -all"),
    ("IPv6:2606:4700::1111", "IPv6:2001:db8::1"),
]


@pytest.mark.parametrize("text, expected", ADDRESS_FORMS)
def test_an_address_is_found_in_any_form_by_both_the_scrubber_and_the_guard(text, expected):
    assert any(leak.startswith("public IP address") for leak in leaks(text))
    clean = _scrubber().scrub(text)
    assert clean == expected
    assert leaks(clean) == []


NOT_ADDRESSES = [
    "10.0.22631.4317", "16.0.17928.20114", "v1.2.3.4567", "256.300.1.1", "1.2.3", "09:30:00", "T09:30:00.123Z",
    "2026-10-01T09:30:00Z", "00:1A:2B:3C:4D:5E", "3fa85f64-5717-4562-b3fc-2c963f66afa6", "a bare :: stays",
    "12:30", "see Section 2.4 and 3.1.", "0x2606", "Dead beef: cafe",
    "Cache::get", "std::string", "[System.String]::Format", "my_dead::beef",
]


@pytest.mark.parametrize("text", NOT_ADDRESSES)
def test_a_version_a_time_a_mac_a_guid_or_a_bare_colon_pair_is_not_an_address(text):
    assert leaks(text) == []
    assert _scrubber().scrub(text) == text


GLUED_ADDRESSES = ["addr2606:4700::1111", "ip62606:4700::1111", "ip_2606:4700::1111", "a%202606:4700::1111"]


@pytest.mark.parametrize("text", GLUED_ADDRESSES)
def test_an_address_glued_to_a_letter_an_underscore_or_a_percent_escape_is_flagged_by_the_guard_only(text):
    assert leaks(text) == ["public IP address 2606:4700::1111"]
    assert _scrubber().scrub(text) == text  # not an address the scrubber can tell from a word: the guard refuses


def test_a_capture_holding_an_address_glued_to_a_word_is_refused_and_nothing_is_written(tmp_path, capsys):
    assert _scrub(tmp_path, {"users.json": b'{"note": "addr2606:4700::1111"}'}) == 1
    assert "users.json: public IP address 2606:4700::1111" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw", "deny.txt")


def test_a_string_that_is_a_valid_address_is_replaced_even_when_it_is_not_one():
    assert _scrubber().scrub('"5.0.5.0" "00:1A:2B:FF:FE:3C:4D:5E"') == '"192.0.2.1" "2001:db8::2"'


def test_two_spellings_of_one_ipv6_address_map_to_one_documentation_address():
    text = ('"2606:4700::1111" "2606:4700:0:0:0:0:0:1111" "2606:4700::1112" "2606:4700::ABCD" "2606:4700::abcd" '
            '"2606:4700::1111"')
    assert _scrubber().scrub(text) == ('"2001:db8::1" "2001:db8::1" "2001:db8::2" "2001:db8::3" "2001:db8::3" '
                                       '"2001:db8::1"')


def test_documentation_addresses_run_through_three_ranges_and_never_wrap():
    scrubber = _scrubber()
    addresses = [f"11.0.{i // 250}.{i % 250 + 1}" for i in range(762)]
    mapped = scrubber.scrub(" ".join(addresses)).split()
    assert len(set(mapped)) == 762
    assert (mapped[0], mapped[253], mapped[254]) == ("192.0.2.1", "192.0.2.254", "198.51.100.1")
    assert (mapped[507], mapped[508], mapped[761]) == ("198.51.100.254", "203.0.113.1", "203.0.113.254")
    assert scrubber.scrub("11.0.0.1") == "192.0.2.1"  # one already seen keeps its address
    with pytest.raises(ValueError, match="addresses"):
        scrubber.scrub("11.9.9.9")


def test_a_capture_with_more_addresses_than_the_ranges_hold_is_refused_and_nothing_is_written(tmp_path, capsys):
    text = " ".join(f"11.0.{i // 250}.{i % 250 + 1}" for i in range(763))
    assert _scrub(tmp_path, {"users.json": text.encode("utf-8")}) == 1
    assert "users.json" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw", "deny.txt")


def test_the_owners_name_is_replaced_in_every_form_graph_writes():
    text = ('{"displayName": "Pat Example", "sortName": "EXAMPLE, Pat", "givenName": "Pat", "surname": "example", '
            '"alias": "Pat.Example", "mail": "pat@example.net", "upn": "x@contosolab.onmicrosoft.com", '
            '"patch": "Patch", "other": "Pattern Examples", "folder": "/personal/pat_example_contosolab_x/", '
            '"link": "Pat%20Example"}')
    assert _scrubber().scrub(text) == (
        '{"displayName": "Lab Admin", "sortName": "Admin, Lab", "givenName": "Lab", "surname": "Admin", '
        '"alias": "lab.admin", "mail": "lab.admin@harborlab.example", "upn": "x@harborlab.example", '
        '"patch": "Patch", "other": "Pattern Examples", "folder": "/personal/lab.admin_Admin_harborlab_x/", '
        '"link": "Lab%20Admin"}')


def test_the_local_part_of_the_address_is_replaced_as_a_whole_word_in_any_case():
    scrubber = Scrubber(TENANT, "Pat Example", "pexample@example.net")
    text = '{"nick": "pexample", "mail": "PExample@Example.net", "x": "xpexample", "y": "pexamples"}'
    assert scrubber.scrub(text) == ('{"nick": "lab.admin", "mail": "lab.admin@harborlab.example", '
                                    '"x": "xpexample", "y": "pexamples"}')


def test_a_local_part_that_is_also_the_given_name_is_the_alias_when_written_as_the_address_is():
    assert _scrubber().scrub('{"mailNickname": "pat", "givenName": "Pat"}') == (
        '{"mailNickname": "lab.admin", "givenName": "Lab"}')


def test_a_name_part_shorter_than_three_characters_is_left_alone():
    scrubber = Scrubber(TENANT, "Jo Q Lee", "jlee@example.net")
    assert scrubber.scrub('"Jo Q Lee", "Lee, Jo Q", "Q", "Jo"') == '"Lab Admin", "Admin, Lab", "Q", "Jo"'
    assert "Jo" not in scrubber.denied and "Q" not in scrubber.denied


def test_every_form_of_the_name_is_denied_and_a_denied_value_matches_whole_words_only():
    scrubber = _scrubber()
    assert {"Pat Example", "Pat", "Example", "Example, Pat", "pat.example", "pat", "pat@example.net"} <= set(
        scrubber.denied)
    assert leaks("Patch, Pattern and Examples", ["Pat", "Example"]) == []
    assert leaks('"example, pat" and PAT.', ["Example, Pat", "Pat"]) == [
        "denied value 'Example, Pat'", "denied value 'Pat'"]
    assert leaks('"a%40pat.net"', ["pat"]) == ["denied value 'pat'"]


def test_what_the_scrubber_writes_is_never_reported_as_a_denied_value():
    clean = _scrubber().scrub('{"mail": "pat@example.net", "name": "Pat Example", "x": "Example, Pat"}')
    assert clean == '{"mail": "lab.admin@harborlab.example", "name": "Lab Admin", "x": "Admin, Lab"}'
    assert leaks(clean, _scrubber().denied) == []
    admin = Scrubber(TENANT, "Pat Example", "admin@example.net")
    assert leaks(admin.scrub('{"mail": "admin@example.net", "who": "Pat Example"}'), admin.denied) == []


def test_scrubbed_output_is_not_flagged_for_a_hyphenated_label_and_an_admin_address():
    scrubber = Scrubber(TENANT, "Alex Stone", "admin@example.net")
    text = ('{"mail": "admin@example.net", "s": "https://my-lab.sharepoint.com", "u": "x@my-lab.onmicrosoft.com", '
            '"n": "Alex Stone", "r": "Stone, Alex"}')
    clean = scrubber.scrub(text)
    assert clean == ('{"mail": "lab.admin@harborlab.example", "s": "https://harborlab.sharepoint.com", '
                     '"u": "x@harborlab.example", "n": "Lab Admin", "r": "Admin, Lab"}')
    assert {"my-lab", "admin@example.net", "admin", "Stone"} <= set(scrubber.denied)
    assert leaks(clean, scrubber.denied) == []


@pytest.mark.parametrize("value, text", [
    ("admin@example.net", '{"mail": "admin@example.net"}'),
    ("my-lab", '{"s": "https://my-lab.sharepoint.com/x"}'),
    ("lab-pat", '{"n": "lab-pat"}'),
    ("LAB-PC-01", '{"device": "LAB-PC-01"}'),
    ("harbor-lab.com", '{"d": "harbor-lab.com"}'),
    ("admin.contoso.com", '{"d": "admin.contoso.com"}'),
    ("Example", '{"d": "lab.example"}'),
    ("Pat", '{"mail": "pat@harborlab.example"}'),
])
def test_a_denied_value_that_contains_one_of_the_scrubbers_words_is_still_flagged(value, text):
    assert leaks(text, [value]) == [f"denied value {value!r}"]


def test_a_denied_value_is_flagged_beside_the_scrubbers_own_words_too():
    scrubber = Scrubber(TENANT, "Alex Stone", "admin@example.net")
    scrubber.learn('"x@my-lab.onmicrosoft.com"')
    text = '{"mail": "admin@example.net", "s": "https://my-lab.sharepoint.com", "own": "lab.admin@harborlab.example"}'
    assert leaks(text, scrubber.denied) == ["denied value 'admin@example.net'", "denied value 'my-lab'"]


def test_leaks_name_onmicrosoft_public_addresses_and_denied_values():
    assert leaks('{"a": "x.onmicrosoft.com", "b": "8.8.8.8", "c": "10.1.2.3", "d": "192.0.2.7", "e": "Pat"}',
                 ["pat"]) == ["an onmicrosoft.com domain", "public IP address 8.8.8.8", "denied value 'pat'"]


@pytest.mark.parametrize("text", ["a@contosolab.onmicrosoft.com", "a%40contosolab.onmicrosoft.com",
                                  "contosolab.mail.onmicrosoft.com", "x@fabrikam.onmicrosoft.us"])
def test_leaks_name_every_onmicrosoft_domain_form(text):
    assert leaks(text)[0].startswith("an onmicrosoft.")


GUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
PAGED = '{"@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$top=5&$skiptoken=%s", "value": []}'


def _token(encode=base64.b64encode, padded=True):
    """What Graph puts after $skiptoken=: a binary header, then the page's last user principal name and ID."""
    raw = b"\xfb\xff\xfe" + f"DSptABC:Pat.Example@contosolab.onmicrosoft.com)User_{GUID}".encode("ascii")
    token = encode(raw).decode("ascii")
    return token if padded else token.rstrip("=")


SKIPTOKENS = [
    ('"u?$top=5&$skiptoken=abc123"', '"u?$top=5&$skiptoken=REDACTED"'),
    ("u?$skiptoken=abc123&$top=5", "u?$skiptoken=REDACTED&$top=5"),
    ("u?$SkipToken=abc123==", "u?$SkipToken=REDACTED"),
    ("u?%24skiptoken=abc%2B123", "u?%24skiptoken=REDACTED"),
    ('"u?$skiptoken=abc-_123\\" tail"', '"u?$skiptoken=REDACTED\\" tail"'),
    ("u?$skiptoken=abc 123", "u?$skiptoken=REDACTED 123"),
    ("u?$skiptoken=", "u?$skiptoken="),
    ("u?skiptoken=abc123 and $skip=5", "u?skiptoken=abc123 and $skip=5"),
]


@pytest.mark.parametrize("text, expected", SKIPTOKENS)
def test_the_value_after_a_skiptoken_is_replaced_with_a_placeholder(text, expected):
    assert _scrubber().scrub(text) == expected


def test_a_paged_users_export_is_scrubbed_of_the_address_its_skiptoken_holds_and_the_guard_saw_it_before():
    text = PAGED % _token()
    assert leaks(text) == ["an onmicrosoft.com domain (inside base64)"]
    assert leaks(text, ["Pat"]) == ["an onmicrosoft.com domain (inside base64)", "denied value 'Pat' (inside base64)"]
    clean = _scrubber().scrub(text)
    assert clean == PAGED % "REDACTED"
    assert leaks(clean, _scrubber().denied) == []


def test_a_capture_with_a_paged_users_export_keeps_its_next_link_and_loses_the_token(tmp_path):
    assert _scrub(tmp_path, {"users.json": (PAGED % _token()).encode("utf-8")}) == 0
    assert _written(tmp_path, "users.json") == PAGED % "REDACTED"


@pytest.mark.parametrize("encode", [base64.b64encode, base64.urlsafe_b64encode])
@pytest.mark.parametrize("padded", [True, False])
@pytest.mark.parametrize("form", ["x?$skiptoken=%s", '{"state": "%s"}', "x?$skiptoken=%s&$top=5"])
def test_the_guard_reads_base64_in_either_alphabet_with_or_without_padding(encode, padded, form):
    assert leaks(form % _token(encode, padded)) == ["an onmicrosoft.com domain (inside base64)"]


def test_the_two_base64_alphabets_differ_in_the_token_the_tests_use():
    assert {"+", "/"} <= set(_token(base64.b64encode)) and {"-", "_"} <= set(_token(base64.urlsafe_b64encode))


def test_the_guard_reads_a_token_whose_plus_and_slash_are_percent_encoded():
    token = _token().replace("+", "%2B").replace("/", "%2F")
    assert "%2B" in token and leaks(f"x?$skiptoken={token}") == ["an onmicrosoft.com domain (inside base64)"]


def test_the_guard_finds_a_public_address_inside_base64_too():
    token = base64.b64encode(b"Sign-in from 203.45.67.89 was blocked by policy").decode("ascii")
    assert leaks(f'{{"note": "{token}"}}') == ["public IP address 203.45.67.89 (inside base64)"]


def test_a_base64_run_that_decodes_to_binary_noise_is_not_flagged():
    text = b"a@contosolab.onmicrosoft.com"
    noise = base64.b64encode(bytes(range(0x80, 0xC0)) + text).decode("ascii")
    assert leaks(f'{{"blob": "{noise}"}}', ["contosolab"]) == []
    mostly_text = base64.b64encode(bytes(range(0x80, 0x84)) + text).decode("ascii")
    assert leaks(f'{{"blob": "{mostly_text}"}}') == ["an onmicrosoft.com domain (inside base64)"]


@pytest.mark.parametrize("text", [
    '{"id": "0123456789abcdef0123456789abcdef01234567"}', '{"hash": "' + "ABCDEF" * 11 + '"}',
    '{"name": "mfa-exclusions-group-for-all-users"}', "-" * 40, "=" * 40, "/personal/lab_admin_harborlab_x/Documents",
])
def test_a_long_identifier_or_a_line_of_dashes_is_not_flagged(text):
    assert leaks(text, ["Pat"]) == []


def test_the_guard_stays_fast_on_a_file_full_of_the_scrubbers_own_words():
    text = "lab " * 12000
    started = time.perf_counter()
    assert leaks(text, ["lab"]) == []
    assert time.perf_counter() - started < 1.0


def test_the_tenant_label_is_learned_from_every_file_and_replaced_wherever_it_appears(tmp_path):
    first = ('{"site": "https://contosolab.sharepoint.com/sites/x", '
             '"admin": "https://contosolab-admin.sharepoint.com", '
             '"mx": "contosolab.mail.protection.outlook.com", "enc": "a%40contosolab.onmicrosoft.com", '
             '"my": "contosolab-my.sharepoint.com", "gov": "https://fabrikam.sharepoint.com", '
             '"word": "contosolabs.sharepoint.com"}')
    second = '{"upn": "u@contosolab.onmicrosoft.com", "us": "x@fabrikam.onmicrosoft.us"}'
    assert _scrub(tmp_path, {"a.json": first.encode("utf-8"), "b.json": second.encode("utf-8")}) == 0
    assert _written(tmp_path, "a.json") == (
        '{"site": "https://harborlab.sharepoint.com/sites/x", "admin": "https://harborlab-admin.sharepoint.com", '
        '"mx": "harborlab.mail.protection.outlook.com", "enc": "a%40harborlab.example", '
        '"my": "harborlab-my.sharepoint.com", "gov": "https://harborlab.sharepoint.com", '
        '"word": "contosolabs.sharepoint.com"}')
    assert _written(tmp_path, "b.json") == '{"upn": "u@harborlab.example", "us": "x@harborlab.example"}'
    deny = (tmp_path / "deny.txt").read_text(encoding="utf-8").splitlines()
    assert "contosolab" in deny and "fabrikam" in deny


def test_a_label_seen_only_in_a_later_file_is_still_replaced_in_an_earlier_one(tmp_path):
    files = {"a.json": b'{"site": "https://contosolab.sharepoint.com"}',
             "z.json": b'{"u": "a@contosolab.onmicrosoft.com"}'}
    assert _scrub(tmp_path, files) == 0
    assert _written(tmp_path, "a.json") == '{"site": "https://harborlab.sharepoint.com"}'


def test_also_values_are_replaced_with_redacted_and_denied(tmp_path):
    text = '{"phone": "+1 555 0100", "device": "Fabrikam Surface 7", "note": "FABRIKAM"}'
    assert _scrub(tmp_path, {"users.json": text.encode("utf-8")}, "--also", "+1 555 0100", "--also", "fabrikam") == 0
    assert _written(tmp_path, "users.json") == (
        '{"phone": "redacted", "device": "redacted Surface 7", "note": "redacted"}')
    deny = (tmp_path / "deny.txt").read_text(encoding="utf-8").splitlines()
    assert "+1 555 0100" in deny and "fabrikam" in deny


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
    # Changed on purpose: the owner's name parts, "Surname, Given", dotted form and local part, and the tenant's
    # label learned from the capture are denied as well as the full name, address and tenant ID.
    assert deny.read_text(encoding="utf-8").splitlines() == sorted([
        TENANT, "Pat Example", "pat@example.net", "pat", "Pat", "Example", "Example, Pat", "pat.example", "contosolab"])


def test_utf8_with_a_byte_order_mark_and_utf16_big_endian_keep_the_form_of_their_bytes(tmp_path):
    bom8 = b"\xef\xbb\xbf" + '{"upn": "a@contosolab.onmicrosoft.com", "ip": "203.45.67.89"}\r\n'.encode("utf-8")
    be16 = b"\xfe\xff" + '{\n  "name": "Pat Example"\n}\n'.encode("utf-16-be")
    assert _scrub(tmp_path, {"bom8.json": bom8, "be16.json": be16}) == 0
    assert (tmp_path / "out" / "bom8.json").read_bytes() == (
        b"\xef\xbb\xbf" + '{"upn": "a@harborlab.example", "ip": "192.0.2.1"}\r\n'.encode("utf-8"))
    assert (tmp_path / "out" / "be16.json").read_bytes() == (
        b"\xfe\xff" + '{\n  "name": "Lab Admin"\n}\n'.encode("utf-16-be"))
    assert decode((tmp_path / "out" / "be16.json").read_bytes())[1:] == ("utf-16-be", b"\xfe\xff")


def test_a_capture_still_holding_a_denied_value_is_refused_and_removed(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "users.json").write_text('{"note": "an old tenant: oldlab"}', encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("oldlab\n", encoding="utf-8")
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=deny) == 1
    assert not (tmp_path / "out").exists()
    assert "users.json: denied value 'oldlab'" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw", "deny.txt")


def test_a_file_that_is_not_an_export_is_refused(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "notes.txt").write_text("hello", encoding="utf-8")
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt") == 1
    assert "notes.txt: not an export or a manifest" in capsys.readouterr().err


def test_a_raw_folder_that_does_not_exist_is_refused_with_nothing_written(tmp_path, capsys):
    assert main([str(tmp_path / "nope"), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt") == 1
    err = capsys.readouterr().err
    assert "nope" in err and "not an existing folder" in err
    assert _nothing_but(tmp_path)


def test_a_raw_path_that_is_a_file_is_refused(tmp_path, capsys):
    (tmp_path / "raw").write_text("{}", encoding="utf-8")
    assert main([str(tmp_path / "raw"), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt") == 1
    assert "not an existing folder" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw")


@pytest.mark.parametrize("subfolders", [[], ["exports"]])
def test_a_raw_folder_with_no_files_is_refused_with_nothing_written(tmp_path, capsys, subfolders):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in subfolders:
        (raw / name).mkdir()
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt") == 1
    assert "holds no files" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw")


@pytest.mark.parametrize("name, data", [
    ("users.json", b'{"a": "\x80\x81"}'),
    ("users.json", '{"a": 1}'.encode("utf-16-le")),  # UTF-16 with no byte-order mark reads as NULs, not text
    ("users.json", b"\xff\xfe{"),
    ("photo.json", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"),
])
def test_a_file_that_is_not_text_is_refused_by_name_with_nothing_written(tmp_path, capsys, name, data):
    assert _scrub(tmp_path, {"exports/ok.json": b'{"a": 1}', f"exports/{name}": data}) == 1
    assert f"exports/{name}: not UTF-8 or UTF-16 text" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw")


def test_a_failure_part_way_leaves_no_partial_copy_and_no_staging_folder(tmp_path, monkeypatch):
    real = Scrubber.scrub
    calls = []

    def fail_on_the_second_file(self, text):
        calls.append(text)
        if len(calls) == 2:
            raise RuntimeError("disk full")
        return real(self, text)

    monkeypatch.setattr(Scrubber, "scrub", fail_on_the_second_file)
    raw = _raw(tmp_path, {"a.json": b'{"a": 1}', "b.json": b'{"b": 2}'})
    with pytest.raises(RuntimeError, match="disk full"):
        main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt")
    assert len(calls) == 2
    assert _nothing_but(tmp_path, "raw", "deny.txt")


def test_a_file_whose_name_could_name_the_tenant_is_refused(tmp_path, capsys):
    assert _scrub(tmp_path, {"pat.example.json": b'{"a": 1}'}) == 1
    assert "pat.example.json" in capsys.readouterr().err
    assert _nothing_but(tmp_path, "raw", "deny.txt")


def test_an_output_that_exists_is_left_alone_and_exits_two(tmp_path, capsys):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "keep.json").write_text("{}", encoding="utf-8")
    assert _scrub(tmp_path, {"users.json": b"{}"}) == 2
    assert "already exists" in capsys.readouterr().err
    assert (tmp_path / "out" / "keep.json").read_text(encoding="utf-8") == "{}"
    assert not (tmp_path / "deny.txt").exists()
