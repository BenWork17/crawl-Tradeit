"""Country list for the buyer-search country picker.

Mirrors the TradeIT site exactly: same countries, same order, same group
names and the same English labels, plus Vietnamese labels and flag URLs.
No runtime dependency and no network access is needed to import this.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

FLAG_BASE = "https://flagcdn.com/w40"

# (code, English name shown on the site, Vietnamese name)
GROUPS: tuple[tuple[str, str, str, tuple[tuple[str, str, str], ...]], ...] = (
    ('AM', 'America', 'Châu Mỹ', (
        ('AG', 'Antigua & Barbuda', 'Antigua và Barbuda'),
        ('AR', 'Argentina', 'Argentina'),
        ('BS', 'Bahamas', 'Bahamas'),
        ('BB', 'Barbados', 'Barbados'),
        ('BZ', 'Belize', 'Belize'),
        ('BO', 'Bolivia', 'Bolivia'),
        ('BR', 'Brazil', 'Brazil'),
        ('CA', 'Canada', 'Canada'),
        ('CL', 'Chile', 'Chile'),
        ('CO', 'Colombia', 'Colombia'),
        ('CR', 'Costa Rica', 'Costa Rica'),
        ('CU', 'Cuba', 'Cuba'),
        ('DM', 'Dominica', 'Dominica'),
        ('DO', 'Dominican Republic', 'Cộng hòa Dominica'),
        ('EC', 'Ecuador', 'Ecuador'),
        ('SV', 'El Salvador', 'El Salvador'),
        ('GD', 'Grenada', 'Grenada'),
        ('GT', 'Guatemala', 'Guatemala'),
        ('GY', 'Guyana', 'Guyana'),
        ('HT', 'Haiti', 'Haiti'),
        ('HN', 'Honduras', 'Honduras'),
        ('JM', 'Jamaica', 'Jamaica'),
        ('MX', 'Mexico', 'Mexico'),
        ('PA', 'Panama', 'Panama'),
        ('PY', 'Paraguay', 'Paraguay'),
        ('PE', 'Peru', 'Peru'),
        ('KN', 'St. Kitts & Nevis', 'St. Kitts và Nevis'),
        ('LC', 'St. Lucia', 'St. Lucia'),
        ('VC', 'St. Vincent & Grenadines', 'St. Vincent và Grenadines'),
        ('SR', 'Suriname', 'Suriname'),
        ('TT', 'Trinidad & Tobago', 'Trinidad và Tobago'),
        ('US', 'United States', 'Hoa Kỳ'),
        ('UY', 'Uruguay', 'Uruguay'),
        ('VE', 'Venezuela', 'Venezuela'),
    )),
    ('AS', 'Asia', 'Châu Á', (
        ('AF', 'Afghanistan', 'Afghanistan'),
        ('AM', 'Armenia', 'Armenia'),
        ('BH', 'Bahrain', 'Bahrain'),
        ('BD', 'Bangladesh', 'Bangladesh'),
        ('BT', 'Bhutan', 'Bhutan'),
        ('BN', 'Brunei', 'Brunei'),
        ('KH', 'Cambodia', 'Campuchia'),
        ('CN', 'China', 'Trung Quốc'),
        ('CY', 'Cyprus', 'Síp'),
        ('HK', 'Hong Kong SAR', 'Hồng Kông'),
        ('IN', 'India', 'Ấn Độ'),
        ('ID', 'Indonesia', 'Indonesia'),
        ('IR', 'Iran', 'Iran'),
        ('IQ', 'Iraq', 'Iraq'),
        ('IL', 'Israel', 'Israel'),
        ('JP', 'Japan', 'Nhật Bản'),
        ('JO', 'Jordan', 'Jordan'),
        ('KZ', 'Kazakhstan', 'Kazakhstan'),
        ('KR', 'Korea', 'Hàn Quốc'),
        ('KW', 'Kuwait', 'Kuwait'),
        ('KG', 'Kyrgyzstan', 'Kyrgyzstan'),
        ('LA', 'Laos', 'Lào'),
        ('LB', 'Lebanon', 'Liban'),
        ('MY', 'Malaysia', 'Malaysia'),
        ('MV', 'Maldives', 'Maldives'),
        ('MN', 'Mongolia', 'Mông Cổ'),
        ('MM', 'Myanmar', 'Myanmar'),
        ('NP', 'Nepal', 'Nepal'),
        ('OM', 'Oman', 'Oman'),
        ('PK', 'Pakistan', 'Pakistan'),
        ('PS', 'Palestinian Authority', 'Palestine'),
        ('PH', 'Philippines', 'Philippines'),
        ('QA', 'Qatar', 'Qatar'),
        ('SA', 'Saudi Arabia', 'Ả Rập Xê Út'),
        ('SG', 'Singapore', 'Singapore'),
        ('LK', 'Sri Lanka', 'Sri Lanka'),
        ('SY', 'Syria', 'Syria'),
        ('TW', 'Taiwan', 'Đài Loan'),
        ('TJ', 'Tajikistan', 'Tajikistan'),
        ('TH', 'Thailand', 'Thái Lan'),
        ('TL', 'Timor-Leste', 'Đông Timor'),
        ('TR', 'Türkiye', 'Thổ Nhĩ Kỳ'),
        ('TM', 'Turkmenistan', 'Turkmenistan'),
        ('AE', 'United Arab Emirates', 'UAE'),
        ('UZ', 'Uzbekistan', 'Uzbekistan'),
        ('VN', 'Vietnam', 'Việt Nam'),
        ('YE', 'Yemen', 'Yemen'),
    )),
    ('AF', 'Africa', 'Châu Phi', (
        ('DZ', 'Algeria', 'Algeria'),
        ('AO', 'Angola', 'Angola'),
        ('BJ', 'Benin', 'Benin'),
        ('BW', 'Botswana', 'Botswana'),
        ('BF', 'Burkina Faso', 'Burkina Faso'),
        ('BI', 'Burundi', 'Burundi'),
        ('CV', 'Cabo Verde', 'Cabo Verde'),
        ('CM', 'Cameroon', 'Cameroon'),
        ('CF', 'Central African Republic', 'Cộng hòa Trung Phi'),
        ('TD', 'Chad', 'Chad'),
        ('KM', 'Comoros', 'Comoros'),
        ('CG', 'Congo', 'Congo'),
        ('CD', 'Congo (DRC)', 'Congo (CHDC)'),
        ('CI', 'Côte d’Ivoire', 'Bờ Biển Ngà'),
        ('DJ', 'Djibouti', 'Djibouti'),
        ('EG', 'Egypt', 'Ai Cập'),
        ('GQ', 'Equatorial Guinea', 'Guinea Xích Đạo'),
        ('ER', 'Eritrea', 'Eritrea'),
        ('SZ', 'Eswatini', 'Eswatini'),
        ('ET', 'Ethiopia', 'Ethiopia'),
        ('GA', 'Gabon', 'Gabon'),
        ('GM', 'Gambia', 'Gambia'),
        ('GH', 'Ghana', 'Ghana'),
        ('GN', 'Guinea', 'Guinea'),
        ('GW', 'Guinea-Bissau', 'Guinea-Bissau'),
        ('KE', 'Kenya', 'Kenya'),
        ('LS', 'Lesotho', 'Lesotho'),
        ('LR', 'Liberia', 'Liberia'),
        ('LY', 'Libya', 'Libya'),
        ('MG', 'Madagascar', 'Madagascar'),
        ('MW', 'Malawi', 'Malawi'),
        ('ML', 'Mali', 'Mali'),
        ('MR', 'Mauritania', 'Mauritania'),
        ('MU', 'Mauritius', 'Mauritius'),
        ('MA', 'Morocco', 'Maroc'),
        ('MZ', 'Mozambique', 'Mozambique'),
        ('NA', 'Namibia', 'Namibia'),
        ('NE', 'Niger', 'Niger'),
        ('NG', 'Nigeria', 'Nigeria'),
        ('RW', 'Rwanda', 'Rwanda'),
        ('ST', 'São Tomé & Príncipe', 'São Tomé và Príncipe'),
        ('SN', 'Senegal', 'Senegal'),
        ('SC', 'Seychelles', 'Seychelles'),
        ('SL', 'Sierra Leone', 'Sierra Leone'),
        ('SO', 'Somalia', 'Somalia'),
        ('ZA', 'South Africa', 'Nam Phi'),
        ('SS', 'South Sudan', 'Nam Sudan'),
        ('SH', 'St Helena, Ascension, Tristan da Cunha', 'St Helena, Ascension, Tristan da Cunha'),
        ('SD', 'Sudan', 'Sudan'),
        ('TZ', 'Tanzania', 'Tanzania'),
        ('TG', 'Togo', 'Togo'),
        ('TN', 'Tunisia', 'Tunisia'),
        ('UG', 'Uganda', 'Uganda'),
        ('ZM', 'Zambia', 'Zambia'),
        ('ZW', 'Zimbabwe', 'Zimbabwe'),
    )),
    ('OC', 'Oceania', 'Châu Đại Dương', (
        ('AU', 'Australia', 'Úc'),
        ('FJ', 'Fiji', 'Fiji'),
        ('KI', 'Kiribati', 'Kiribati'),
        ('MH', 'Marshall Islands', 'Quần đảo Marshall'),
        ('FM', 'Micronesia', 'Micronesia'),
        ('NR', 'Nauru', 'Nauru'),
        ('NZ', 'New Zealand', 'New Zealand'),
        ('PW', 'Palau', 'Palau'),
        ('PG', 'Papua New Guinea', 'Papua New Guinea'),
        ('WS', 'Samoa', 'Samoa'),
        ('SB', 'Solomon Islands', 'Quần đảo Solomon'),
        ('TO', 'Tonga', 'Tonga'),
        ('TV', 'Tuvalu', 'Tuvalu'),
        ('VU', 'Vanuatu', 'Vanuatu'),
    )),
    ('EU', 'Europe', 'Châu Âu', (
        ('AL', 'Albania', 'Albania'),
        ('AD', 'Andorra', 'Andorra'),
        ('AT', 'Austria', 'Áo'),
        ('BY', 'Belarus', 'Belarus'),
        ('BE', 'Belgium', 'Bỉ'),
        ('BA', 'Bosnia & Herzegovina', 'Bosnia và Herzegovina'),
        ('BG', 'Bulgaria', 'Bulgaria'),
        ('HR', 'Croatia', 'Croatia'),
        ('CZ', 'Czechia', 'Séc'),
        ('DK', 'Denmark', 'Đan Mạch'),
        ('EE', 'Estonia', 'Estonia'),
        ('FI', 'Finland', 'Phần Lan'),
        ('FR', 'France', 'Pháp'),
        ('GE', 'Georgia', 'Gruzia'),
        ('DE', 'Germany', 'Đức'),
        ('GR', 'Greece', 'Hy Lạp'),
        ('HU', 'Hungary', 'Hungary'),
        ('IS', 'Iceland', 'Iceland'),
        ('IE', 'Ireland', 'Ireland'),
        ('IT', 'Italy', 'Ý'),
        ('XK', 'Kosovo', 'Kosovo'),
        ('LV', 'Latvia', 'Latvia'),
        ('LI', 'Liechtenstein', 'Liechtenstein'),
        ('LT', 'Lithuania', 'Litva'),
        ('LU', 'Luxembourg', 'Luxembourg'),
        ('MT', 'Malta', 'Malta'),
        ('MD', 'Moldova', 'Moldova'),
        ('MC', 'Monaco', 'Monaco'),
        ('ME', 'Montenegro', 'Montenegro'),
        ('NL', 'Netherlands', 'Hà Lan'),
        ('MK', 'North Macedonia', 'Bắc Macedonia'),
        ('NO', 'Norway', 'Na Uy'),
        ('PL', 'Poland', 'Ba Lan'),
        ('PT', 'Portugal', 'Bồ Đào Nha'),
        ('RO', 'Romania', 'Romania'),
        ('RU', 'Russia', 'Nga'),
        ('SM', 'San Marino', 'San Marino'),
        ('RS', 'Serbia', 'Serbia'),
        ('SK', 'Slovakia', 'Slovakia'),
        ('SI', 'Slovenia', 'Slovenia'),
        ('ES', 'Spain', 'Tây Ban Nha'),
        ('SE', 'Sweden', 'Thụy Điển'),
        ('CH', 'Switzerland', 'Thụy Sĩ'),
        ('UA', 'Ukraine', 'Ukraine'),
        ('GB', 'United Kingdom', 'Vương quốc Anh'),
    )),
)

# Flat list in the exact order the site renders it.
COUNTRIES: tuple[tuple[str, str, str, str], ...] = tuple(
    (code, name_en, name_vi, group_code)
    for group_code, _name, _vi, members in GROUPS
    for code, name_en, name_vi in members
)

COUNTRY_BY_CODE: dict[str, dict[str, str]] = {
    row[0]: {
        "code": row[0],
        "name": row[1],
        "name_vi": row[2],
        "group": row[3],
    }
    for row in COUNTRIES
}

GROUP_NAMES: dict[str, str] = {g[0]: g[1] for g in GROUPS}
GROUP_NAMES_VI: dict[str, str] = {g[0]: g[2] for g in GROUPS}

SITE_CODES: frozenset[str] = frozenset(row[0] for row in COUNTRIES)

# Flags: Kosovo has no ISO-3166 flag on flagcdn, so it uses the XK asset.
FLAG_OVERRIDES: dict[str, str] = {"XK": "xk"}


def flag_url(code: str) -> str:
    """Return a small flag image URL for a country code."""
    slug = FLAG_OVERRIDES.get(code, code.lower())
    return f"{FLAG_BASE}/{slug}.png"


def flag_emoji(code: str) -> str:
    """Return the regional-indicator flag emoji for a country code."""
    code = str(code).upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code)


# Names users may type that are not the site label: old spellings, ISO-3166
# names that differ from the site label, and common short forms.
COUNTRY_ALIASES: dict[str, str] = {
    "netherland": "NL",
    "holland": "NL",
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "unitedstates": "US",
    "unitedstatesofamerica": "US",
    "america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "greatbritain": "GB",
    "england": "GB",
    "britain": "GB",
    "vietnam": "VN",
    "viet nam": "VN",
    "southkorea": "KR",
    "republicofkorea": "KR",
    "korea,republicof": "KR",
    "northkorea": "KP",
    "southafrica": "ZA",
    "czechrepublic": "CZ",
    "czechia": "CZ",
    "burma": "MM",
    "ivorycoast": "CI",
    "cotedivoire": "CI",
    "coted'ivoire": "CI",
    "capeverde": "CV",
    "easttimor": "TL",
    "turkey": "TR",
    "turkiye": "TR",
    "uae": "AE",
    "emirates": "AE",
    "saudiarabia": "SA",
    "hongkong": "HK",
    "hongkongsar": "HK",
    "macau": "MO",
    "macao": "MO",
    "russia": "RU",
    "russianfederation": "RU",
    "moldova": "MD",
    "republicofmoldova": "MD",
    "syria": "SY",
    "syrianarabrepublic": "SY",
    "laos": "LA",
    "laopdr": "LA",
    "brunei": "BN",
    "bruneidarussalam": "BN",
    "taiwan": "TW",
    "chinesetaipei": "TW",
    "palestine": "PS",
    "palestinianauthority": "PS",
    "palestinianterritories": "PS",
    "congodrc": "CD",
    "democraticrepublicofthecongo": "CD",
    "drcongo": "CD",
    "zaire": "CD",
    "congobrazzaville": "CG",
    "republicofthecongo": "CG",
    "saotomeandprincipe": "ST",
    "saotome": "ST",
    "saintkittsandnevis": "KN",
    "stkitts": "KN",
    "saintlucia": "LC",
    "stlucia": "LC",
    "saintvincentandthegrenadines": "VC",
    "stvincent": "VC",
    "trinidadandtobago": "TT",
    "antiguaandbarbuda": "AG",
    "bosniaandherzegovina": "BA",
    "sainthelena": "SH",
    "sthelena": "SH",
    "southsudan": "SS",
    "kosovo": "XK",
}

GROUP_CODE_BY_NAME: dict[str, str] = {}
for _code, _en, _vi, _members in GROUPS:
    GROUP_CODE_BY_NAME[_en.strip().lower()] = _code
    GROUP_CODE_BY_NAME[_vi.strip().lower()] = _code
    GROUP_CODE_BY_NAME[_code.lower()] = _code


class RegionError(ValueError):
    """Raised when a region selection cannot be resolved to country codes."""


def _normalize_token(raw: str) -> str:
    return " ".join(str(raw).strip().lower().replace("_", " ").split())


def normalize_country_code(value: str) -> Optional[str]:
    """Resolve any user-typed country reference to an ISO-3166 alpha-2 code.

    Accepts ``NL``, ``nl``, ``NLD``, ``Netherlands``, ``netherland`` (the old
    hardcoded default), ``Hà Lan`` or the site label. Returns ``None`` when the
    value is not a country the site offers.
    """
    token = _normalize_token(value)
    if not token:
        return None

    upper = token.upper()
    if len(upper) == 2:
        return upper if upper in COUNTRY_BY_CODE else None

    compact = token.replace(" ", "").replace(".", "").replace("-", "")
    alias = COUNTRY_ALIASES.get(token) or COUNTRY_ALIASES.get(compact)
    if alias:
        # An alias may name a territory the site does not offer (Macau, North
        # Korea); in that case it must not resolve, or we would build a query
        # the site cannot run.
        return alias if alias in COUNTRY_BY_CODE else None

    for row in COUNTRIES:
        if (
            row[1].strip().lower() == token
            or row[2].strip().lower() == token
            or row[1].strip().lower().replace(" ", "") == compact
        ):
            return row[0]
    return None


def normalize_group_code(value: str) -> Optional[str]:
    """Resolve a group name/code (America, Asia, ...) to its two-letter code."""
    token = _normalize_token(value)
    if not token:
        return None
    return GROUP_CODE_BY_NAME.get(token)


def country_label(code: str) -> str:
    """Human readable ``"Hà Lan (NL)"`` label for a country code."""
    info = COUNTRY_BY_CODE.get(code)
    if not info:
        return code
    return f"{info['name_vi']} ({code})"


def countries_in_group(group_code: str) -> list[str]:
    """Return the codes of a group, in the site's display order."""
    return [row[0] for row in COUNTRIES if row[3] == group_code]


def all_country_codes() -> list[str]:
    """Return every country code, in the site's display order."""
    return [row[0] for row in COUNTRIES]


def resolve_region_codes(
    raw_values: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Turn a mixed list of country/group selectors into ISO-2 code list.

    Accepts country names, ISO-2 codes, aliases and group names (``Asia``
    expands to every Asian country). Anything that cannot be understood is
    reported back in ``unknown`` instead of being silently replaced.

    Returns:
        ``(codes, unknown)`` — ``codes`` in the site's display order.

    Raises:
        RegionError: If nothing usable is left after normalisation.
    """
    wanted: set[str] = set()
    unknown: list[str] = []

    for raw in raw_values:
        for piece in str(raw).replace(";", ",").split(","):
            value = piece.strip()
            if not value:
                continue

            token = _normalize_token(value)
            if token in {"all", "worldwide", "world", "*"}:
                wanted.update(all_country_codes())
                continue

            group = normalize_group_code(value)
            if group:
                wanted.update(countries_in_group(group))
                continue

            code = normalize_country_code(value)
            if code is None:
                unknown.append(value)
                continue
            wanted.add(code)

    if not wanted:
        raise RegionError(
            "Không xác định được quốc gia/vùng nào từ lựa chọn của bạn"
            + (f": {', '.join(unknown[:5])}" if unknown else "")
        )

    ordered = [code for code in all_country_codes() if code in wanted]
    return ordered, unknown


def build_destination_codes(codes: Iterable[str]) -> str:
    """Build the comma-joined ``destiCountryCode`` value the API expects.

    The buyer-search request takes the importing countries as a single
    comma-separated string of ISO-2 codes (e.g. ``"US,VN"``). Order follows the
    site's display order so the same selection always builds the same request.

    Raises:
        RegionError: If no usable country code remains.
    """
    wanted: set[str] = set()
    for raw in codes:
        code = str(raw).strip().upper()
        if not code:
            continue
        if code not in COUNTRY_BY_CODE:
            raise RegionError(f"Mã quốc gia không hợp lệ: {raw}")
        wanted.add(code)

    ordered = [code for code in all_country_codes() if code in wanted]
    # Keep codes the site list does not carry (defensive) rather than dropping.
    ordered += sorted(wanted - set(ordered))

    if not ordered:
        raise RegionError("Chưa chọn quốc gia/vùng nhập hàng nào")
    return ",".join(ordered)


def parse_destination_codes(value: str) -> list[str]:
    """Split a ``destiCountryCode`` string back into ISO-2 codes."""
    return [part.strip().upper() for part in str(value or "").split(",") if part.strip()]


def validate_hs_code(value: str) -> str:
    """Normalise an HS code the way the site accepts it.

    The site keeps only digits and commas and warns when the code is shorter
    than 2 characters. Dots and spaces are removed here as a convenience.

    Raises:
        RegionError: For an empty code or fewer than 2 digits.
    """
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        raise RegionError("HS Code phải chứa chữ số (ví dụ: 090411)")
    if len(digits) < 2:
        raise RegionError("HS Code phải có ít nhất 2 chữ số (ví dụ: 09 hoặc 090411)")
    return digits
