"""Country / region catalog used to build the buyer-search filter.

Generated from ISO-3166 reference data; no runtime dependency and no
network access is required to render the picker.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

# (code, English name, Vietnamese name)
CONTINENTS: tuple[tuple[str, str, str], ...] = (
    ('AF', 'Africa', 'Châu Phi'),
    ('AS', 'Asia', 'Châu Á'),
    ('EU', 'Europe', 'Châu Âu'),
    ('NA', 'North America', 'Bắc Mỹ'),
    ('SA', 'South America', 'Nam Mỹ'),
    ('OC', 'Oceania', 'Châu Đại Dương'),
    ('AN', 'Antarctica', 'Nam Cực'),
)

CONTINENT_NAMES: dict[str, str] = {code: en for code, en, _ in CONTINENTS}
CONTINENT_NAMES_VI: dict[str, str] = {code: vi for code, _, vi in CONTINENTS}

# (code, iso3, English name, Vietnamese name, continent code, sub-region)
COUNTRIES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ('AF', 'AFG', 'Afghanistan', 'Afghanistan', 'AS', 'Southern Asia'),
    ('AL', 'ALB', 'Albania', 'Albania', 'EU', 'Southeast Europe'),
    ('DZ', 'DZA', 'Algeria', 'Algeria', 'AF', 'Northern Africa'),
    ('AS', 'ASM', 'American Samoa', 'American Samoa', 'OC', 'Polynesia'),
    ('AD', 'AND', 'Andorra', 'Andorra', 'EU', 'Southern Europe'),
    ('AO', 'AGO', 'Angola', 'Angola', 'AF', 'Middle Africa'),
    ('AI', 'AIA', 'Anguilla', 'Anguilla', 'NA', 'Caribbean'),
    ('AQ', 'ATA', 'Antarctica', 'Antarctica', 'AN', ''),
    ('AG', 'ATG', 'Antigua and Barbuda', 'Antigua and Barbuda', 'NA', 'Caribbean'),
    ('AR', 'ARG', 'Argentina', 'Argentina', 'SA', 'South America'),
    ('AM', 'ARM', 'Armenia', 'Armenia', 'AS', 'Western Asia'),
    ('AW', 'ABW', 'Aruba', 'Aruba', 'NA', 'Caribbean'),
    ('AU', 'AUS', 'Australia', 'Úc', 'OC', 'Australia and New Zealand'),
    ('AT', 'AUT', 'Austria', 'Áo', 'EU', 'Central Europe'),
    ('AZ', 'AZE', 'Azerbaijan', 'Azerbaijan', 'AS', 'Western Asia'),
    ('BS', 'BHS', 'Bahamas', 'Bahamas', 'NA', 'Caribbean'),
    ('BH', 'BHR', 'Bahrain', 'Bahrain', 'AS', 'Western Asia'),
    ('BD', 'BGD', 'Bangladesh', 'Bangladesh', 'AS', 'Southern Asia'),
    ('BB', 'BRB', 'Barbados', 'Barbados', 'NA', 'Caribbean'),
    ('BY', 'BLR', 'Belarus', 'Belarus', 'EU', 'Eastern Europe'),
    ('BE', 'BEL', 'Belgium', 'Bỉ', 'EU', 'Western Europe'),
    ('BZ', 'BLZ', 'Belize', 'Belize', 'NA', 'Central America'),
    ('BJ', 'BEN', 'Benin', 'Benin', 'AF', 'Western Africa'),
    ('BM', 'BMU', 'Bermuda', 'Bermuda', 'NA', 'North America'),
    ('BT', 'BTN', 'Bhutan', 'Bhutan', 'AS', 'Southern Asia'),
    ('BO', 'BOL', 'Bolivia', 'Bolivia', 'SA', 'South America'),
    ('BA', 'BIH', 'Bosnia and Herzegovina', 'Bosnia và Herzegovina', 'EU', 'Southeast Europe'),
    ('BW', 'BWA', 'Botswana', 'Botswana', 'AF', 'Southern Africa'),
    ('BV', 'BVT', 'Bouvet Island', 'Bouvet Island', 'AN', ''),
    ('BR', 'BRA', 'Brazil', 'Brazil', 'SA', 'South America'),
    ('IO', 'IOT', 'British Indian Ocean Territory', 'British Indian Ocean Territory', 'AF', 'Eastern Africa'),
    ('VG', 'VGB', 'British Virgin Islands', 'British Virgin Islands', 'NA', 'Caribbean'),
    ('BN', 'BRN', 'Brunei', 'Brunei', 'AS', 'South-Eastern Asia'),
    ('BG', 'BGR', 'Bulgaria', 'Bulgaria', 'EU', 'Southeast Europe'),
    ('BF', 'BFA', 'Burkina Faso', 'Burkina Faso', 'AF', 'Western Africa'),
    ('BI', 'BDI', 'Burundi', 'Burundi', 'AF', 'Eastern Africa'),
    ('KH', 'KHM', 'Cambodia', 'Campuchia', 'AS', 'South-Eastern Asia'),
    ('CM', 'CMR', 'Cameroon', 'Cameroon', 'AF', 'Middle Africa'),
    ('CA', 'CAN', 'Canada', 'Canada', 'NA', 'North America'),
    ('CV', 'CPV', 'Cape Verde', 'Cape Verde', 'AF', 'Western Africa'),
    ('BQ', 'BES', 'Caribbean Netherlands', 'Caribbean Netherlands', 'NA', 'Caribbean'),
    ('KY', 'CYM', 'Cayman Islands', 'Cayman Islands', 'NA', 'Caribbean'),
    ('CF', 'CAF', 'Central African Republic', 'Central African Republic', 'AF', 'Middle Africa'),
    ('TD', 'TCD', 'Chad', 'Chad', 'AF', 'Middle Africa'),
    ('CL', 'CHL', 'Chile', 'Chile', 'SA', 'South America'),
    ('CN', 'CHN', 'China', 'Trung Quốc', 'AS', 'Eastern Asia'),
    ('CX', 'CXR', 'Christmas Island', 'Christmas Island', 'OC', 'Australia and New Zealand'),
    ('CC', 'CCK', 'Cocos (Keeling) Islands', 'Cocos (Keeling) Islands', 'OC', 'Australia and New Zealand'),
    ('CO', 'COL', 'Colombia', 'Colombia', 'SA', 'South America'),
    ('KM', 'COM', 'Comoros', 'Comoros', 'AF', 'Eastern Africa'),
    ('CG', 'COG', 'Congo', 'Congo', 'AF', 'Middle Africa'),
    ('CK', 'COK', 'Cook Islands', 'Cook Islands', 'OC', 'Polynesia'),
    ('CR', 'CRI', 'Costa Rica', 'Costa Rica', 'NA', 'Central America'),
    ('HR', 'HRV', 'Croatia', 'Croatia', 'EU', 'Southeast Europe'),
    ('CU', 'CUB', 'Cuba', 'Cuba', 'NA', 'Caribbean'),
    ('CW', 'CUW', 'Curaçao', 'Curaçao', 'NA', 'Caribbean'),
    ('CY', 'CYP', 'Cyprus', 'Cyprus', 'EU', 'Southern Europe'),
    ('CZ', 'CZE', 'Czechia', 'Séc', 'EU', 'Central Europe'),
    ('CD', 'COD', 'DR Congo', 'DR Congo', 'AF', 'Middle Africa'),
    ('DK', 'DNK', 'Denmark', 'Đan Mạch', 'EU', 'Northern Europe'),
    ('DJ', 'DJI', 'Djibouti', 'Djibouti', 'AF', 'Eastern Africa'),
    ('DM', 'DMA', 'Dominica', 'Dominica', 'NA', 'Caribbean'),
    ('DO', 'DOM', 'Dominican Republic', 'Dominican Republic', 'NA', 'Caribbean'),
    ('EC', 'ECU', 'Ecuador', 'Ecuador', 'SA', 'South America'),
    ('EG', 'EGY', 'Egypt', 'Ai Cập', 'AF', 'Northern Africa'),
    ('SV', 'SLV', 'El Salvador', 'El Salvador', 'NA', 'Central America'),
    ('GQ', 'GNQ', 'Equatorial Guinea', 'Equatorial Guinea', 'AF', 'Middle Africa'),
    ('ER', 'ERI', 'Eritrea', 'Eritrea', 'AF', 'Eastern Africa'),
    ('EE', 'EST', 'Estonia', 'Estonia', 'EU', 'Northern Europe'),
    ('SZ', 'SWZ', 'Eswatini', 'Eswatini', 'AF', 'Southern Africa'),
    ('ET', 'ETH', 'Ethiopia', 'Ethiopia', 'AF', 'Eastern Africa'),
    ('FK', 'FLK', 'Falkland Islands', 'Falkland Islands', 'SA', 'South America'),
    ('FO', 'FRO', 'Faroe Islands', 'Faroe Islands', 'EU', 'Northern Europe'),
    ('FJ', 'FJI', 'Fiji', 'Fiji', 'OC', 'Melanesia'),
    ('FI', 'FIN', 'Finland', 'Phần Lan', 'EU', 'Northern Europe'),
    ('FR', 'FRA', 'France', 'Pháp', 'EU', 'Western Europe'),
    ('GF', 'GUF', 'French Guiana', 'French Guiana', 'SA', 'South America'),
    ('PF', 'PYF', 'French Polynesia', 'French Polynesia', 'OC', 'Polynesia'),
    ('TF', 'ATF', 'French Southern and Antarctic Lands', 'French Southern and Antarctic Lands', 'AN', ''),
    ('GA', 'GAB', 'Gabon', 'Gabon', 'AF', 'Middle Africa'),
    ('GM', 'GMB', 'Gambia', 'Gambia', 'AF', 'Western Africa'),
    ('GE', 'GEO', 'Georgia', 'Gruzia', 'AS', 'Western Asia'),
    ('DE', 'DEU', 'Germany', 'Đức', 'EU', 'Western Europe'),
    ('GH', 'GHA', 'Ghana', 'Ghana', 'AF', 'Western Africa'),
    ('GI', 'GIB', 'Gibraltar', 'Gibraltar', 'EU', 'Southern Europe'),
    ('GR', 'GRC', 'Greece', 'Hy Lạp', 'EU', 'Southern Europe'),
    ('GL', 'GRL', 'Greenland', 'Greenland', 'NA', 'North America'),
    ('GD', 'GRD', 'Grenada', 'Grenada', 'NA', 'Caribbean'),
    ('GP', 'GLP', 'Guadeloupe', 'Guadeloupe', 'NA', 'Caribbean'),
    ('GU', 'GUM', 'Guam', 'Guam', 'OC', 'Micronesia'),
    ('GT', 'GTM', 'Guatemala', 'Guatemala', 'NA', 'Central America'),
    ('GG', 'GGY', 'Guernsey', 'Guernsey', 'EU', 'Northern Europe'),
    ('GN', 'GIN', 'Guinea', 'Guinea', 'AF', 'Western Africa'),
    ('GW', 'GNB', 'Guinea-Bissau', 'Guinea-Bissau', 'AF', 'Western Africa'),
    ('GY', 'GUY', 'Guyana', 'Guyana', 'SA', 'South America'),
    ('HT', 'HTI', 'Haiti', 'Haiti', 'NA', 'Caribbean'),
    ('HM', 'HMD', 'Heard Island and McDonald Islands', 'Heard Island and McDonald Islands', 'AN', ''),
    ('HN', 'HND', 'Honduras', 'Honduras', 'NA', 'Central America'),
    ('HK', 'HKG', 'Hong Kong', 'Hồng Kông', 'AS', 'Eastern Asia'),
    ('HU', 'HUN', 'Hungary', 'Hungary', 'EU', 'Central Europe'),
    ('IS', 'ISL', 'Iceland', 'Iceland', 'EU', 'Northern Europe'),
    ('IN', 'IND', 'India', 'Ấn Độ', 'AS', 'Southern Asia'),
    ('ID', 'IDN', 'Indonesia', 'Indonesia', 'AS', 'South-Eastern Asia'),
    ('IR', 'IRN', 'Iran', 'Iran', 'AS', 'Southern Asia'),
    ('IQ', 'IRQ', 'Iraq', 'Iraq', 'AS', 'Western Asia'),
    ('IE', 'IRL', 'Ireland', 'Ireland', 'EU', 'Northern Europe'),
    ('IM', 'IMN', 'Isle of Man', 'Isle of Man', 'EU', 'Northern Europe'),
    ('IL', 'ISR', 'Israel', 'Israel', 'AS', 'Western Asia'),
    ('IT', 'ITA', 'Italy', 'Ý', 'EU', 'Southern Europe'),
    ('CI', 'CIV', 'Ivory Coast', 'Bờ Biển Ngà', 'AF', 'Western Africa'),
    ('JM', 'JAM', 'Jamaica', 'Jamaica', 'NA', 'Caribbean'),
    ('JP', 'JPN', 'Japan', 'Nhật Bản', 'AS', 'Eastern Asia'),
    ('JE', 'JEY', 'Jersey', 'Jersey', 'EU', 'Northern Europe'),
    ('JO', 'JOR', 'Jordan', 'Jordan', 'AS', 'Western Asia'),
    ('KZ', 'KAZ', 'Kazakhstan', 'Kazakhstan', 'AS', 'Central Asia'),
    ('KE', 'KEN', 'Kenya', 'Kenya', 'AF', 'Eastern Africa'),
    ('KI', 'KIR', 'Kiribati', 'Kiribati', 'OC', 'Micronesia'),
    ('KW', 'KWT', 'Kuwait', 'Kuwait', 'AS', 'Western Asia'),
    ('KG', 'KGZ', 'Kyrgyzstan', 'Kyrgyzstan', 'AS', 'Central Asia'),
    ('LA', 'LAO', 'Laos', 'Lào', 'AS', 'South-Eastern Asia'),
    ('LV', 'LVA', 'Latvia', 'Latvia', 'EU', 'Northern Europe'),
    ('LB', 'LBN', 'Lebanon', 'Liban', 'AS', 'Western Asia'),
    ('LS', 'LSO', 'Lesotho', 'Lesotho', 'AF', 'Southern Africa'),
    ('LR', 'LBR', 'Liberia', 'Liberia', 'AF', 'Western Africa'),
    ('LY', 'LBY', 'Libya', 'Libya', 'AF', 'Northern Africa'),
    ('LI', 'LIE', 'Liechtenstein', 'Liechtenstein', 'EU', 'Western Europe'),
    ('LT', 'LTU', 'Lithuania', 'Litva', 'EU', 'Northern Europe'),
    ('LU', 'LUX', 'Luxembourg', 'Luxembourg', 'EU', 'Western Europe'),
    ('MO', 'MAC', 'Macau', 'Ma Cao', 'AS', 'Eastern Asia'),
    ('MG', 'MDG', 'Madagascar', 'Madagascar', 'AF', 'Eastern Africa'),
    ('MW', 'MWI', 'Malawi', 'Malawi', 'AF', 'Eastern Africa'),
    ('MY', 'MYS', 'Malaysia', 'Malaysia', 'AS', 'South-Eastern Asia'),
    ('MV', 'MDV', 'Maldives', 'Maldives', 'AS', 'Southern Asia'),
    ('ML', 'MLI', 'Mali', 'Mali', 'AF', 'Western Africa'),
    ('MT', 'MLT', 'Malta', 'Malta', 'EU', 'Southern Europe'),
    ('MH', 'MHL', 'Marshall Islands', 'Marshall Islands', 'OC', 'Micronesia'),
    ('MQ', 'MTQ', 'Martinique', 'Martinique', 'NA', 'Caribbean'),
    ('MR', 'MRT', 'Mauritania', 'Mauritania', 'AF', 'Western Africa'),
    ('MU', 'MUS', 'Mauritius', 'Mauritius', 'AF', 'Eastern Africa'),
    ('YT', 'MYT', 'Mayotte', 'Mayotte', 'AF', 'Eastern Africa'),
    ('MX', 'MEX', 'Mexico', 'Mexico', 'NA', 'North America'),
    ('FM', 'FSM', 'Micronesia', 'Micronesia', 'OC', 'Micronesia'),
    ('MD', 'MDA', 'Moldova', 'Moldova', 'EU', 'Eastern Europe'),
    ('MC', 'MCO', 'Monaco', 'Monaco', 'EU', 'Western Europe'),
    ('MN', 'MNG', 'Mongolia', 'Mông Cổ', 'AS', 'Eastern Asia'),
    ('ME', 'MNE', 'Montenegro', 'Montenegro', 'EU', 'Southeast Europe'),
    ('MS', 'MSR', 'Montserrat', 'Montserrat', 'NA', 'Caribbean'),
    ('MA', 'MAR', 'Morocco', 'Maroc', 'AF', 'Northern Africa'),
    ('MZ', 'MOZ', 'Mozambique', 'Mozambique', 'AF', 'Eastern Africa'),
    ('MM', 'MMR', 'Myanmar', 'Myanmar', 'AS', 'South-Eastern Asia'),
    ('NA', 'NAM', 'Namibia', 'Namibia', 'AF', 'Southern Africa'),
    ('NR', 'NRU', 'Nauru', 'Nauru', 'OC', 'Micronesia'),
    ('NP', 'NPL', 'Nepal', 'Nepal', 'AS', 'Southern Asia'),
    ('NL', 'NLD', 'Netherlands', 'Hà Lan', 'EU', 'Western Europe'),
    ('NC', 'NCL', 'New Caledonia', 'New Caledonia', 'OC', 'Melanesia'),
    ('NZ', 'NZL', 'New Zealand', 'New Zealand', 'OC', 'Australia and New Zealand'),
    ('NI', 'NIC', 'Nicaragua', 'Nicaragua', 'NA', 'Central America'),
    ('NE', 'NER', 'Niger', 'Niger', 'AF', 'Western Africa'),
    ('NG', 'NGA', 'Nigeria', 'Nigeria', 'AF', 'Western Africa'),
    ('NU', 'NIU', 'Niue', 'Niue', 'OC', 'Polynesia'),
    ('NF', 'NFK', 'Norfolk Island', 'Norfolk Island', 'OC', 'Australia and New Zealand'),
    ('KP', 'PRK', 'North Korea', 'North Korea', 'AS', 'Eastern Asia'),
    ('MK', 'MKD', 'North Macedonia', 'Bắc Macedonia', 'EU', 'Southeast Europe'),
    ('MP', 'MNP', 'Northern Mariana Islands', 'Northern Mariana Islands', 'OC', 'Micronesia'),
    ('NO', 'NOR', 'Norway', 'Na Uy', 'EU', 'Northern Europe'),
    ('OM', 'OMN', 'Oman', 'Oman', 'AS', 'Western Asia'),
    ('PK', 'PAK', 'Pakistan', 'Pakistan', 'AS', 'Southern Asia'),
    ('PW', 'PLW', 'Palau', 'Palau', 'OC', 'Micronesia'),
    ('PS', 'PSE', 'Palestine', 'Palestine', 'AS', 'Western Asia'),
    ('PA', 'PAN', 'Panama', 'Panama', 'NA', 'Central America'),
    ('PG', 'PNG', 'Papua New Guinea', 'Papua New Guinea', 'OC', 'Melanesia'),
    ('PY', 'PRY', 'Paraguay', 'Paraguay', 'SA', 'South America'),
    ('PE', 'PER', 'Peru', 'Peru', 'SA', 'South America'),
    ('PH', 'PHL', 'Philippines', 'Philippines', 'AS', 'South-Eastern Asia'),
    ('PN', 'PCN', 'Pitcairn Islands', 'Pitcairn Islands', 'OC', 'Polynesia'),
    ('PL', 'POL', 'Poland', 'Ba Lan', 'EU', 'Central Europe'),
    ('PT', 'PRT', 'Portugal', 'Bồ Đào Nha', 'EU', 'Southern Europe'),
    ('PR', 'PRI', 'Puerto Rico', 'Puerto Rico', 'NA', 'Caribbean'),
    ('QA', 'QAT', 'Qatar', 'Qatar', 'AS', 'Western Asia'),
    ('RO', 'ROU', 'Romania', 'Romania', 'EU', 'Southeast Europe'),
    ('RU', 'RUS', 'Russia', 'Nga', 'EU', 'Eastern Europe'),
    ('RW', 'RWA', 'Rwanda', 'Rwanda', 'AF', 'Eastern Africa'),
    ('RE', 'REU', 'Réunion', 'Réunion', 'AF', 'Eastern Africa'),
    ('BL', 'BLM', 'Saint Barthélemy', 'Saint Barthélemy', 'NA', 'Caribbean'),
    ('SH', 'SHN', 'Saint Helena, Ascension and Tristan da Cunha', 'Saint Helena, Ascension and Tristan da Cunha', 'AF', 'Western Africa'),
    ('KN', 'KNA', 'Saint Kitts and Nevis', 'Saint Kitts and Nevis', 'NA', 'Caribbean'),
    ('LC', 'LCA', 'Saint Lucia', 'Saint Lucia', 'NA', 'Caribbean'),
    ('MF', 'MAF', 'Saint Martin', 'Saint Martin', 'NA', 'Caribbean'),
    ('PM', 'SPM', 'Saint Pierre and Miquelon', 'Saint Pierre and Miquelon', 'NA', 'North America'),
    ('VC', 'VCT', 'Saint Vincent and the Grenadines', 'Saint Vincent and the Grenadines', 'NA', 'Caribbean'),
    ('WS', 'WSM', 'Samoa', 'Samoa', 'OC', 'Polynesia'),
    ('SM', 'SMR', 'San Marino', 'San Marino', 'EU', 'Southern Europe'),
    ('SA', 'SAU', 'Saudi Arabia', 'Ả Rập Xê Út', 'AS', 'Western Asia'),
    ('SN', 'SEN', 'Senegal', 'Senegal', 'AF', 'Western Africa'),
    ('RS', 'SRB', 'Serbia', 'Serbia', 'EU', 'Southeast Europe'),
    ('SC', 'SYC', 'Seychelles', 'Seychelles', 'AF', 'Eastern Africa'),
    ('SL', 'SLE', 'Sierra Leone', 'Sierra Leone', 'AF', 'Western Africa'),
    ('SG', 'SGP', 'Singapore', 'Singapore', 'AS', 'South-Eastern Asia'),
    ('SX', 'SXM', 'Sint Maarten', 'Sint Maarten', 'NA', 'Caribbean'),
    ('SK', 'SVK', 'Slovakia', 'Slovakia', 'EU', 'Central Europe'),
    ('SI', 'SVN', 'Slovenia', 'Slovenia', 'EU', 'Central Europe'),
    ('SB', 'SLB', 'Solomon Islands', 'Solomon Islands', 'OC', 'Melanesia'),
    ('SO', 'SOM', 'Somalia', 'Somalia', 'AF', 'Eastern Africa'),
    ('ZA', 'ZAF', 'South Africa', 'Nam Phi', 'AF', 'Southern Africa'),
    ('GS', 'SGS', 'South Georgia', 'South Georgia', 'AN', ''),
    ('KR', 'KOR', 'South Korea', 'Hàn Quốc', 'AS', 'Eastern Asia'),
    ('SS', 'SSD', 'South Sudan', 'South Sudan', 'AF', 'Middle Africa'),
    ('ES', 'ESP', 'Spain', 'Tây Ban Nha', 'EU', 'Southern Europe'),
    ('LK', 'LKA', 'Sri Lanka', 'Sri Lanka', 'AS', 'Southern Asia'),
    ('SD', 'SDN', 'Sudan', 'Sudan', 'AF', 'Northern Africa'),
    ('SR', 'SUR', 'Suriname', 'Suriname', 'SA', 'South America'),
    ('SJ', 'SJM', 'Svalbard and Jan Mayen', 'Svalbard and Jan Mayen', 'EU', 'Northern Europe'),
    ('SE', 'SWE', 'Sweden', 'Thụy Điển', 'EU', 'Northern Europe'),
    ('CH', 'CHE', 'Switzerland', 'Thụy Sĩ', 'EU', 'Western Europe'),
    ('SY', 'SYR', 'Syria', 'Syria', 'AS', 'Western Asia'),
    ('ST', 'STP', 'São Tomé and Príncipe', 'São Tomé and Príncipe', 'AF', 'Middle Africa'),
    ('TW', 'TWN', 'Taiwan', 'Đài Loan', 'AS', 'Eastern Asia'),
    ('TJ', 'TJK', 'Tajikistan', 'Tajikistan', 'AS', 'Central Asia'),
    ('TZ', 'TZA', 'Tanzania', 'Tanzania', 'AF', 'Eastern Africa'),
    ('TH', 'THA', 'Thailand', 'Thái Lan', 'AS', 'South-Eastern Asia'),
    ('TL', 'TLS', 'Timor-Leste', 'Timor-Leste', 'AS', 'South-Eastern Asia'),
    ('TG', 'TGO', 'Togo', 'Togo', 'AF', 'Western Africa'),
    ('TK', 'TKL', 'Tokelau', 'Tokelau', 'OC', 'Polynesia'),
    ('TO', 'TON', 'Tonga', 'Tonga', 'OC', 'Polynesia'),
    ('TT', 'TTO', 'Trinidad and Tobago', 'Trinidad và Tobago', 'NA', 'Caribbean'),
    ('TN', 'TUN', 'Tunisia', 'Tunisia', 'AF', 'Northern Africa'),
    ('TM', 'TKM', 'Turkmenistan', 'Turkmenistan', 'AS', 'Central Asia'),
    ('TC', 'TCA', 'Turks and Caicos Islands', 'Turks and Caicos Islands', 'NA', 'Caribbean'),
    ('TV', 'TUV', 'Tuvalu', 'Tuvalu', 'OC', 'Polynesia'),
    ('TR', 'TUR', 'Türkiye', 'Thổ Nhĩ Kỳ', 'AS', 'Western Asia'),
    ('UG', 'UGA', 'Uganda', 'Uganda', 'AF', 'Eastern Africa'),
    ('UA', 'UKR', 'Ukraine', 'Ukraine', 'EU', 'Eastern Europe'),
    ('AE', 'ARE', 'United Arab Emirates', 'UAE', 'AS', 'Western Asia'),
    ('GB', 'GBR', 'United Kingdom', 'Anh', 'EU', 'Northern Europe'),
    ('US', 'USA', 'United States', 'Hoa Kỳ', 'NA', 'North America'),
    ('UM', 'UMI', 'United States Minor Outlying Islands', 'United States Minor Outlying Islands', 'NA', 'North America'),
    ('VI', 'VIR', 'United States Virgin Islands', 'United States Virgin Islands', 'NA', 'Caribbean'),
    ('UY', 'URY', 'Uruguay', 'Uruguay', 'SA', 'South America'),
    ('UZ', 'UZB', 'Uzbekistan', 'Uzbekistan', 'AS', 'Central Asia'),
    ('VU', 'VUT', 'Vanuatu', 'Vanuatu', 'OC', 'Melanesia'),
    ('VA', 'VAT', 'Vatican City', 'Vatican City', 'EU', 'Southern Europe'),
    ('VE', 'VEN', 'Venezuela', 'Venezuela', 'SA', 'South America'),
    ('VN', 'VNM', 'Vietnam', 'Việt Nam', 'AS', 'South-Eastern Asia'),
    ('WF', 'WLF', 'Wallis and Futuna', 'Wallis and Futuna', 'OC', 'Polynesia'),
    ('EH', 'ESH', 'Western Sahara', 'Western Sahara', 'AF', 'Northern Africa'),
    ('YE', 'YEM', 'Yemen', 'Yemen', 'AS', 'Western Asia'),
    ('ZM', 'ZMB', 'Zambia', 'Zambia', 'AF', 'Eastern Africa'),
    ('ZW', 'ZWE', 'Zimbabwe', 'Zimbabwe', 'AF', 'Eastern Africa'),
    ('AX', 'ALA', 'Åland Islands', 'Åland Islands', 'EU', 'Northern Europe'),
)

COUNTRY_BY_CODE: dict[str, dict[str, str]] = {
    row[0]: {
        "code": row[0],
        "iso3": row[1],
        "name": row[2],
        "name_vi": row[3],
        "continent": row[4],
        "region": row[5],
    }
    for row in COUNTRIES
}

# Aliases the TradeIt site (and users) may type instead of the ISO-2 code.
COUNTRY_ALIASES: dict[str, str] = {
    "netherland": "NL",
    "netherlands": "NL",
    "holland": "NL",
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "unitedstates": "US",
    "america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "greatbritain": "GB",
    "england": "GB",
    "britain": "GB",
    "vietnam": "VN",
    "viet nam": "VN",
    "korea": "KR",
    "southkorea": "KR",
    "republicofkorea": "KR",
    "china": "CN",
    "prc": "CN",
    "russia": "RU",
    "czechia": "CZ",
    "czechrepublic": "CZ",
    "türkiye": "TR",
    "turkiye": "TR",
    "turkey": "TR",
    "uae": "AE",
    "emirates": "AE",
    "saudiarabia": "SA",
    "ivorycoast": "CI",
    "cotedivoire": "CI",
    "coted'ivoire": "CI",
}

CONTINENT_CODE_BY_NAME: dict[str, str] = {}
for _code, _en, _vi in CONTINENTS:
    CONTINENT_CODE_BY_NAME[_en.strip().lower()] = _code
    CONTINENT_CODE_BY_NAME[_vi.strip().lower()] = _code
    CONTINENT_CODE_BY_NAME[_code.lower()] = _code


class RegionError(ValueError):
    """Raised when a region selection cannot be resolved to country codes."""


def _normalize_token(raw: str) -> str:
    return " ".join(str(raw).strip().lower().replace("_", " ").split())


def normalize_country_code(value: str) -> Optional[str]:
    """Resolve any user-typed country reference to an ISO-3166 alpha-2 code.

    Accepts ``NL``, ``nl``, ``NLD``, ``Netherlands``, ``netherland`` (the old
    hardcoded default) or ``Hà Lan``. Returns ``None`` when unrecognised.
    """
    token = _normalize_token(value)
    if not token:
        return None

    upper = token.upper()
    if len(upper) == 2 and upper in COUNTRY_BY_CODE:
        return upper
    if len(upper) == 3:
        for row in COUNTRIES:
            if row[1] == upper:
                return row[0]

    compact = token.replace(" ", "").replace(".", "").replace("-", "")
    alias = COUNTRY_ALIASES.get(token) or COUNTRY_ALIASES.get(compact)
    if alias:
        return alias

    for row in COUNTRIES:
        if (
            row[2].strip().lower() == token
            or row[3].strip().lower() == token
            or row[2].strip().lower().replace(" ", "") == compact
        ):
            return row[0]
    return None


def normalize_continent_code(value: str) -> Optional[str]:
    """Resolve a continent name/code to its two-letter continent code."""
    token = _normalize_token(value)
    if not token:
        return None
    return CONTINENT_CODE_BY_NAME.get(token)


def country_label(code: str) -> str:
    """Human readable ``"Hà Lan (NL)"`` label for a country code."""
    info = COUNTRY_BY_CODE.get(code)
    if not info:
        return code
    name = info["name_vi"] if info["name_vi"] != info["name"] else info["name"]
    if name == info["name"]:
        return f"{name} ({code})"
    return f"{name} ({code})"


def countries_in_continent(continent_code: str) -> list[str]:
    """Return the country codes that belong to a continent, sorted by name."""
    return [
        row[0]
        for row in sorted(COUNTRIES, key=lambda item: item[2])
        if row[4] == continent_code
    ]


def resolve_region_codes(
    raw_values: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Turn a mixed list of country/continent selectors into ISO-2 code list.

    Accepts country names, ISO-2/ISO-3 codes, ``netherland`` style aliases and
    continent names (``Asia`` expands to every Asian country). Anything that
    cannot be understood is reported back in ``unknown`` instead of being
    silently replaced by a default country.

    Returns:
        ``(codes, unknown)`` — ``codes`` sorted and de-duplicated.

    Raises:
        RegionError: If nothing usable is left after normalisation.
    """
    codes: list[str] = []
    seen: set[str] = set()
    unknown: list[str] = []

    def _add(code: str) -> None:
        if code not in seen:
            seen.add(code)
            codes.append(code)

    for raw in raw_values:
        for piece in str(raw).replace(";", ",").split(","):
            value = piece.strip()
            if not value:
                continue

            token = _normalize_token(value)
            if token in {"all", "worldwide", "world", "*"}:
                for code in countries_in_continent_all():
                    _add(code)
                continue

            continent = normalize_continent_code(value)
            if continent:
                for code in countries_in_continent(continent):
                    _add(code)
                continue

            code = normalize_country_code(value)
            if code is None:
                unknown.append(value)
                continue
            _add(code)

    if not codes:
        raise RegionError(
            "Không xác định được quốc gia/vùng nào từ lựa chọn của bạn"
            + (f": {', '.join(unknown[:5])}" if unknown else "")
        )

    return sorted(set(codes)), unknown


def countries_in_continent_all() -> list[str]:
    """Return every known country code, sorted by country name."""
    return [row[0] for row in sorted(COUNTRIES, key=lambda item: item[2])]


def build_destination_codes(codes: Iterable[str]) -> str:
    """Build the comma-joined ``destiCountryCode`` value the API expects.

    The buyer-search request takes the importing countries as a single
    comma-separated string of ISO-2 codes (e.g. ``"US,VN"``), not as an array
    of objects. Order is preserved so the same user selection always produces
    the same request.

    Raises:
        RegionError: If no usable country code remains.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        code = str(raw).strip().upper()
        if not code or code in seen:
            continue
        if code not in COUNTRY_BY_CODE:
            raise RegionError(f"Mã quốc gia không hợp lệ: {raw}")
        seen.add(code)
        ordered.append(code)

    if not ordered:
        raise RegionError("Chưa chọn quốc gia/vùng nhập hàng nào")
    return ",".join(ordered)


def parse_destination_codes(value: str) -> list[str]:
    """Split a ``destiCountryCode`` string back into ISO-2 codes."""
    return [part.strip().upper() for part in str(value or "").split(",") if part.strip()]


def validate_hs_code(value: str) -> str:
    """Normalise an HS code the way the site accepts it.

    The site strips everything except digits and commas, and rejects a single
    character (its own form warns below 2 characters). Dots and spaces are
    removed here as a convenience.

    Raises:
        RegionError: For an empty code or fewer than 2 digits.
    """
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        raise RegionError("HS Code phải chứa chữ số (ví dụ: 090411)")
    if len(digits) < 2:
        raise RegionError("HS Code phải có ít nhất 2 chữ số (ví dụ: 09 hoặc 090411)")
    return digits

