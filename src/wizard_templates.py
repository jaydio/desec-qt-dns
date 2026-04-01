"""
DNS Record Wizard Template Data Module

Each template is a dict with:
  id          - unique string identifier
  name        - human-readable name
  description - short description shown in the wizard
  category    - one of the strings in CATEGORIES
  variables   - dict of {var_name: {label, hint, default, required}}
                Reserved variables handled automatically by the wizard
                and must NOT appear here: {domain}, {subdomain_prefix}
  records     - list of {type, subname, ttl, content}
                subname is relative (e.g. "" for apex, "www" for www.domain.tld)
                content may contain {var_name}, {domain}, {subdomain_prefix}

TTL values follow common conventions (300 = 5 min, 3600 = 1 hr, 86400 = 1 day).
MX/SRV content includes priority as first token per RFC.
CNAME/MX/NS targets must have a trailing dot.
TXT content must be wrapped in escaped double-quotes.
"""

CATEGORIES = [
    "Email",
    "Chat/Social",
    "Web",
    "Security",
    "ACME/Certificates",
    "Verification",
]

TEMPLATES = [
    # -------------------------------------------------------------------------
    # Email (5)
    # -------------------------------------------------------------------------
    {
        "id": "google_workspace",
        "name": "Google Workspace",
        "description": "MX records, SPF, DMARC, and DKIM CNAME for Google Workspace (G Suite).",
        "category": "Email",
        "variables": {
            "dkim_selector": {
                "label": "DKIM Selector",
                "hint": "The DKIM selector provided by Google (e.g. google)",
                "default": "google",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "1 aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "5 alt1.aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "5 alt2.aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 alt3.aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 alt4.aspmx.l.google.com."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:_spf.google.com ~all\"",
            },
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=none; rua=mailto:dmarc-reports@{domain}\"",
            },
            {
                "type": "CNAME",
                "subname": "{dkim_selector}._domainkey",
                "ttl": 3600,
                "content": "{dkim_selector}._domainkey.{domain}.googlehosted.com.",
            },
        ],
    },
    {
        "id": "microsoft_365",
        "name": "Microsoft 365",
        "description": "MX record, SPF, Autodiscover CNAME, and DMARC for Microsoft 365.",
        "category": "Email",
        "variables": {},
        "records": [
            {
                "type": "MX",
                "subname": "",
                "ttl": 3600,
                "content": "0 {domain}.mail.protection.outlook.com.",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.protection.outlook.com -all\"",
            },
            {
                "type": "CNAME",
                "subname": "autodiscover",
                "ttl": 3600,
                "content": "autodiscover.outlook.com.",
            },
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=none; rua=mailto:dmarc-reports@{domain}\"",
            },
        ],
    },
    {
        "id": "fastmail",
        "name": "Fastmail",
        "description": "MX records, SPF, DKIM CNAMEs, and DMARC for Fastmail.",
        "category": "Email",
        "variables": {},
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 in1-smtp.messagingengine.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "20 in2-smtp.messagingengine.com."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.messagingengine.com ~all\"",
            },
            {
                "type": "CNAME",
                "subname": "fm1._domainkey",
                "ttl": 3600,
                "content": "fm1.{domain}.dkim.fmhosted.com.",
            },
            {
                "type": "CNAME",
                "subname": "fm2._domainkey",
                "ttl": 3600,
                "content": "fm2.{domain}.dkim.fmhosted.com.",
            },
            {
                "type": "CNAME",
                "subname": "fm3._domainkey",
                "ttl": 3600,
                "content": "fm3.{domain}.dkim.fmhosted.com.",
            },
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=none; rua=mailto:dmarc-reports@{domain}\"",
            },
        ],
    },
    {
        "id": "proton_mail",
        "name": "Proton Mail",
        "description": "MX records, SPF, domain verification TXT, DKIM CNAMEs, and DMARC for Proton Mail.",
        "category": "Email",
        "variables": {
            "proton_verify": {
                "label": "Proton Mail Verification Code",
                "hint": "The TXT verification value from the Proton Mail admin panel",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 mail.protonmail.ch."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "20 mailsec.protonmail.ch."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:_spf.protonmail.ch ~all\"",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{proton_verify}\"",
            },
            {
                "type": "CNAME",
                "subname": "protonmail._domainkey",
                "ttl": 3600,
                "content": "protonmail.domainkey.{domain}.domains.proton.ch.",
            },
            {
                "type": "CNAME",
                "subname": "protonmail2._domainkey",
                "ttl": 3600,
                "content": "protonmail2.domainkey.{domain}.domains.proton.ch.",
            },
            {
                "type": "CNAME",
                "subname": "protonmail3._domainkey",
                "ttl": 3600,
                "content": "protonmail3.domainkey.{domain}.domains.proton.ch.",
            },
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=none; rua=mailto:dmarc-reports@{domain}\"",
            },
        ],
    },
    {
        "id": "basic_mx_spf_dmarc",
        "name": "Basic MX + SPF + DMARC",
        "description": "Generic MX record with SPF and DMARC for any mail server.",
        "category": "Email",
        "variables": {
            "mail_server": {
                "label": "Mail Server Hostname",
                "hint": "Fully-qualified hostname of your mail server (e.g. mail.example.com.)",
                "default": "",
                "required": True,
            },
            "mx_priority": {
                "label": "MX Priority",
                "hint": "Lower number = higher priority (e.g. 10)",
                "default": "10",
                "required": True,
            },
        },
        "records": [
            {
                "type": "MX",
                "subname": "",
                "ttl": 3600,
                "content": "{mx_priority} {mail_server}",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 mx ~all\"",
            },
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=none; rua=mailto:dmarc-reports@{domain}\"",
            },
        ],
    },

    # -------------------------------------------------------------------------
    # Chat/Social (2)
    # -------------------------------------------------------------------------
    {
        "id": "matrix_synapse",
        "name": "Matrix / Synapse",
        "description": "SRV records for Matrix federation and client discovery (Synapse homeserver).",
        "category": "Chat/Social",
        "variables": {
            "matrix_server": {
                "label": "Matrix Homeserver Hostname",
                "hint": "FQDN of your Synapse server (e.g. matrix.example.com.)",
                "default": "",
                "required": True,
            },
            "matrix_port": {
                "label": "Federation Port",
                "hint": "Port Synapse listens on for federation (default: 8448)",
                "default": "8448",
                "required": True,
            },
        },
        "records": [
            {
                "type": "SRV",
                "subname": "_matrix._tcp",
                "ttl": 3600,
                "content": "10 0 {matrix_port} {matrix_server}",
            },
            {
                "type": "SRV",
                "subname": "_matrix-fed._tcp",
                "ttl": 3600,
                "content": "10 0 {matrix_port} {matrix_server}",
            },
        ],
    },
    {
        "id": "xmpp_jabber",
        "name": "XMPP / Jabber",
        "description": "SRV records for XMPP client and server (federation) connections.",
        "category": "Chat/Social",
        "variables": {
            "xmpp_server": {
                "label": "XMPP Server Hostname",
                "hint": "FQDN of your XMPP server with trailing dot (e.g. xmpp.example.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "SRV",
                "subname": "_xmpp-client._tcp",
                "ttl": 3600,
                "content": "5 0 5222 {xmpp_server}",
            },
            {
                "type": "SRV",
                "subname": "_xmpp-server._tcp",
                "ttl": 3600,
                "content": "5 0 5269 {xmpp_server}",
            },
        ],
    },

    # -------------------------------------------------------------------------
    # Web (2)
    # -------------------------------------------------------------------------
    {
        "id": "letsencrypt_caa",
        "name": "Let's Encrypt CAA",
        "description": "CAA records restricting certificate issuance to Let's Encrypt only.",
        "category": "Web",
        "variables": {},
        "records": [
            {
                "type": "CAA",
                "subname": "",
                "ttl": 86400,
                "content": "0 issue \"letsencrypt.org\"",
            },
            {
                "type": "CAA",
                "subname": "",
                "ttl": 86400,
                "content": "0 issuewild \"letsencrypt.org\"",
            },
        ],
    },
    {
        "id": "web_hosting_cname",
        "name": "Web Hosting CNAME",
        "description": "CNAME pointing the www subdomain to a hosting provider.",
        "category": "Web",
        "variables": {
            "hosting_target": {
                "label": "Hosting Target Hostname",
                "hint": "FQDN provided by your hosting provider with trailing dot (e.g. mysite.netlify.app.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{hosting_target}",
            },
        ],
    },

    # -------------------------------------------------------------------------
    # Security (4)
    # -------------------------------------------------------------------------
    {
        "id": "dmarc_standalone",
        "name": "DMARC Standalone",
        "description": "Add or update a DMARC policy TXT record for the domain.",
        "category": "Security",
        "variables": {
            "dmarc_policy": {
                "label": "DMARC Policy",
                "hint": "none, quarantine, or reject",
                "default": "none",
                "required": True,
            },
            "dmarc_rua": {
                "label": "Aggregate Report Email",
                "hint": "Email address to receive DMARC aggregate reports",
                "default": "dmarc@{domain}",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p={dmarc_policy}; rua=mailto:{dmarc_rua}\"",
            },
        ],
    },
    {
        "id": "spf_standalone",
        "name": "SPF Standalone",
        "description": "Add an SPF TXT record with configurable includes and policy.",
        "category": "Security",
        "variables": {
            "spf_includes": {
                "label": "SPF Include Mechanisms",
                "hint": "Space-separated include directives (e.g. include:_spf.example.com mx)",
                "default": "mx",
                "required": True,
            },
            "spf_policy": {
                "label": "SPF Fail Policy",
                "hint": "~all (soft fail) or -all (hard fail)",
                "default": "~all",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 {spf_includes} {spf_policy}\"",
            },
        ],
    },
    {
        "id": "mta_sts",
        "name": "MTA-STS",
        "description": "DNS records required for MTA-STS (SMTP TLS enforcement) policy discovery.",
        "category": "Security",
        "variables": {
            "mta_sts_id": {
                "label": "MTA-STS Policy ID",
                "hint": "Unique policy identifier string (e.g. a timestamp like 20240101000000)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "mta-sts",
                "ttl": 3600,
                "content": "mta-sts.{domain}.",
            },
            {
                "type": "TXT",
                "subname": "_mta-sts",
                "ttl": 3600,
                "content": "\"v=STSv1; id={mta_sts_id}\"",
            },
            {
                "type": "TXT",
                "subname": "_smtp._tls",
                "ttl": 3600,
                "content": "\"v=TLSRPTv1; rua=mailto:tlsrpt@{domain}\"",
            },
        ],
    },
    {
        "id": "dane_tlsa",
        "name": "DANE / TLSA",
        "description": "TLSA record for DANE (DNS-based Authentication of Named Entities).",
        "category": "Security",
        "variables": {
            "tlsa_port": {
                "label": "Port",
                "hint": "TCP port the service runs on (e.g. 443, 25, 993)",
                "default": "443",
                "required": True,
            },
            "tlsa_usage": {
                "label": "Certificate Usage",
                "hint": "0=PKIX-TA, 1=PKIX-EE, 2=DANE-TA, 3=DANE-EE",
                "default": "3",
                "required": True,
            },
            "tlsa_selector": {
                "label": "Selector",
                "hint": "0=Full certificate, 1=SubjectPublicKeyInfo",
                "default": "1",
                "required": True,
            },
            "tlsa_matching": {
                "label": "Matching Type",
                "hint": "0=Exact, 1=SHA-256, 2=SHA-512",
                "default": "1",
                "required": True,
            },
            "tlsa_hash": {
                "label": "Certificate Hash",
                "hint": "Hex-encoded hash of the selected certificate data",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TLSA",
                "subname": "_{tlsa_port}._tcp",
                "ttl": 3600,
                "content": "{tlsa_usage} {tlsa_selector} {tlsa_matching} {tlsa_hash}",
            },
        ],
    },

    # -------------------------------------------------------------------------
    # ACME/Certificates (3)
    # -------------------------------------------------------------------------
    {
        "id": "acme_dns01_txt",
        "name": "DNS-01 Challenge TXT",
        "description": "Temporary TXT record for an ACME DNS-01 challenge (low TTL for quick propagation).",
        "category": "ACME/Certificates",
        "variables": {
            "acme_token": {
                "label": "ACME Challenge Token",
                "hint": "The token value provided by your ACME client",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "_acme-challenge",
                "ttl": 60,
                "content": "\"{acme_token}\"",
            },
        ],
    },
    {
        "id": "acme_dns01_cname",
        "name": "DNS-01 CNAME Delegation",
        "description": "CNAME delegating the ACME challenge subdomain to a validation provider.",
        "category": "ACME/Certificates",
        "variables": {
            "validation_domain": {
                "label": "Validation Domain",
                "hint": "Target FQDN for the CNAME with trailing dot (e.g. _acme-challenge.auth.example.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "_acme-challenge",
                "ttl": 3600,
                "content": "{validation_domain}",
            },
        ],
    },
    {
        "id": "caa_acme_account",
        "name": "CAA with ACME Account Binding",
        "description": "CAA records that restrict issuance to a specific CA and ACME account URI.",
        "category": "ACME/Certificates",
        "variables": {
            "ca_domain": {
                "label": "CA Domain",
                "hint": "Certificate Authority domain (e.g. letsencrypt.org)",
                "default": "letsencrypt.org",
                "required": True,
            },
            "account_uri": {
                "label": "ACME Account URI",
                "hint": "Your ACME account URL (e.g. https://acme-v02.api.letsencrypt.org/acme/acct/123456)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CAA",
                "subname": "",
                "ttl": 86400,
                "content": "0 issue \"{ca_domain}; accounturi={account_uri}\"",
            },
            {
                "type": "CAA",
                "subname": "",
                "ttl": 86400,
                "content": "0 issuewild \"{ca_domain}; accounturi={account_uri}\"",
            },
        ],
    },

    # -------------------------------------------------------------------------
    # Verification (2)
    # -------------------------------------------------------------------------
    {
        "id": "google_site_verification",
        "name": "Google Site Verification",
        "description": "TXT record for verifying domain ownership with Google Search Console.",
        "category": "Verification",
        "variables": {
            "google_verify_code": {
                "label": "Google Verification Code",
                "hint": "The full verification string from Google Search Console (e.g. google-site-verification=xxxxx)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{google_verify_code}\"",
            },
        ],
    },
    {
        "id": "facebook_domain_verification",
        "name": "Facebook Domain Verification",
        "description": "TXT record for verifying domain ownership with Facebook / Meta Business.",
        "category": "Verification",
        "variables": {
            "fb_verify_code": {
                "label": "Facebook Verification Code",
                "hint": "The verification string from Facebook Business Manager (e.g. facebook-domain-verification=xxxxx)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{fb_verify_code}\"",
            },
        ],
    },
]
