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

TTL values follow common conventions (60 = ACME challenge, 3600 = 1 hr, 86400 = 1 day).
MX/CNAME/NS targets must have a trailing dot.
TXT content must be wrapped in escaped double-quotes.
SRV content format: "priority weight port target."
"""

CATEGORIES = [
    "Google",
    "Microsoft 365",
    "Proton",
    "Email Providers",
    "Self-Hosted Email",
    "Transactional Email",
    "Web Platforms",
    "Web Hosting",
    "CDN/Protection",
    "Cloud Providers",
    "Collaboration",
    "Identity/Auth",
    "Developer Platforms",
    "Chat/Social",
    "ACME/Certificates",
    "Security",
    "Verification",
]

TEMPLATES = [

    # =========================================================================
    # Google (5)
    # =========================================================================
    {
        "id": "google_workspace_mail",
        "name": "Google Workspace Mail",
        "description": "MX records (5 servers) and SPF TXT for Google Workspace email delivery.",
        "category": "Google",
        "variables": {},
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
        ],
    },
    {
        "id": "google_dkim",
        "name": "Google DKIM",
        "description": "CNAME for Google Workspace DKIM selector pointing to Google's DKIM record.",
        "category": "Google",
        "variables": {
            "dkim_selector": {
                "label": "DKIM Selector",
                "hint": "Found in Google Admin Console under Apps > Google Workspace > Gmail > Authenticate email",
                "default": "google",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "{dkim_selector}._domainkey",
                "ttl": 3600,
                "content": "{dkim_selector}.domainkey.{domain}.",
            },
        ],
    },
    {
        "id": "google_dmarc",
        "name": "Google DMARC",
        "description": "DMARC TXT record with quarantine policy and aggregate reporting for Google Workspace.",
        "category": "Google",
        "variables": {},
        "records": [
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\"",
            },
        ],
    },

    # =========================================================================
    # Microsoft 365 (5)
    # =========================================================================
    {
        "id": "m365_mail",
        "name": "M365 Exchange Mail",
        "description": "MX record, SPF TXT, and Autodiscover CNAME for Microsoft 365 Exchange Online.",
        "category": "Microsoft 365",
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
                "content": "\"v=spf1 include:spf.protection.outlook.com ~all\"",
            },
            {
                "type": "CNAME",
                "subname": "autodiscover",
                "ttl": 3600,
                "content": "autodiscover.outlook.com.",
            },
        ],
    },
    {
        "id": "m365_dkim",
        "name": "M365 DKIM",
        "description": "Two DKIM CNAME records (selector1 and selector2) for Microsoft 365 Exchange Online.",
        "category": "Microsoft 365",
        "variables": {
            "m365_dkim_domain": {
                "label": "M365 Initial Domain",
                "hint": "Your onmicrosoft.com domain with dashes replacing dots (e.g. contoso-com.onmicrosoft.com)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "selector1._domainkey",
                "ttl": 3600,
                "content": "selector1-{m365_dkim_domain}._domainkey.{m365_dkim_domain}.",
            },
            {
                "type": "CNAME",
                "subname": "selector2._domainkey",
                "ttl": 3600,
                "content": "selector2-{m365_dkim_domain}._domainkey.{m365_dkim_domain}.",
            },
        ],
    },
    {
        "id": "m365_teams",
        "name": "M365 Teams / Skype",
        "description": "SRV and CNAME records for Microsoft Teams and Skype for Business federation.",
        "category": "Microsoft 365",
        "variables": {},
        "records": [
            {
                "type": "SRV",
                "subname": "_sip._tls",
                "ttl": 3600,
                "content": "100 1 443 sipdir.online.lync.com.",
            },
            {
                "type": "SRV",
                "subname": "_sipfederationtls._tcp",
                "ttl": 3600,
                "content": "100 1 5061 sipfed.online.lync.com.",
            },
            {
                "type": "CNAME",
                "subname": "sip",
                "ttl": 3600,
                "content": "sipdir.online.lync.com.",
            },
            {
                "type": "CNAME",
                "subname": "lyncdiscover",
                "ttl": 3600,
                "content": "webdir.online.lync.com.",
            },
        ],
    },
    {
        "id": "m365_intune",
        "name": "M365 Intune (MDM)",
        "description": "CNAME records for Microsoft Intune mobile device management enrollment.",
        "category": "Microsoft 365",
        "variables": {},
        "records": [
            {
                "type": "CNAME",
                "subname": "enterpriseregistration",
                "ttl": 3600,
                "content": "enterpriseregistration.windows.net.",
            },
            {
                "type": "CNAME",
                "subname": "enterpriseenrollment",
                "ttl": 3600,
                "content": "enterpriseenrollment.manage.microsoft.com.",
            },
        ],
    },
    {
        "id": "m365_dmarc",
        "name": "M365 DMARC",
        "description": "DMARC TXT record with quarantine policy and aggregate reporting for Microsoft 365.",
        "category": "Microsoft 365",
        "variables": {},
        "records": [
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\"",
            },
        ],
    },

    # =========================================================================
    # Proton (3)
    # =========================================================================
    {
        "id": "proton_mail",
        "name": "Proton Mail",
        "description": "MX records, SPF TXT, and domain verification TXT for Proton Mail custom domains.",
        "category": "Proton",
        "variables": {
            "proton_verify": {
                "label": "Proton Mail Verification Code",
                "hint": "The verification value from the Proton Mail admin panel (e.g. protonmail-verification=xxxxx)",
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
                "content": "\"protonmail-verification={proton_verify}\"",
            },
        ],
    },
    {
        "id": "proton_dkim",
        "name": "Proton DKIM",
        "description": "Three DKIM CNAME records for Proton Mail custom domain email authentication.",
        "category": "Proton",
        "variables": {
            "proton_verify": {
                "label": "Proton Verification Token",
                "hint": "The token part of your Proton verification code (used to build DKIM targets)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "protonmail._domainkey",
                "ttl": 3600,
                "content": "protonmail.domainkey.{proton_verify}.domains.proton.ch.",
            },
            {
                "type": "CNAME",
                "subname": "protonmail2._domainkey",
                "ttl": 3600,
                "content": "protonmail2.domainkey.{proton_verify}.domains.proton.ch.",
            },
            {
                "type": "CNAME",
                "subname": "protonmail3._domainkey",
                "ttl": 3600,
                "content": "protonmail3.domainkey.{proton_verify}.domains.proton.ch.",
            },
        ],
    },
    {
        "id": "proton_dmarc",
        "name": "Proton DMARC",
        "description": "DMARC TXT record with quarantine policy and aggregate reporting for Proton Mail.",
        "category": "Proton",
        "variables": {},
        "records": [
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\"",
            },
        ],
    },

    # =========================================================================
    # Email Providers (6)
    # =========================================================================
    {
        "id": "fastmail",
        "name": "Fastmail",
        "description": "MX records, SPF TXT, and three DKIM CNAMEs for Fastmail custom domain email.",
        "category": "Email Providers",
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
        ],
    },
    {
        "id": "zoho_mail",
        "name": "Zoho Mail",
        "description": "MX records, SPF TXT, and DKIM CNAME for Zoho Mail custom domain.",
        "category": "Email Providers",
        "variables": {
            "zoho_dkim_selector": {
                "label": "DKIM Selector",
                "hint": "DKIM selector from Zoho Mail admin dashboard (usually 'zmail')",
                "default": "zmail",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 mx.zoho.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "20 mx2.zoho.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "50 mx3.zoho.com."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:zoho.com ~all\"",
            },
            {
                "type": "CNAME",
                "subname": "{zoho_dkim_selector}._domainkey",
                "ttl": 3600,
                "content": "{zoho_dkim_selector}.{domain}.zohomail.com.",
            },
        ],
    },
    {
        "id": "tutanota_mail",
        "name": "Tutanota / Tuta Mail",
        "description": "MX record and SPF TXT for Tutanota (Tuta) custom domain email.",
        "category": "Email Providers",
        "variables": {},
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 mail.tutanota.de."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.tutanota.de ~all\"",
            },
        ],
    },
    {
        "id": "infomaniak_mail",
        "name": "Infomaniak Mail",
        "description": "MX records, SPF TXT, and DKIM TXT for Infomaniak hosted email.",
        "category": "Email Providers",
        "variables": {
            "infomaniak_dkim": {
                "label": "DKIM Public Key",
                "hint": "The DKIM public key value (p=...) from the Infomaniak dashboard",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "5 mta.infomaniak.ch."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 mta2.infomaniak.ch."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.infomaniak.ch ~all\"",
            },
            {
                "type": "TXT",
                "subname": "default._domainkey",
                "ttl": 3600,
                "content": "\"v=DKIM1; k=rsa; p={infomaniak_dkim}\"",
            },
        ],
    },
    {
        "id": "mailfence_mail",
        "name": "Mailfence Mail",
        "description": "MX records and SPF TXT for Mailfence custom domain email.",
        "category": "Email Providers",
        "variables": {},
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600, "content": "10 mailfence.com."},
            {"type": "MX", "subname": "", "ttl": 3600, "content": "20 relay.mailfence.com."},
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.mailfence.com ~all\"",
            },
        ],
    },
    {
        "id": "basic_mx_spf_dmarc",
        "name": "Basic MX + SPF + DMARC",
        "description": "Generic MX record with SPF and DMARC for any mail server.",
        "category": "Email Providers",
        "variables": {
            "mail_server": {
                "label": "Mail Server Hostname",
                "hint": "Fully-qualified hostname of your mail server with trailing dot (e.g. mail.example.com.)",
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
                "content": "\"v=DMARC1; p=none; rua=mailto:dmarc@{domain}\"",
            },
        ],
    },

    # =========================================================================
    # Self-Hosted Email (3)
    # =========================================================================
    {
        "id": "mailinbox",
        "name": "Mail-in-a-Box",
        "description": "MX, SPF, DMARC, autoconfig CNAME, and autodiscover SRV for Mail-in-a-Box.",
        "category": "Self-Hosted Email",
        "variables": {
            "mail_host": {
                "label": "Mail-in-a-Box Hostname",
                "hint": "FQDN of your Mail-in-a-Box server with trailing dot (e.g. box.example.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "MX",
                "subname": "",
                "ttl": 3600,
                "content": "10 {mail_host}",
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
                "content": "\"v=DMARC1; p=quarantine; rua=mailto:admin@{domain}\"",
            },
            {
                "type": "CNAME",
                "subname": "autoconfig",
                "ttl": 3600,
                "content": "{mail_host}",
            },
            {
                "type": "SRV",
                "subname": "_autodiscover._tcp",
                "ttl": 3600,
                "content": "10 1 443 {mail_host}",
            },
        ],
    },
    {
        "id": "mailcow",
        "name": "Mailcow",
        "description": "MX, SPF, DMARC, autoconfig/autodiscover CNAMEs, and SRV records for Mailcow.",
        "category": "Self-Hosted Email",
        "variables": {
            "mail_host": {
                "label": "Mailcow Hostname",
                "hint": "FQDN of your Mailcow server with trailing dot (e.g. mail.example.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "MX",
                "subname": "",
                "ttl": 3600,
                "content": "10 {mail_host}",
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
                "content": "\"v=DMARC1; p=quarantine; rua=mailto:postmaster@{domain}\"",
            },
            {
                "type": "CNAME",
                "subname": "autoconfig",
                "ttl": 3600,
                "content": "{mail_host}",
            },
            {
                "type": "CNAME",
                "subname": "autodiscover",
                "ttl": 3600,
                "content": "{mail_host}",
            },
            {
                "type": "SRV",
                "subname": "_autodiscover._tcp",
                "ttl": 3600,
                "content": "10 1 443 {mail_host}",
            },
            {
                "type": "SRV",
                "subname": "_submissions._tcp",
                "ttl": 3600,
                "content": "10 1 465 {mail_host}",
            },
        ],
    },
    {
        "id": "cloudron",
        "name": "Cloudron Mail",
        "description": "MX, SPF, and DMARC records for a Cloudron self-hosted mail server.",
        "category": "Self-Hosted Email",
        "variables": {
            "cloudron_host": {
                "label": "Cloudron Hostname",
                "hint": "FQDN of your Cloudron instance with trailing dot (e.g. my.example.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "MX",
                "subname": "",
                "ttl": 3600,
                "content": "10 {cloudron_host}",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 a:{cloudron_host} ~all\"",
            },
            {
                "type": "TXT",
                "subname": "_dmarc",
                "ttl": 3600,
                "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\"",
            },
        ],
    },

    # =========================================================================
    # Transactional Email (5)
    # =========================================================================
    {
        "id": "mailgun",
        "name": "Mailgun",
        "description": "MX records, SPF TXT, and DKIM TXT for Mailgun transactional email sending.",
        "category": "Transactional Email",
        "variables": {
            "mailgun_region": {
                "label": "Mailgun Subdomain Prefix",
                "hint": "Subdomain prefix configured in Mailgun, usually 'mg'",
                "default": "mg",
                "required": True,
            },
            "mailgun_dkim_key": {
                "label": "Mailgun DKIM Public Key",
                "hint": "The DKIM public key value from the Mailgun dashboard (p=...)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "MX",
                "subname": "{mailgun_region}",
                "ttl": 3600,
                "content": "10 mxa.mailgun.org.",
            },
            {
                "type": "MX",
                "subname": "{mailgun_region}",
                "ttl": 3600,
                "content": "10 mxb.mailgun.org.",
            },
            {
                "type": "TXT",
                "subname": "{mailgun_region}",
                "ttl": 3600,
                "content": "\"v=spf1 include:mailgun.org ~all\"",
            },
            {
                "type": "TXT",
                "subname": "smtp._domainkey.{mailgun_region}",
                "ttl": 3600,
                "content": "\"{mailgun_dkim_key}\"",
            },
        ],
    },
    {
        "id": "sendgrid",
        "name": "SendGrid",
        "description": "SPF TXT and two DKIM CNAME records for SendGrid email authentication.",
        "category": "Transactional Email",
        "variables": {
            "sendgrid_s1_target": {
                "label": "Selector 1 CNAME Target",
                "hint": "s1._domainkey CNAME target from SendGrid dashboard (e.g. s1.domainkey.uXXXX.wl.sendgrid.net.)",
                "default": "",
                "required": True,
            },
            "sendgrid_s2_target": {
                "label": "Selector 2 CNAME Target",
                "hint": "s2._domainkey CNAME target from SendGrid dashboard (e.g. s2.domainkey.uXXXX.wl.sendgrid.net.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:sendgrid.net ~all\"",
            },
            {
                "type": "CNAME",
                "subname": "s1._domainkey",
                "ttl": 3600,
                "content": "{sendgrid_s1_target}",
            },
            {
                "type": "CNAME",
                "subname": "s2._domainkey",
                "ttl": 3600,
                "content": "{sendgrid_s2_target}",
            },
        ],
    },
    {
        "id": "mailchimp_mandrill",
        "name": "Mailchimp / Mandrill",
        "description": "SPF TXT and DKIM TXT for Mailchimp transactional email via Mandrill.",
        "category": "Transactional Email",
        "variables": {
            "mandrill_dkim": {
                "label": "Mandrill DKIM Value",
                "hint": "The DKIM TXT record value from the Mailchimp/Mandrill dashboard",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.mandrillapp.com ~all\"",
            },
            {
                "type": "TXT",
                "subname": "mandrill._domainkey",
                "ttl": 3600,
                "content": "\"{mandrill_dkim}\"",
            },
        ],
    },
    {
        "id": "amazon_ses",
        "name": "Amazon SES",
        "description": "Domain verification TXT, SPF TXT, and three DKIM CNAMEs for Amazon SES.",
        "category": "Transactional Email",
        "variables": {
            "ses_verify_token": {
                "label": "SES Domain Verification Token",
                "hint": "The token from the SES domain verification TXT record (e.g. pmBGN/7MjnfhTKUZ06Enqq1PeGUaAkU...)",
                "default": "",
                "required": True,
            },
            "ses_dkim1": {
                "label": "DKIM Token 1",
                "hint": "First DKIM token from SES (the part before ._domainkey)",
                "default": "",
                "required": True,
            },
            "ses_dkim2": {
                "label": "DKIM Token 2",
                "hint": "Second DKIM token from SES",
                "default": "",
                "required": True,
            },
            "ses_dkim3": {
                "label": "DKIM Token 3",
                "hint": "Third DKIM token from SES",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "_amazonses",
                "ttl": 3600,
                "content": "\"{ses_verify_token}\"",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:amazonses.com ~all\"",
            },
            {
                "type": "CNAME",
                "subname": "{ses_dkim1}._domainkey",
                "ttl": 3600,
                "content": "{ses_dkim1}.dkim.amazonses.com.",
            },
            {
                "type": "CNAME",
                "subname": "{ses_dkim2}._domainkey",
                "ttl": 3600,
                "content": "{ses_dkim2}.dkim.amazonses.com.",
            },
            {
                "type": "CNAME",
                "subname": "{ses_dkim3}._domainkey",
                "ttl": 3600,
                "content": "{ses_dkim3}.dkim.amazonses.com.",
            },
        ],
    },
    {
        "id": "postmark",
        "name": "Postmark",
        "description": "SPF TXT, DKIM CNAME, and bounce subdomain CNAME for Postmark transactional email.",
        "category": "Transactional Email",
        "variables": {
            "postmark_dkim_host": {
                "label": "DKIM CNAME Host",
                "hint": "The CNAME host (subname) from the Postmark dashboard (e.g. 20201231210734pm._domainkey)",
                "default": "",
                "required": True,
            },
            "postmark_dkim_value": {
                "label": "DKIM CNAME Target",
                "hint": "The CNAME target from the Postmark dashboard with trailing dot (e.g. pm.domainkey.postmarkapp.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"v=spf1 include:spf.mtasv.net ~all\"",
            },
            {
                "type": "CNAME",
                "subname": "{postmark_dkim_host}",
                "ttl": 3600,
                "content": "{postmark_dkim_value}",
            },
            {
                "type": "CNAME",
                "subname": "pm-bounces",
                "ttl": 3600,
                "content": "pm.mtasv.net.",
            },
        ],
    },

    # =========================================================================
    # Web Platforms (4)
    # =========================================================================
    {
        "id": "shopify",
        "name": "Shopify",
        "description": "A record, www CNAME, and optional domain verification TXT for Shopify stores.",
        "category": "Web Platforms",
        "variables": {
            "shopify_verify": {
                "label": "Shopify Verification TXT",
                "hint": "Domain verification string from Shopify admin (leave blank if not required)",
                "default": "",
                "required": False,
            },
        },
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "23.227.38.65"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "shops.myshopify.com.",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{shopify_verify}\"",
            },
        ],
    },
    {
        "id": "squarespace",
        "name": "Squarespace",
        "description": "Four A records, www CNAME, and domain verification TXT for Squarespace websites.",
        "category": "Web Platforms",
        "variables": {
            "squarespace_verify": {
                "label": "Squarespace Verification TXT",
                "hint": "Domain verification string from Squarespace settings",
                "default": "",
                "required": False,
            },
        },
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "198.185.159.144"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "198.185.159.145"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "198.49.23.144"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "198.49.23.145"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "ext-cust.squarespace.com.",
            },
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{squarespace_verify}\"",
            },
        ],
    },
    {
        "id": "wordpress_com",
        "name": "WordPress.com",
        "description": "Two A records and www CNAME for WordPress.com custom domain mapping.",
        "category": "Web Platforms",
        "variables": {},
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "192.0.78.24"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "192.0.78.25"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{domain}.",
            },
        ],
    },
    {
        "id": "wix",
        "name": "Wix",
        "description": "A record at apex and www CNAME for Wix custom domain (IP from Wix dashboard).",
        "category": "Web Platforms",
        "variables": {
            "wix_ip": {
                "label": "Wix Server IP",
                "hint": "IPv4 address shown in the Wix domain connection wizard",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "A",
                "subname": "",
                "ttl": 3600,
                "content": "{wix_ip}",
            },
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{domain}.",
            },
        ],
    },

    # =========================================================================
    # Web Hosting (5)
    # =========================================================================
    {
        "id": "web_server",
        "name": "Web Server (A + AAAA + www)",
        "description": "A and AAAA records for apex, plus www CNAME redirect.",
        "category": "Web Hosting",
        "variables": {
            "ipv4_address": {
                "label": "IPv4 Address",
                "hint": "IPv4 address of your web server",
                "default": "",
                "required": True,
            },
            "ipv6_address": {
                "label": "IPv6 Address",
                "hint": "IPv6 address of your web server",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "{ipv4_address}"},
            {"type": "AAAA", "subname": "", "ttl": 3600, "content": "{ipv6_address}"},
            {"type": "CNAME", "subname": "www", "ttl": 3600, "content": "{domain}."},
        ],
    },
    {
        "id": "github_pages",
        "name": "GitHub Pages",
        "description": "Four A records, four AAAA records, and www CNAME for GitHub Pages custom domain.",
        "category": "Web Hosting",
        "variables": {
            "github_username": {
                "label": "GitHub Username / Org",
                "hint": "Your GitHub username or organisation name (e.g. myusername)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "185.199.108.153"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "185.199.109.153"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "185.199.110.153"},
            {"type": "A", "subname": "", "ttl": 3600, "content": "185.199.111.153"},
            {"type": "AAAA", "subname": "", "ttl": 3600, "content": "2606:50c0:8000::153"},
            {"type": "AAAA", "subname": "", "ttl": 3600, "content": "2606:50c0:8001::153"},
            {"type": "AAAA", "subname": "", "ttl": 3600, "content": "2606:50c0:8002::153"},
            {"type": "AAAA", "subname": "", "ttl": 3600, "content": "2606:50c0:8003::153"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{github_username}.github.io.",
            },
        ],
    },
    {
        "id": "netlify",
        "name": "Netlify",
        "description": "A record at apex and www CNAME for Netlify custom domain hosting.",
        "category": "Web Hosting",
        "variables": {
            "netlify_subdomain": {
                "label": "Netlify App Subdomain",
                "hint": "Your Netlify app hostname with trailing dot (e.g. my-site.netlify.app.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "75.2.60.5"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{netlify_subdomain}",
            },
        ],
    },
    {
        "id": "vercel",
        "name": "Vercel",
        "description": "A record at apex and www CNAME for Vercel custom domain deployment.",
        "category": "Web Hosting",
        "variables": {},
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "76.76.21.21"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "cname.vercel-dns.com.",
            },
        ],
    },
    {
        "id": "cloudflare_pages",
        "name": "Cloudflare Pages",
        "description": "CNAME records at apex and www pointing to a Cloudflare Pages project.",
        "category": "Web Hosting",
        "variables": {
            "cf_pages_project": {
                "label": "Cloudflare Pages Hostname",
                "hint": "Your pages.dev hostname with trailing dot (e.g. my-project.pages.dev.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "",
                "ttl": 3600,
                "content": "{cf_pages_project}",
            },
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{cf_pages_project}",
            },
        ],
    },

    # =========================================================================
    # CDN/Protection (1)
    # =========================================================================
    {
        "id": "cloudflare_tunnel",
        "name": "Cloudflare Tunnel",
        "description": "CNAME records routing apex and www through a Cloudflare Tunnel (Argo Tunnel).",
        "category": "CDN/Protection",
        "variables": {
            "tunnel_id": {
                "label": "Tunnel UUID",
                "hint": "The tunnel UUID from 'cloudflared tunnel list' or the Cloudflare Zero Trust dashboard",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "",
                "ttl": 3600,
                "content": "{tunnel_id}.cfargotunnel.com.",
            },
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{tunnel_id}.cfargotunnel.com.",
            },
        ],
    },

    # =========================================================================
    # Cloud Providers (1)
    # =========================================================================
    {
        "id": "azure_custom_domain",
        "name": "Azure Custom Domain",
        "description": "Domain verification TXT and www CNAME for an Azure App Service custom domain.",
        "category": "Cloud Providers",
        "variables": {
            "azure_verify_id": {
                "label": "Azure Verification ID",
                "hint": "The Custom Domain Verification ID string from the Azure portal",
                "default": "",
                "required": True,
            },
            "azure_target": {
                "label": "Azure App Hostname",
                "hint": "Your Azure app hostname with trailing dot (e.g. myapp.azurewebsites.net.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{azure_verify_id}\"",
            },
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{azure_target}",
            },
        ],
    },

    # =========================================================================
    # Collaboration (2)
    # =========================================================================
    {
        "id": "notion_custom_domain",
        "name": "Notion Custom Domain",
        "description": "Domain verification TXT and www CNAME for a Notion custom domain.",
        "category": "Collaboration",
        "variables": {
            "notion_verify": {
                "label": "Notion Verification TXT",
                "hint": "TXT verification value from Notion settings",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"{notion_verify}\"",
            },
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "custom.notion.site.",
            },
        ],
    },
    {
        "id": "atlassian_domain_verify",
        "name": "Atlassian Domain Verification",
        "description": "TXT record for verifying domain ownership with Atlassian (Jira, Confluence, etc.).",
        "category": "Collaboration",
        "variables": {
            "atlassian_verify_code": {
                "label": "Atlassian Verification Code",
                "hint": "The verification code from Atlassian Admin (admin.atlassian.com) domain verification",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "_atl-domain-verification",
                "ttl": 3600,
                "content": "\"{atlassian_verify_code}\"",
            },
        ],
    },

    # =========================================================================
    # Identity/Auth (2)
    # =========================================================================
    {
        "id": "okta_custom_domain",
        "name": "Okta Custom Domain",
        "description": "CNAME and verification TXT records for an Okta custom domain configuration.",
        "category": "Identity/Auth",
        "variables": {
            "okta_subdomain": {
                "label": "Okta Subdomain Label",
                "hint": "The subdomain label to use for your Okta custom domain (e.g. auth or login)",
                "default": "auth",
                "required": True,
            },
            "okta_target": {
                "label": "Okta CNAME Target",
                "hint": "The CNAME target from Okta with trailing dot (e.g. myorg.customdomains.okta.com.)",
                "default": "",
                "required": True,
            },
            "okta_verify": {
                "label": "Okta Verification Code",
                "hint": "The TXT verification value from the Okta admin portal",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "CNAME",
                "subname": "{okta_subdomain}",
                "ttl": 3600,
                "content": "{okta_target}",
            },
            {
                "type": "TXT",
                "subname": "_oktaverification",
                "ttl": 3600,
                "content": "\"{okta_verify}\"",
            },
        ],
    },

    # =========================================================================
    # Developer Platforms (2)
    # =========================================================================
    {
        "id": "render",
        "name": "Render",
        "description": "A record at apex and www CNAME for a Render web service custom domain.",
        "category": "Developer Platforms",
        "variables": {
            "render_target": {
                "label": "Render Service Hostname",
                "hint": "Your Render service hostname with trailing dot (e.g. xxx.onrender.com.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "A", "subname": "", "ttl": 3600, "content": "216.24.57.1"},
            {
                "type": "CNAME",
                "subname": "www",
                "ttl": 3600,
                "content": "{render_target}",
            },
        ],
    },

    # =========================================================================
    # Chat/Social (2)
    # =========================================================================
    {
        "id": "matrix_synapse",
        "name": "Matrix / Synapse",
        "description": "SRV records for Matrix federation and client discovery (Synapse homeserver).",
        "category": "Chat/Social",
        "variables": {
            "matrix_server": {
                "label": "Matrix Homeserver Hostname",
                "hint": "FQDN of your Synapse server with trailing dot (e.g. matrix.example.com.)",
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

    # =========================================================================
    # ACME/Certificates (3)
    # =========================================================================
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
        "description": "CAA records restricting issuance to a specific CA and ACME account URI.",
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

    # =========================================================================
    # Security (5)
    # =========================================================================
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
                "hint": "Email address to receive DMARC aggregate reports (e.g. dmarc@yourdomain.com)",
                "default": "",
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
    {
        "id": "letsencrypt_caa",
        "name": "Let's Encrypt CAA",
        "description": "CAA records restricting certificate issuance to Let's Encrypt only.",
        "category": "Security",
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

    # =========================================================================
    # Verification (5)
    # =========================================================================
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
    {
        "id": "microsoft_domain_verify",
        "name": "Microsoft Domain Verification",
        "description": "TXT record for verifying domain ownership with Microsoft 365 or Azure AD.",
        "category": "Verification",
        "variables": {
            "ms_verify_code": {
                "label": "Microsoft Verification Code",
                "hint": "The code portion from Microsoft domain verification (e.g. XXXXXXXXXXXXXXXXXX from MS=XXXXXXXXXXXXXXXXXX)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"MS={ms_verify_code}\"",
            },
        ],
    },
    {
        "id": "apple_domain_verify",
        "name": "Apple Domain Verification",
        "description": "TXT record for verifying domain ownership with Apple (Sign in with Apple, Business Manager, etc.).",
        "category": "Verification",
        "variables": {
            "apple_verify_code": {
                "label": "Apple Verification Code",
                "hint": "The verification code from Apple Business Manager or Apple Developer account",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"apple-domain-verification={apple_verify_code}\"",
            },
        ],
    },
    {
        "id": "brave_creator_verify",
        "name": "Brave Creator Verification",
        "description": "TXT record for verifying domain ownership with Brave Rewards / Brave Creators.",
        "category": "Verification",
        "variables": {
            "brave_verify_code": {
                "label": "Brave Verification Code",
                "hint": "The verification token from the Brave Creators dashboard",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {
                "type": "TXT",
                "subname": "",
                "ttl": 3600,
                "content": "\"brave-ledger-verification={brave_verify_code}\"",
            },
        ],
    },
    {
        "id": "google_site_verification",
        "name": "Google Site Verification (Legacy)",
        "description": "TXT record for verifying domain ownership with Google (legacy template, use Google category for new setups).",
        "category": "Verification",
        "variables": {
            "google_verify_code": {
                "label": "Google Verification Code",
                "hint": "Full verification string from Google Search Console (e.g. google-site-verification=xxxxx)",
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
]
