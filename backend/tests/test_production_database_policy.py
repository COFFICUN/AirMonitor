"""Production database-target policy regressions."""

import socket
from collections.abc import Callable
from contextlib import ExitStack
from ipaddress import IPv4Address, IPv6Address
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import URL, make_url

from app.core.config import Settings


DEFAULT_TARGET_ERROR = (
    "database_url must be explicitly configured in production"
)
AMBIGUOUS_TARGET_ERROR = "database_url has ambiguous target options"
EXPLICIT_TARGET_ERROR = (
    "database_url must explicitly identify a single production target"
)
TARGET_IDENTITY_QUERY_KEYS = (
    "host",
    "port",
    "database",
    "dbname",
    "user",
    "username",
    "password",
    "passfile",
    "service",
    "servicefile",
)
AMBIENT_PG_VARIABLES = (
    "PGHOST",
    "PGPORT",
    "PGUSER",
    "PGPASSWORD",
    "PGDATABASE",
    "PGPASSFILE",
    "PGSERVICE",
    "PGSERVICEFILE",
)


def default_database_url() -> str:
    value = Settings.model_fields["database_url"].default
    assert isinstance(value, str)
    return value


def parsed_default_database_url() -> URL:
    return make_url(default_database_url())


def explicit_production_target() -> URL:
    default = parsed_default_database_url()
    assert default.username is not None
    assert default.password is not None
    assert default.port is not None
    assert default.database is not None
    return URL.create(
        drivername=default.drivername,
        username=f"{default.username}_production",
        password=f"{default.password}_production",
        host="phase-c4a-production.invalid",
        port=default.port + 1,
        database=f"{default.database}_production",
    )


def render_candidate(candidate: URL) -> str:
    return candidate.render_as_string(hide_password=False)


def without_host(candidate: URL) -> URL:
    return URL.create(
        drivername=candidate.drivername,
        username=candidate.username,
        password=candidate.password,
        port=candidate.port,
        database=candidate.database,
    )


def without_port(candidate: URL) -> URL:
    return URL.create(
        drivername=candidate.drivername,
        username=candidate.username,
        password=candidate.password,
        host=candidate.host,
        database=candidate.database,
    )


def without_username(candidate: URL) -> URL:
    return URL.create(
        drivername=candidate.drivername,
        password=candidate.password,
        host=candidate.host,
        port=candidate.port,
        database=candidate.database,
    )


def without_password(candidate: URL) -> URL:
    return URL.create(
        drivername=candidate.drivername,
        username=candidate.username,
        host=candidate.host,
        port=candidate.port,
        database=candidate.database,
    )


def without_database(candidate: URL) -> URL:
    return URL.create(
        drivername=candidate.drivername,
        username=candidate.username,
        password=candidate.password,
        host=candidate.host,
        port=candidate.port,
    )


def with_empty_host(candidate: URL) -> URL:
    return candidate.set(host="")


def with_empty_username(candidate: URL) -> URL:
    return candidate.set(username="")


def with_empty_password(candidate: URL) -> URL:
    return candidate.set(password="")


def with_empty_database(candidate: URL) -> URL:
    return candidate.set(database="")


def with_duplicate_loopback_hosts(candidate: URL) -> URL:
    return candidate.set(host="localhost,localhost")


def with_mixed_loopback_hosts(candidate: URL) -> URL:
    return candidate.set(
        host=f"localhost,{IPv4Address((127 << 24) | 1)}"
    )


def with_distinct_hosts(candidate: URL) -> URL:
    return candidate.set(
        host="phase-c4a-primary.invalid,phase-c4a-secondary.invalid"
    )


def with_percent_encoded_host_separator(candidate: URL) -> URL:
    return candidate.set(
        host="phase-c4a-primary.invalid%2Cphase-c4a-secondary.invalid"
    )


def assert_explicit_target_error(error: ValidationError) -> None:
    errors = error.errors(include_url=False, include_input=False)
    assert len(errors) == 1
    assert errors[0]["msg"] == f"Value error, {EXPLICIT_TARGET_ERROR}"


def render_default_target(
    *,
    drivername: str | None = None,
    host: str | None = None,
    port: int | None = None,
    include_port: bool = True,
    database: str | None = None,
    query: dict[str, str] | None = None,
) -> str:
    default = parsed_default_database_url()
    assert default.host is not None
    assert default.port is not None
    rendered = URL.create(
        drivername=drivername or default.drivername,
        username=default.username,
        password=default.password,
        host=host or default.host,
        port=(port if port is not None else default.port)
        if include_port
        else None,
        database=database or default.database,
        query=query or {},
    )
    return rendered.render_as_string(hide_password=False)


def omit_default_port(_: URL) -> str:
    return render_default_target(include_port=False)


def vary_host_case(default: URL) -> str:
    assert default.host is not None
    return render_default_target(host=default.host.swapcase())


def add_trailing_dot_to_local_host(default: URL) -> str:
    assert default.host is not None
    return render_default_target(host=f"{default.host}.")


def use_ipv4_loopback(_: URL) -> str:
    return render_default_target(host=str(IPv4Address((127 << 24) | 1)))


def use_ipv6_loopback(_: URL) -> str:
    return render_default_target(host=str(IPv6Address(1)))


def percent_encode(value: str) -> str:
    assert value
    return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))


def percent_encode_identity(default: URL) -> str:
    assert default.username is not None
    assert default.password is not None
    assert default.host is not None
    assert default.port is not None
    assert default.database is not None
    return (
        f"{default.drivername}://"
        f"{percent_encode(default.username)}:"
        f"{percent_encode(default.password)}@"
        f"{percent_encode(default.host)}:"
        f"{default.port}/"
        f"{percent_encode(default.database)}"
    )


def add_harmless_query_option(_: URL) -> str:
    return render_default_target(
        query={"application_name": "phase-c4a-policy-test"}
    )


def replace_default_target_host(
    host: str,
) -> Callable[[URL], str]:
    def variant(_: URL) -> str:
        return render_default_target(host=host)

    return variant


def add_leading_ascii_whitespace_to_host(default: URL) -> str:
    assert default.host is not None
    return render_default_target(host=f" {default.host}")


def add_trailing_ascii_whitespace_to_host(default: URL) -> str:
    assert default.host is not None
    return render_default_target(host=f"{default.host} ")


def transform_default_target_host(
    transform: Callable[[str], str],
) -> Callable[[URL], str]:
    def variant(default: URL) -> str:
        assert default.host is not None
        return render_default_target(host=transform(default.host))

    return variant


def to_fullwidth_ascii(value: str) -> str:
    return "".join(
        chr(ord(character) + 0xFEE0)
        if character.isascii() and character.isalnum()
        else character
        for character in value
    )


def use_compatibility_letter(value: str) -> str:
    assert "s" in value
    return value.replace("s", chr(0x017F), 1)


def superscript_numeric(value: str) -> str:
    code_points = {
        "1": 0x00B9,
        "2": 0x00B2,
        "7": 0x2077,
    }
    return "".join(
        chr(code_points[character])
        if character in code_points
        else character
        for character in value
    )


def subscript_numeric(value: str) -> str:
    return "".join(
        chr(0x2080 + int(character))
        if character.isascii() and character.isdecimal()
        else character
        for character in value
    )


def mathematical_numeric(value: str) -> str:
    return "".join(
        chr(0x1D7D8 + int(character))
        if character.isascii() and character.isdecimal()
        else character
        for character in value
    )


def insert_into_default_host(
    character: str,
) -> Callable[[URL], str]:
    def variant(default: URL) -> str:
        assert default.host is not None
        midpoint = len(default.host) // 2
        host = (
            f"{default.host[:midpoint]}"
            f"{character}"
            f"{default.host[midpoint:]}"
        )
        return render_default_target(host=host)

    return variant


def use_canonical_distinct_ipv4(candidate: URL) -> URL:
    return candidate.set(
        host=str(IPv4Address((192 << 24) | (2 << 8) | 1))
    )


def use_canonical_distinct_ipv6(candidate: URL) -> URL:
    return candidate.set(
        host=str(IPv6Address((0x2001 << 112) | (0xDB8 << 96) | 1))
    )


def use_normal_dns_hostname(candidate: URL) -> URL:
    return candidate.set(host="phase-c4a-dns.invalid")


AMBIGUOUS_HOST_VARIANTS = (
    pytest.param(
        replace_default_target_host("127.1"),
        id="abbreviated-two-component",
    ),
    pytest.param(
        replace_default_target_host("127.0.1"),
        id="abbreviated-three-component",
    ),
    pytest.param(
        replace_default_target_host("127.000.000.001"),
        id="zero-padded-components",
    ),
    pytest.param(
        replace_default_target_host(str((127 << 24) | 1)),
        id="single-decimal-integer",
    ),
    pytest.param(
        replace_default_target_host("0x7f000001"),
        id="single-hexadecimal-integer",
    ),
    pytest.param(
        replace_default_target_host("0177.0.0.1"),
        id="leading-zero-component",
    ),
    pytest.param(
        replace_default_target_host("127.0x0.1"),
        id="mixed-base-components",
    ),
    pytest.param(
        replace_default_target_host(f"127{percent_encode('.')}1"),
        id="percent-encoded-separator",
    ),
    pytest.param(
        add_leading_ascii_whitespace_to_host,
        id="leading-ascii-whitespace",
    ),
    pytest.param(
        add_trailing_ascii_whitespace_to_host,
        id="trailing-ascii-whitespace",
    ),
)


LOOPBACK_SHORTHAND = f"{127}.{1}"
LOOPBACK_CANONICAL = str(IPv4Address((127 << 24) | 1))
NON_ASCII_HOST_VARIANTS = (
    pytest.param(
        transform_default_target_host(to_fullwidth_ascii),
        id="fullwidth-local-host",
    ),
    pytest.param(
        transform_default_target_host(use_compatibility_letter),
        id="compatibility-letter-local-host",
    ),
    pytest.param(
        replace_default_target_host(
            to_fullwidth_ascii(LOOPBACK_SHORTHAND)
        ),
        id="fullwidth-loopback-shorthand",
    ),
    pytest.param(
        replace_default_target_host(
            to_fullwidth_ascii(LOOPBACK_CANONICAL)
        ),
        id="fullwidth-loopback-canonical",
    ),
    pytest.param(
        replace_default_target_host(
            superscript_numeric(LOOPBACK_SHORTHAND)
        ),
        id="superscript-loopback",
    ),
    pytest.param(
        replace_default_target_host(
            subscript_numeric(LOOPBACK_SHORTHAND)
        ),
        id="subscript-loopback",
    ),
    pytest.param(
        replace_default_target_host(
            mathematical_numeric(LOOPBACK_SHORTHAND)
        ),
        id="mathematical-loopback",
    ),
    pytest.param(
        replace_default_target_host(
            LOOPBACK_SHORTHAND.replace(".", chr(0x3002))
        ),
        id="ideographic-full-stop",
    ),
    pytest.param(
        replace_default_target_host(
            LOOPBACK_SHORTHAND.replace(".", chr(0xFF0E))
        ),
        id="fullwidth-full-stop",
    ),
    pytest.param(
        replace_default_target_host(
            LOOPBACK_SHORTHAND.replace(".", chr(0xFF61))
        ),
        id="halfwidth-ideographic-full-stop",
    ),
    pytest.param(
        transform_default_target_host(
            lambda host: percent_encode(use_compatibility_letter(host))
        ),
        id="percent-encoded-compatibility-host",
    ),
)
INTERNAL_ASCII_WHITESPACE_VARIANTS = (
    pytest.param(
        insert_into_default_host(" "),
        id="internal-space",
    ),
    pytest.param(
        insert_into_default_host("\t"),
        id="internal-tab",
    ),
    pytest.param(
        insert_into_default_host("\v"),
        id="internal-control-whitespace",
    ),
)
UNSPECIFIED_HOST_VARIANTS = (
    pytest.param(
        replace_default_target_host(str(IPv4Address(0))),
        id="ipv4-unspecified",
    ),
    pytest.param(
        replace_default_target_host(str(IPv6Address(0))),
        id="ipv6-unspecified",
    ),
    pytest.param(
        replace_default_target_host(
            str(IPv6Address(0xFFFF << 32))
        ),
        id="ipv4-mapped-ipv6-unspecified",
    ),
)
NEW_HOST_POLICY_VARIANTS = (
    NON_ASCII_HOST_VARIANTS
    + INTERNAL_ASCII_WHITESPACE_VARIANTS
    + UNSPECIFIED_HOST_VARIANTS
)


@pytest.mark.parametrize("variant", AMBIGUOUS_HOST_VARIANTS)
def test_production_rejects_ambiguous_noncanonical_host(
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize("variant", NON_ASCII_HOST_VARIANTS)
def test_production_rejects_non_ascii_host(
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize(
    "variant",
    INTERNAL_ASCII_WHITESPACE_VARIANTS,
)
def test_production_rejects_internal_ascii_whitespace(
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize("variant", UNSPECIFIED_HOST_VARIANTS)
def test_production_rejects_unspecified_host(
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(
            use_canonical_distinct_ipv4,
            id="canonical-distinct-ipv4",
        ),
        pytest.param(
            use_canonical_distinct_ipv6,
            id="canonical-distinct-ipv6",
        ),
        pytest.param(
            use_normal_dns_hostname,
            id="normal-dns-hostname",
        ),
    ],
)
def test_production_accepts_canonical_ip_and_dns_hosts(
    variant: Callable[[URL], URL],
) -> None:
    candidate = render_candidate(
        variant(explicit_production_target())
    )

    settings = Settings(
        environment="production",
        database_url=candidate,
        _env_file=None,
    )

    assert settings.database_url == candidate


@pytest.mark.parametrize("environment", ["development", "test"])
@pytest.mark.parametrize("variant", AMBIGUOUS_HOST_VARIANTS)
def test_non_production_retains_ambiguous_host_behavior(
    environment: str,
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    settings = Settings(
        environment=environment,
        database_url=candidate,
        _env_file=None,
    )

    assert settings.database_url == candidate


@pytest.mark.parametrize("environment", ["development", "test"])
@pytest.mark.parametrize("variant", NEW_HOST_POLICY_VARIANTS)
def test_non_production_retains_new_host_policy_behavior(
    environment: str,
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    settings = Settings(
        environment=environment,
        database_url=candidate,
        _env_file=None,
    )

    assert settings.database_url == candidate


def test_new_host_policy_validation_hides_sensitive_output(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default = parsed_default_database_url()
    assert default.port is not None
    markers = (
        "PHASE_C4A_UNICODE_USERNAME_SENTINEL",
        "PHASE_C4A_UNICODE_PASSWORD_SENTINEL",
        use_compatibility_letter("localhost"),
        "PHASE_C4A_UNICODE_DATABASE_SENTINEL",
    )
    port_marker = str(default.port + 7)
    candidate = render_candidate(
        URL.create(
            drivername=default.drivername,
            username=markers[0],
            password=markers[1],
            host=markers[2],
            port=int(port_marker),
            database=markers[3],
        )
    )

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)
    captured = capsys.readouterr()
    visible_output = " ".join(
        (
            str(error_info.value),
            caplog.text,
            captured.out,
            captured.err,
        )
    ).casefold()
    assert candidate.casefold() not in visible_output
    for marker in (*markers, port_marker):
        assert marker.casefold() not in visible_output


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(
            transform_default_target_host(
                use_compatibility_letter
            ),
            id="non-ascii-host",
        ),
        pytest.param(
            replace_default_target_host(str(IPv6Address(0))),
            id="unspecified-host",
        ),
    ],
)
def test_new_host_policy_validation_does_not_use_network_or_database(
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())
    guarded_targets = (
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.create_connection",
        "socket.socket",
        "asyncpg.connect",
        "sqlalchemy.engine.Engine.connect",
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
        "sqlalchemy.ext.asyncio.AsyncConnection.run_sync",
        "sqlalchemy.sql.schema.MetaData.create_all",
    )

    with ExitStack() as stack:
        guarded_calls = [
            stack.enter_context(patch(target))
            for target in guarded_targets
        ]
        with pytest.raises(ValidationError) as error_info:
            Settings(
                environment="production",
                database_url=candidate,
                _env_file=None,
            )

    assert_explicit_target_error(error_info.value)
    assert not any(guard.called for guard in guarded_calls)


def test_ambiguous_host_validation_hides_sensitive_output(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default = parsed_default_database_url()
    assert default.port is not None
    markers = (
        "PHASE_C4A_NUMERIC_USERNAME_SENTINEL",
        "PHASE_C4A_NUMERIC_PASSWORD_SENTINEL",
        str((127 << 24) | 1),
        "PHASE_C4A_NUMERIC_DATABASE_SENTINEL",
    )
    port_marker = str(default.port + 3)
    candidate = render_candidate(
        URL.create(
            drivername=default.drivername,
            username=markers[0],
            password=markers[1],
            host=markers[2],
            port=int(port_marker),
            database=markers[3],
        )
    )

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)
    captured = capsys.readouterr()
    visible_output = " ".join(
        (
            str(error_info.value),
            caplog.text,
            captured.out,
            captured.err,
        )
    ).casefold()
    assert candidate.casefold() not in visible_output
    for marker in (*markers, port_marker):
        assert marker.casefold() not in visible_output


def test_ambiguous_host_validation_does_not_use_network_or_database() -> None:
    candidate = replace_default_target_host(
        str((127 << 24) | 1)
    )(parsed_default_database_url())
    guarded_targets = (
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.create_connection",
        "socket.socket",
        "asyncpg.connect",
        "sqlalchemy.engine.Engine.connect",
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
        "sqlalchemy.ext.asyncio.AsyncConnection.run_sync",
        "sqlalchemy.sql.schema.MetaData.create_all",
    )

    with ExitStack() as stack:
        guarded_calls = [
            stack.enter_context(patch(target))
            for target in guarded_targets
        ]
        with pytest.raises(ValidationError) as error_info:
            Settings(
                environment="production",
                database_url=candidate,
                _env_file=None,
            )

    assert_explicit_target_error(error_info.value)
    assert not any(guard.called for guard in guarded_calls)


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(without_host, id="missing-host"),
        pytest.param(without_port, id="missing-port"),
        pytest.param(without_username, id="missing-username"),
        pytest.param(without_password, id="missing-password"),
        pytest.param(without_database, id="missing-database"),
    ],
)
def test_production_rejects_incomplete_explicit_target(
    variant: Callable[[URL], URL],
) -> None:
    candidate = render_candidate(variant(explicit_production_target()))

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(with_empty_host, id="empty-host"),
        pytest.param(with_empty_username, id="empty-username"),
        pytest.param(with_empty_password, id="empty-password"),
        pytest.param(with_empty_database, id="empty-database"),
    ],
)
def test_production_rejects_empty_explicit_target_component(
    variant: Callable[[URL], URL],
) -> None:
    candidate = render_candidate(variant(explicit_production_target()))

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(
            with_duplicate_loopback_hosts,
            id="duplicate-loopback",
        ),
        pytest.param(with_mixed_loopback_hosts, id="mixed-loopback"),
        pytest.param(with_distinct_hosts, id="distinct-hosts"),
        pytest.param(
            with_percent_encoded_host_separator,
            id="percent-encoded-separator",
        ),
    ],
)
def test_production_rejects_multi_host_target(
    variant: Callable[[URL], URL],
) -> None:
    candidate = render_candidate(variant(explicit_production_target()))

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)


@pytest.mark.parametrize("environment", ["development", "test"])
@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(without_host, id="missing-host"),
        pytest.param(without_port, id="missing-port"),
        pytest.param(without_username, id="missing-username"),
        pytest.param(without_password, id="missing-password"),
        pytest.param(without_database, id="missing-database"),
        pytest.param(
            with_duplicate_loopback_hosts,
            id="duplicate-loopback",
        ),
        pytest.param(with_mixed_loopback_hosts, id="mixed-loopback"),
        pytest.param(with_distinct_hosts, id="distinct-hosts"),
    ],
)
def test_non_production_retains_incomplete_and_multi_host_behavior(
    environment: str,
    variant: Callable[[URL], URL],
) -> None:
    candidate = render_candidate(variant(explicit_production_target()))

    settings = Settings(
        environment=environment,
        database_url=candidate,
        _env_file=None,
    )

    assert settings.database_url == candidate


def test_production_accepts_complete_explicit_single_host_target() -> None:
    candidate = render_candidate(explicit_production_target())

    settings = Settings(
        environment="production",
        database_url=candidate,
        _env_file=None,
    )

    assert settings.database_url == candidate


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(without_host, id="missing-host"),
        pytest.param(without_port, id="missing-port"),
        pytest.param(without_username, id="missing-username"),
        pytest.param(without_password, id="missing-password"),
        pytest.param(without_database, id="missing-database"),
    ],
)
def test_production_rejects_incomplete_target_despite_ambient_pg_fallback(
    variant: Callable[[URL], URL],
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambient_markers = tuple(
        f"PHASE_C4A_{variable}_FALLBACK_SENTINEL"
        for variable in AMBIENT_PG_VARIABLES
    )
    for variable, marker in zip(
        AMBIENT_PG_VARIABLES,
        ambient_markers,
        strict=True,
    ):
        monkeypatch.setenv(variable, marker)
    candidate = render_candidate(
        variant(explicit_production_target())
    )

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)
    captured = capsys.readouterr()
    visible_output = " ".join(
        (
            str(error_info.value),
            caplog.text,
            captured.out,
            captured.err,
        )
    ).casefold()
    assert candidate.casefold() not in visible_output
    for marker in ambient_markers:
        assert marker.casefold() not in visible_output


def test_explicit_target_validation_hides_inputs_and_ambient_pg_values(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_markers = (
        "PHASE_C4A_EXPLICIT_USERNAME_SENTINEL",
        "PHASE_C4A_EXPLICIT_PASSWORD_SENTINEL",
        "PHASE_C4A_EXPLICIT_HOST_ONE_SENTINEL",
        "PHASE_C4A_EXPLICIT_HOST_TWO_SENTINEL",
        "PHASE_C4A_EXPLICIT_DATABASE_SENTINEL",
    )
    ambient_markers = tuple(
        f"PHASE_C4A_{variable}_SENTINEL"
        for variable in AMBIENT_PG_VARIABLES
    )
    for variable, marker in zip(
        AMBIENT_PG_VARIABLES,
        ambient_markers,
        strict=True,
    ):
        monkeypatch.setenv(variable, marker)

    default = parsed_default_database_url()
    assert default.port is not None
    port_marker = str(default.port + 2)
    candidate = render_candidate(
        URL.create(
            drivername=default.drivername,
            username=candidate_markers[0],
            password=candidate_markers[1],
            host=f"{candidate_markers[2]},{candidate_markers[3]}",
            port=int(port_marker),
            database=candidate_markers[4],
        )
    )

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert_explicit_target_error(error_info.value)
    captured = capsys.readouterr()
    visible_output = " ".join(
        (
            str(error_info.value),
            caplog.text,
            captured.out,
            captured.err,
        )
    ).casefold()
    assert candidate.casefold() not in visible_output
    for marker in (*candidate_markers, *ambient_markers, port_marker):
        assert marker.casefold() not in visible_output


def test_explicit_target_validation_does_not_use_network_or_database() -> None:
    candidate = render_candidate(without_host(explicit_production_target()))
    guarded_targets = (
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.create_connection",
        "socket.socket",
        "asyncpg.connect",
        "sqlalchemy.engine.Engine.connect",
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
        "sqlalchemy.ext.asyncio.AsyncConnection.run_sync",
        "sqlalchemy.sql.schema.MetaData.create_all",
    )

    with ExitStack() as stack:
        guarded_calls = [
            stack.enter_context(patch(target))
            for target in guarded_targets
        ]
        with pytest.raises(ValidationError) as error_info:
            Settings(
                environment="production",
                database_url=candidate,
                _env_file=None,
            )

    assert_explicit_target_error(error_info.value)
    assert not any(guard.called for guard in guarded_calls)


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(omit_default_port, id="omitted-default-port"),
        pytest.param(vary_host_case, id="host-case"),
        pytest.param(add_trailing_dot_to_local_host, id="trailing-dot"),
        pytest.param(use_ipv4_loopback, id="ipv4-loopback"),
        pytest.param(use_ipv6_loopback, id="ipv6-loopback"),
        pytest.param(percent_encode_identity, id="percent-encoded"),
        pytest.param(add_harmless_query_option, id="harmless-query"),
    ],
)
def test_production_rejects_canonical_development_target_variants(
    variant: Callable[[URL], str],
) -> None:
    candidate = variant(parsed_default_database_url())

    with pytest.raises(ValidationError, match=DEFAULT_TARGET_ERROR):
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )


def test_production_rejects_driver_case_variant() -> None:
    default = parsed_default_database_url()
    candidate = render_default_target(
        drivername=default.drivername.swapcase()
    )

    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )


@pytest.mark.parametrize(
    "query_key",
    [
        pytest.param(key, id=key)
        for key in TARGET_IDENTITY_QUERY_KEYS
    ]
    + [
        pytest.param(key.swapcase(), id=f"{key}-mixed-case")
        for key in TARGET_IDENTITY_QUERY_KEYS
    ],
)
def test_production_rejects_target_identity_override_query_keys(
    query_key: str,
) -> None:
    default = parsed_default_database_url()
    assert default.database is not None
    candidate = render_default_target(
        database=f"{default.database}_phase_c4a_distinct",
        query={query_key: "phase-c4a-query-value"},
    )

    with pytest.raises(ValidationError, match=AMBIGUOUS_TARGET_ERROR):
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )


def test_production_rejects_percent_encoded_target_override_query_key() -> None:
    default = parsed_default_database_url()
    assert default.database is not None
    candidate = (
        render_default_target(
            database=f"{default.database}_phase_c4a_distinct"
        )
        + f"?{percent_encode('host')}=phase-c4a-query-value"
    )

    with pytest.raises(ValidationError, match=AMBIGUOUS_TARGET_ERROR):
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )


@pytest.mark.parametrize("environment", ["development", "test"])
def test_non_production_retains_current_query_option_behavior(
    environment: str,
) -> None:
    candidate = render_default_target(
        query={"host": "phase-c4a-non-production-value"}
    )

    settings = Settings(
        environment=environment,
        database_url=candidate,
        _env_file=None,
    )

    assert settings.database_url == candidate


def test_production_validation_hides_structural_target_inputs_and_output(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default = parsed_default_database_url()
    markers = (
        "PHASE_C4A_USERNAME_SENTINEL",
        "PHASE_C4A_PASSWORD_SENTINEL",
        "PHASE_C4A_HOST_SENTINEL",
        "PHASE_C4A_DATABASE_SENTINEL",
        "PHASE_C4A_QUERY_SENTINEL",
    )
    assert default.port is not None
    port_marker = str(default.port + 1)
    candidate = URL.create(
        drivername=default.drivername,
        username=markers[0],
        password=markers[1],
        host=markers[2],
        port=int(port_marker),
        database=markers[3],
        query={"HoSt": markers[4]},
    ).render_as_string(hide_password=False)

    with pytest.raises(
        ValidationError,
        match=AMBIGUOUS_TARGET_ERROR,
    ) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    captured = capsys.readouterr()
    visible_output = " ".join(
        (
            str(error_info.value),
            caplog.text,
            captured.out,
            captured.err,
        )
    ).casefold()
    assert candidate.casefold() not in visible_output
    for marker in (*markers, port_marker):
        assert marker.casefold() not in visible_output


def test_production_validation_hides_parser_error_input(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default = parsed_default_database_url()
    assert default.port is not None
    sentinel = "PHASE_C4A_INVALID_PORT_SENTINEL"
    candidate = render_default_target().replace(
        f":{default.port}/",
        f":{sentinel}/",
        1,
    )

    with pytest.raises(
        ValidationError,
        match="database_url is invalid",
    ) as error_info:
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    captured = capsys.readouterr()
    visible_output = " ".join(
        (
            str(error_info.value),
            caplog.text,
            captured.out,
            captured.err,
        )
    ).casefold()
    assert candidate.casefold() not in visible_output
    assert sentinel.casefold() not in visible_output


def test_production_target_validation_does_not_use_network() -> None:
    candidate = omit_default_port(parsed_default_database_url())
    network_targets = (
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.create_connection",
        "socket.socket",
    )

    with (
        patch(network_targets[0]) as getaddrinfo,
        patch(network_targets[1]) as gethostbyaddr,
        patch(network_targets[2]) as gethostbyname,
        patch(network_targets[3]) as create_connection,
        patch(network_targets[4]) as socket_constructor,
        pytest.raises(ValidationError, match=DEFAULT_TARGET_ERROR),
    ):
        Settings(
            environment="production",
            database_url=candidate,
            _env_file=None,
        )

    assert socket.getdefaulttimeout() is None
    assert not any(
        mock.called
        for mock in (
            getaddrinfo,
            gethostbyaddr,
            gethostbyname,
            create_connection,
            socket_constructor,
        )
    )
