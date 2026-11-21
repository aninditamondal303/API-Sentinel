"""The rule catalog: the single source of truth for every finding's wording and severity.

Comparators only emit a rule ID plus details; all human-facing text comes from
here, so wording stays consistent and every rule can be listed with
``apisentinel rules``. Rule IDs are permanent and never reused.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any


class Severity(IntEnum):
    """Ordered so that ``severity >= Severity.HIGH`` works for thresholds."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: str) -> Severity:
        try:
            return cls[value.strip().upper()]
        except KeyError:
            allowed = ", ".join(s.name.lower() for s in cls)
            raise ValueError(f"Unknown severity '{value}'. Use one of: {allowed}.") from None


class Category(StrEnum):
    COMPATIBILITY = "COMPATIBILITY"
    SECURITY_REGRESSION = "SECURITY_REGRESSION"
    SPEC_HYGIENE = "SPEC_HYGIENE"


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    title: str
    category: Category
    severity: Severity
    manual_review: bool
    message: str
    impact: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "severity": self.severity.name,
            "requiresManualReview": self.manual_review,
            "impact": self.impact,
            "remediation": self.remediation,
        }


class _Formatter(string.Formatter):
    """str.format that renders missing fields as '?' instead of raising."""

    def get_value(self, key: int | str, args: Any, kwargs: Any) -> Any:
        if isinstance(key, str):
            return kwargs.get(key, "?")
        return super().get_value(key, args, kwargs)


_FORMATTER = _Formatter()


def render(template: str, details: dict[str, Any]) -> str:
    return _FORMATTER.format(template, **details)


C = Category.COMPATIBILITY
S = Category.SECURITY_REGRESSION
H = Category.SPEC_HYGIENE
_ = Severity

_RULES: list[Rule] = [
    # --- Operations -------------------------------------------------------------
    Rule(
        "OP-001",
        "Path removed",
        C,
        _.CRITICAL,
        False,
        "{method} {path} was removed (the whole path no longer exists).",
        "Every client calling this operation will receive 404 Not Found.",
        "Restore the path, or keep it and mark it deprecated until clients have migrated.",
    ),
    Rule(
        "OP-002",
        "HTTP method removed",
        C,
        _.CRITICAL,
        False,
        "{method} was removed from {path}; other methods on the path remain.",
        "Clients calling this method will receive 404 or 405 Method Not Allowed.",
        "Restore the method, or deprecate it first and remove it in a new major version.",
    ),
    Rule(
        "OP-003",
        "Deprecated operation removed",
        C,
        _.HIGH,
        False,
        "{method} {path} was removed; it was already marked deprecated.",
        "Clients that have not migrated off the deprecated operation will now fail.",
        "Confirm the deprecation window has passed and announce the removal in the changelog.",
    ),
    Rule(
        "OP-004",
        "Operation deprecated",
        C,
        _.INFO,
        False,
        "{method} {path} is now marked deprecated.",
        "No immediate breakage; clients should plan to migrate.",
        "Document the replacement operation and the planned removal date.",
    ),
    Rule(
        "OP-005",
        "Path parameter renamed",
        C,
        _.INFO,
        False,
        "Path parameter renamed from '{old}' to '{new}'.",
        "Wire format is unchanged; generated client code may change parameter names.",
        "No action needed unless SDK parameter names are part of your public contract.",
    ),
    Rule(
        "OP-006",
        "Operation added",
        C,
        _.INFO,
        False,
        "{method} {path} was added.",
        "Additive change; existing clients are unaffected.",
        "Document the new operation.",
    ),
    # --- Request parameters -----------------------------------------------------
    Rule(
        "REQ-PARAM-001",
        "Request parameter removed",
        C,
        _.MEDIUM,
        False,
        "The {location_kind} parameter '{name}' was removed.",
        "Clients still send it; the server will now ignore or reject it, silently changing "
        "behaviour.",
        "Keep accepting the parameter (deprecated) until clients stop sending it.",
    ),
    Rule(
        "REQ-PARAM-002",
        "New required parameter",
        C,
        _.CRITICAL,
        False,
        "New required {location_kind} parameter '{name}'.",
        "Existing clients do not send '{name}'; the server is likely to reject their requests "
        "with 400.",
        "Make '{name}' optional with a server-side default, or introduce it in a new version.",
    ),
    Rule(
        "REQ-PARAM-003",
        "Parameter became required",
        C,
        _.HIGH,
        False,
        "The {location_kind} parameter '{name}' changed from optional to required.",
        "Clients that omit '{name}' will start receiving 400 responses.",
        "Keep the parameter optional and apply a default when it is missing.",
    ),
    Rule(
        "REQ-PARAM-004",
        "Parameter type narrowed",
        C,
        _.HIGH,
        False,
        "Type of {field} changed from {old} to {new}.",
        "Values clients currently send may no longer be accepted.",
        "Accept both the old and the new type, or version the operation.",
    ),
    Rule(
        "REQ-PARAM-005",
        "Parameter enum narrowed",
        C,
        _.HIGH,
        False,
        "Allowed values of {field} were restricted: {detail}.",
        "Clients sending a removed value will receive 400 responses.",
        "Keep accepting the removed values, mapping them to the new behaviour if needed.",
    ),
    Rule(
        "REQ-PARAM-006",
        "Parameter constraints tightened",
        C,
        _.MEDIUM,
        False,
        "Validation of {field} became stricter: {detail}.",
        "Values that were valid before may now be rejected.",
        "Relax the constraint, or confirm with usage data that no client sends affected values.",
    ),
    Rule(
        "REQ-PARAM-007",
        "Parameter serialization changed",
        C,
        _.MEDIUM,
        False,
        "Serialization of {field} changed from {old} to {new}.",
        "Clients will encode the parameter in a format the server no longer parses as before.",
        "Keep the previous style/explode, or accept both encodings during a transition.",
    ),
    Rule(
        "REQ-PARAM-008",
        "Parameter default changed",
        C,
        _.MEDIUM,
        False,
        "Default of {field} changed from {old} to {new}.",
        "Clients that omit the parameter silently get different behaviour.",
        "Keep the old default, or announce the behaviour change prominently.",
    ),
    Rule(
        "REQ-PARAM-009",
        "Parameter pattern changed",
        C,
        _.MEDIUM,
        True,
        "Pattern of {field} changed from {old} to {new}.",
        "Regular-expression containment cannot be decided automatically; valid values may now "
        "be rejected.",
        "Check that every value accepted by the old pattern is accepted by the new one.",
    ),
    Rule(
        "REQ-PARAM-010",
        "Optional parameter added",
        C,
        _.INFO,
        False,
        "Optional {location_kind} parameter '{name}' was added.",
        "Additive change; existing clients are unaffected.",
        "Document the new parameter.",
    ),
    Rule(
        "REQ-PARAM-011",
        "Parameter format changed",
        C,
        _.MEDIUM,
        True,
        "Format of {field} changed from {old} to {new}.",
        "Values clients send in the old format may be rejected or misparsed.",
        "Accept both formats, or confirm all clients already send the new format.",
    ),
    Rule(
        "REQ-PARAM-012",
        "Complex parameter schema changed",
        C,
        _.MEDIUM,
        True,
        "The object schema of {field} changed ({detail}).",
        "Object-valued parameters depend on serialization rules the engine does not model fully.",
        "Review how clients serialize this parameter before and after the change.",
    ),
    # --- Request bodies ---------------------------------------------------------
    Rule(
        "REQ-BODY-001",
        "Request body became required",
        C,
        _.HIGH,
        False,
        "The request body is now required.",
        "Clients that send no body will receive 400 responses.",
        "Keep the body optional, or supply defaults when it is absent.",
    ),
    Rule(
        "REQ-BODY-002",
        "Request media type removed",
        C,
        _.HIGH,
        False,
        "Request media type '{media}' is no longer accepted.",
        "Clients sending '{media}' will receive 415 Unsupported Media Type.",
        "Keep accepting '{media}' until clients have switched.",
    ),
    Rule(
        "REQ-BODY-003",
        "New required request property",
        C,
        _.CRITICAL,
        False,
        "New required property {field}.",
        "Existing clients do not send it; their requests will fail validation.",
        "Make the property optional with a default, or version the operation.",
    ),
    Rule(
        "REQ-BODY-004",
        "Request property became required",
        C,
        _.HIGH,
        False,
        "Property {field} changed from optional to required.",
        "Clients that omit it will start receiving 400 responses.",
        "Keep it optional and apply a server-side default.",
    ),
    Rule(
        "REQ-BODY-005",
        "Request property removed (rejected)",
        C,
        _.HIGH,
        False,
        "Property {field} was removed and additional properties are not allowed.",
        "Clients still sending it will have their requests rejected.",
        "Keep the property (ignored and deprecated) or allow additional properties.",
    ),
    Rule(
        "REQ-BODY-006",
        "Request property removed (ignored)",
        C,
        _.MEDIUM,
        False,
        "Property {field} was removed from the request schema.",
        "Clients still send it and it will be silently ignored, changing behaviour.",
        "Keep accepting the property until clients stop sending it.",
    ),
    Rule(
        "REQ-BODY-007",
        "Request property type narrowed",
        C,
        _.HIGH,
        False,
        "Type of {field} changed from {old} to {new}.",
        "Values clients currently send may fail validation.",
        "Accept both types, or version the operation.",
    ),
    Rule(
        "REQ-BODY-008",
        "Request property format changed",
        C,
        _.MEDIUM,
        True,
        "Format of {field} changed from {old} to {new}.",
        "Values in the old format may be rejected or misparsed.",
        "Accept both formats during a transition period.",
    ),
    Rule(
        "REQ-BODY-009",
        "Request enum narrowed",
        C,
        _.HIGH,
        False,
        "Allowed values of {field} were restricted: {detail}.",
        "Clients sending a removed value will receive 400 responses.",
        "Keep accepting removed values, mapping them to new behaviour if needed.",
    ),
    Rule(
        "REQ-BODY-010",
        "Request constraints tightened",
        C,
        _.MEDIUM,
        False,
        "Validation of {field} became stricter: {detail}.",
        "Values that were valid before may now be rejected.",
        "Relax the constraint or confirm no client sends affected values.",
    ),
    Rule(
        "REQ-BODY-011",
        "Additional properties no longer allowed",
        C,
        _.HIGH,
        False,
        "{field} no longer allows additional properties.",
        "Clients sending any undeclared field will now be rejected.",
        "Allow additional properties, or confirm clients send only declared fields.",
    ),
    Rule(
        "REQ-BODY-012",
        "Optional request property added",
        C,
        _.INFO,
        False,
        "Optional property {field} was added.",
        "Additive change; existing clients are unaffected.",
        "Document the new property.",
    ),
    Rule(
        "REQ-BODY-013",
        "Request property pattern changed",
        C,
        _.MEDIUM,
        True,
        "Pattern of {field} changed from {old} to {new}.",
        "Regular-expression containment cannot be decided automatically; valid values may now "
        "be rejected.",
        "Check that every value accepted by the old pattern is accepted by the new one.",
    ),
    Rule(
        "REQ-BODY-014",
        "Request property default changed",
        C,
        _.MEDIUM,
        False,
        "Default of {field} changed from {old} to {new}.",
        "Clients omitting the property silently get different behaviour.",
        "Keep the old default or announce the behaviour change.",
    ),
    Rule(
        "REQ-BODY-015",
        "Request body removed",
        C,
        _.MEDIUM,
        False,
        "The operation no longer documents a request body.",
        "Clients still send a body that the server will ignore or reject.",
        "Keep accepting the body until clients stop sending it.",
    ),
    # --- Responses --------------------------------------------------------------
    Rule(
        "RES-001",
        "Success status code removed",
        C,
        _.HIGH,
        False,
        "Success response {status} was removed.",
        "Clients that check for {status} will treat successful calls as failures.",
        "Keep returning {status}, or version the operation.",
    ),
    Rule(
        "RES-002",
        "Error status code removed",
        C,
        _.LOW,
        False,
        "Documented response {status} was removed.",
        "Usually harmless; clients handling {status} simply stop seeing it.",
        "Confirm the server really no longer returns {status}.",
    ),
    Rule(
        "RES-003",
        "Success status code added",
        C,
        _.MEDIUM,
        False,
        "New success response {status} was added.",
        "Clients that only handle the previously documented success codes may treat {status} "
        "as an error.",
        "Check that clients accept any 2xx, or keep the previous status code.",
    ),
    Rule(
        "RES-004",
        "Response media type removed",
        C,
        _.HIGH,
        False,
        "Response {status} no longer offers media type '{media}'.",
        "Clients requesting or parsing '{media}' will fail.",
        "Keep producing '{media}' until clients have migrated.",
    ),
    Rule(
        "RES-005",
        "Response property removed",
        C,
        _.HIGH,
        False,
        "Response property {field} was removed.",
        "Clients reading it will get null/undefined values or deserialization errors.",
        "Keep the property (deprecated) or version the response.",
    ),
    Rule(
        "RES-006",
        "Response property became optional",
        C,
        _.MEDIUM,
        False,
        "Response property {field} is no longer required.",
        "Clients assuming it is always present may crash when it is missing.",
        "Keep it required, or confirm clients handle its absence.",
    ),
    Rule(
        "RES-007",
        "Response property type changed",
        C,
        _.HIGH,
        False,
        "Type of {field} changed from {old} to {new}.",
        "Clients parsing the old type will fail or misinterpret values.",
        "Keep the old type, or add a new property with the new type.",
    ),
    Rule(
        "RES-008",
        "Response property became nullable",
        C,
        _.MEDIUM,
        False,
        "{field} may now be null.",
        "Clients that do not expect null may crash.",
        "Keep the field non-null, or confirm clients handle null.",
    ),
    Rule(
        "RES-009",
        "Response enum widened",
        C,
        _.MEDIUM,
        False,
        "{field} may now return additional values: {detail}.",
        "Clients with exhaustive switches or strict enums will fail on the new values.",
        "Confirm clients have a default branch for unknown values before shipping.",
    ),
    Rule(
        "RES-010",
        "Response enum value removed",
        C,
        _.INFO,
        False,
        "{field} will no longer return: {detail}.",
        "Safe for clients; branches for the removed values become dead code.",
        "No action needed.",
    ),
    Rule(
        "RES-011",
        "Response body shape changed",
        C,
        _.CRITICAL,
        False,
        "Response body of {field} changed shape from {old} to {new}.",
        "Every client deserializing this response will fail.",
        "Keep the old shape; put the new shape in a new operation or version.",
    ),
    Rule(
        "RES-012",
        "Response property format changed",
        C,
        _.MEDIUM,
        True,
        "Format of {field} changed from {old} to {new}.",
        "Clients parsing the old format (for example dates) may fail.",
        "Keep the old format, or add a new property in the new format.",
    ),
    Rule(
        "RES-013",
        "Response property added",
        C,
        _.INFO,
        False,
        "Response property {field} was added.",
        "Additive; only clients that reject unknown fields are affected.",
        "Document the new property.",
    ),
    Rule(
        "RES-014",
        "Response constraints relaxed",
        C,
        _.LOW,
        False,
        "Constraints on {field} were relaxed: {detail}.",
        "Clients relying on the old limits (for example column sizes) may overflow.",
        "Confirm client-side storage and validation accept the wider range.",
    ),
    Rule(
        "RES-015",
        "Response property pattern changed",
        C,
        _.LOW,
        True,
        "Pattern of {field} changed from {old} to {new}.",
        "Clients validating the old pattern may reject new values.",
        "Check client-side validation against the new pattern.",
    ),
    # --- Authentication (compatibility) -----------------------------------------
    Rule(
        "AUTH-001",
        "Authentication added",
        C,
        _.CRITICAL,
        False,
        "{method} {path} now requires authentication ({new}).",
        "Clients calling it anonymously will receive 401 Unauthorized.",
        "Announce the requirement in advance, or keep anonymous access during a transition.",
    ),
    Rule(
        "AUTH-002",
        "Credentials no longer accepted",
        C,
        _.CRITICAL,
        False,
        "Security requirement changed from {old} to {new}.",
        "Clients presenting the previously accepted credentials will receive 401 or 403.",
        "Accept both the old and the new scheme during a migration window.",
    ),
    Rule(
        "AUTH-003",
        "Required scopes added",
        C,
        _.HIGH,
        False,
        "Additional OAuth scopes are required: {detail}.",
        "Existing tokens without the new scopes will receive 403 Forbidden.",
        "Coordinate scope grants with clients before enforcing them.",
    ),
    # --- Security regressions ---------------------------------------------------
    Rule(
        "SEC-R001",
        "Security requirement removed",
        S,
        _.HIGH,
        False,
        "{method} {path} no longer declares any security requirement (was {old}).",
        "The operation is now documented as public; if intentional, data may be exposed.",
        "Confirm the operation is meant to be public; otherwise restore the requirement.",
    ),
    Rule(
        "SEC-R002",
        "Weaker authentication accepted",
        S,
        _.MEDIUM,
        False,
        "{method} {path} now accepts a weaker requirement: {new}.",
        "Callers can authenticate with less than was previously demanded, or not at all.",
        "Confirm the weaker alternative is intended and protected appropriately.",
    ),
    Rule(
        "SEC-R003",
        "Required scopes reduced",
        S,
        _.MEDIUM,
        False,
        "Fewer OAuth scopes are required: {detail}.",
        "Tokens with narrower grants can now perform this operation.",
        "Confirm the reduced scope set still enforces least privilege.",
    ),
    Rule(
        "SEC-R004",
        "Server URL downgraded to HTTP",
        S,
        _.HIGH,
        False,
        "Server '{old}' changed to plain HTTP '{new}'.",
        "Traffic, including credentials, would travel unencrypted.",
        "Keep HTTPS for every non-local server URL.",
    ),
    # --- Specification security hygiene (single spec) ----------------------------
    Rule(
        "SEC-H001",
        "Server URL uses plain HTTP",
        H,
        _.MEDIUM,
        False,
        "Server '{url}' uses http:// instead of https://.",
        "Requests, tokens and responses to this server would travel unencrypted.",
        "Use an https:// URL for every non-local server.",
    ),
    Rule(
        "SEC-H002",
        "Operation has no security requirement",
        H,
        _.MEDIUM,
        False,
        "{method} {path} declares no security requirement and the document has no default.",
        "The operation is documented as callable without authentication.",
        "Add a security requirement, or mark it public explicitly with 'security: []'.",
    ),
    Rule(
        "SEC-H003",
        "Operation explicitly public",
        H,
        _.INFO,
        False,
        "{method} {path} is explicitly public ('security: []').",
        "Intentional public access; listed so it can be reviewed.",
        "Confirm the operation exposes no sensitive data.",
    ),
    Rule(
        "SEC-H004",
        "Undefined security scheme referenced",
        H,
        _.HIGH,
        False,
        "Security requirement references '{scheme}', which is not defined in "
        "components.securitySchemes.",
        "Clients and gateways cannot know how to authenticate; generated code may skip auth.",
        "Define '{scheme}' under components.securitySchemes or fix the name.",
    ),
    Rule(
        "SEC-H005",
        "Unused security scheme",
        H,
        _.LOW,
        False,
        "Security scheme '{scheme}' is defined but never required by any operation.",
        "Dead configuration can mislead readers about how the API is protected.",
        "Remove the scheme or reference it where it is enforced.",
    ),
    Rule(
        "SEC-H006",
        "Undefined OAuth2 scope required",
        H,
        _.MEDIUM,
        False,
        "Scope '{scope}' is required but not defined in any flow of scheme '{scheme}'.",
        "Clients cannot request a scope the authorization server does not advertise.",
        "Define the scope in the scheme's flows or correct the requirement.",
    ),
    Rule(
        "SEC-H007",
        "API key sent in the query string",
        H,
        _.MEDIUM,
        False,
        "Security scheme '{scheme}' sends the API key as query parameter '{name}'.",
        "Query strings are written to server logs, proxies and browser history.",
        "Send the key in a header instead.",
    ),
    Rule(
        "SEC-H008",
        "Basic authentication without HTTPS",
        H,
        _.HIGH,
        False,
        "Scheme '{scheme}' uses HTTP Basic while server '{url}' is plain HTTP.",
        "Basic credentials are only base64-encoded and would be exposed in transit.",
        "Serve the API over HTTPS only, or use a token-based scheme.",
    ),
    Rule(
        "SEC-H009",
        "Mutating operation less protected than read",
        H,
        _.MEDIUM,
        False,
        "{method} {path} is public while GET {path} requires authentication.",
        "Writes are usually more sensitive than reads; this pattern often indicates a "
        "missing requirement.",
        "Require at least the same authentication as GET on this path.",
    ),
    Rule(
        "SEC-H010",
        "Local server URL uses HTTP",
        H,
        _.INFO,
        False,
        "Local server '{url}' uses http://.",
        "Acceptable for local development; make sure it is not the only documented server.",
        "No action needed for local development servers.",
    ),
    Rule(
        "SEC-H011",
        "Deprecated OAuth2 flow",
        H,
        _.MEDIUM,
        False,
        "Scheme '{scheme}' uses the OAuth2 '{flow}' flow.",
        "The implicit and password flows are discouraged by current OAuth 2.0 security "
        "guidance (token leakage, credential exposure).",
        "Use the authorization code flow with PKCE, or client credentials for services.",
    ),
    Rule(
        "SEC-H012",
        "Authorization endpoint over HTTP",
        H,
        _.HIGH,
        False,
        "Scheme '{scheme}' uses a plain HTTP URL: '{url}'.",
        "Tokens or authorization codes would travel unencrypted.",
        "Use https:// for token, authorization and OpenID Connect URLs.",
    ),
    Rule(
        "SEC-H013",
        "Credential-like query parameter",
        H,
        _.MEDIUM,
        False,
        "{method} {path} accepts '{name}' as a query parameter.",
        "Secrets in query strings end up in logs, proxies and browser history.",
        "Accept the value in a header or request body instead.",
    ),
    Rule(
        "SEC-H014",
        "Optional authentication on mutating operation",
        H,
        _.MEDIUM,
        False,
        "{method} {path} allows anonymous access ('{{}}' alternative) for a write operation.",
        "Anyone can call this write operation without credentials.",
        "Remove the empty '{{}}' alternative unless anonymous writes are intended.",
    ),
    # --- Manual review ----------------------------------------------------------
    Rule(
        "MR-001",
        "Composition change needs review",
        C,
        _.MEDIUM,
        True,
        "{field}: {detail}.",
        "oneOf/anyOf/allOf changes can break clients in ways the engine cannot prove safe.",
        "Review the variants manually; prefer additive changes to response unions.",
    ),
    Rule(
        "MR-002",
        "Unsupported schema keyword changed",
        C,
        _.MEDIUM,
        True,
        "{field}: '{keyword}' changed; the engine does not analyse this keyword.",
        "Compatibility of this change is unknown.",
        "Review the change manually.",
    ),
    Rule(
        "MR-003",
        "Discriminator changed",
        C,
        _.MEDIUM,
        True,
        "Discriminator of {field} changed from {old} to {new}.",
        "Clients selecting subtypes by the old discriminator may deserialize the wrong type.",
        "Keep the discriminator property and mapping values stable.",
    ),
    Rule(
        "MR-004",
        "Schema too deep or cyclic to compare",
        C,
        _.LOW,
        True,
        "{field}: {detail}.",
        "Part of this schema was not compared.",
        "Review the change manually.",
    ),
]

RULES: dict[str, Rule] = {rule.id: rule for rule in _RULES}

if len(RULES) != len(_RULES):  # pragma: no cover - guards catalog edits
    raise RuntimeError("Duplicate rule IDs in catalog")
