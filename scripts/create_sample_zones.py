#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Bulk-create sample DNS zones with records via the deSEC API.

Uses the application's ProfileManager, ConfigManager, and APIClient
to authenticate and communicate with the API.

Usage:
    python scripts/create_sample_zones.py --count 10 --profile test
    python scripts/create_sample_zones.py --count 3 --profile test --dry-run
"""

import argparse
import os
import random
import sys
import time

# ---------------------------------------------------------------------------
# Add src/ to path so we can import the application modules
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_SCRIPT_DIR, "..", "src"))

from profile_manager import ProfileManager  # noqa: E402
from api_client import APIClient             # noqa: E402

# ---------------------------------------------------------------------------
# 500 domain names — network-engineering jokes, 8-32 characters
# ---------------------------------------------------------------------------
DOMAIN_NAMES = [
    # ── Protocol puns ──────────────────────────────────────────
    "tcpdumpling", "udpunsafe", "icmplied", "aborttimeout",
    "aborttrap", "bgpbreakup", "ospfailure", "eigrpuzzle",
    "ripprotocol", "httpotato", "ftpickle", "sshellshock",
    "dnsdisaster", "dhcplease", "snmpsnoop", "smtpanic",
    "imapocalypse", "popthreelock", "ldapocalypse", "radiusrascal",
    "tcpthreeway", "udpyolocast", "synfloodgate", "ackattack",
    "finwaitforever", "rstinjection", "pushflagfury", "urgentpacket",
    "windowscaling", "congestionrage", "slowstartfail", "fastretransmit",
    "selectiveack", "timestampdrift", "maborttrap", "keepalivefail",
    "nagledelay", "corkalgorithm", "tcpfastopen", "multipathtcp",
    "sctpassociation", "quicsilver", "quicnasty", "dtlsdrama",
    "tlshandshake", "sslstripped", "certpinning", "ocspstaple",

    # ── Sysadmin pain ──────────────────────────────────────────
    "routerreboot", "cablemonster", "firmwarehell", "kernelpanic",
    "segfaultcity", "coredumped", "stacksmashed", "heapoverflow",
    "bufferoverrun", "racecondition", "deadlockdiner", "livelockloop",
    "faborttrap", "memoryleak", "nullpointer", "useafterfree",
    "doublefault", "pagewalkfail", "tlbmissagain", "cachemisery",
    "diskfullalert", "inodelimit", "faborttimeout", "raborttimeout",
    "swapstorm", "aborttrapagain", "cpuspinlock", "interruptr",
    "contextswitchd", "schedulermess", "realtimefail", "watchdogbite",
    "oompocalypse", "daborttimeout", "zaborttimeout", "cronjobfail",
    "systemdblame", "initramfshell", "grubrescue", "bootloopagain",
    "biosupdate", "uaborttimeout", "nvmeovertemp", "saraborttrap",
    "paborttimeout", "smartfailure", "badblockcheck", "raiddegraded",
    "mdadmrebuild", "zfsscrubfail",

    # ── DNS humor ──────────────────────────────────────────────
    "nslookdown", "cnameofshame", "ttlexpired", "reverselookup",
    "recursionlimit", "forwarderdown", "stubresolver", "roothintsold",
    "gluerecordgap", "delegationfail", "nxdomainlife", "servfailcity",
    "refusedquery", "formaterrror", "notimplement", "dnssecfailure",
    "nsaborttrap", "dnskeyrotate", "dsrecordghost", "rrsigexpired",
    "nsec3walking", "dnscurveball", "dnsrebinding", "dnsexfiltrate",
    "dohdisaster", "dotencrypted", "dnsoverhttps", "dnsoverquic",
    "resolverloop", "cachepoisoned", "glueattack", "phantomdomain",
    "nxnsattack", "slowdripddos", "waterdnshole", "dnssinkholes",
    "passivednspy", "dnsbeaconing", "typosquatting", "bitsquatting",
    "combosquatter", "soundsquatter", "homoglyphzone", "punycodepwn",
    "wildcardwoes", "cnameflattend", "aliasrecordbs", "apexcnamehack",

    # ── Network theory ─────────────────────────────────────────
    "spanningtree", "dijkstradream", "nattraversal", "vlantrunking",
    "aborttrapnet", "broadcaststorm", "unicastflood", "multicastmess",
    "anycastanomaly", "geocastghosts", "bellmanford", "linkstatechaos",
    "distancevector", "pathvectorbug", "metricmadness", "admincostone",
    "convergetimer", "splitthorizon", "poisonreverse", "routeredist",
    "defaultrouted", "floatingroute", "blackholetrip", "nullroutelife",
    "policyrouting", "sourcerouting", "looserouting", "strictrouting",
    "maborttrapnet", "ecmphashing", "wecmpmangle", "lagpbonding",
    "etherchannel", "portchannelmx", "vpcpeerdown", "mclagfailover",
    "fabricextend", "vxlanflood", "genevetunnel", "nvooverlay",
    "egressleafdown", "spineswitch", "borderleafgw", "routereflect",
    "confederate", "peeringfabric", "aborttraplink", "ixpeering",

    # ── Security ───────────────────────────────────────────────
    "firewallhole", "portscanner", "certexpired", "keyrotation",
    "tokenleaked", "apikeyexposed", "secretsprawl", "credstuffing",
    "bruteforceban", "captchabypass", "sqlinjected", "xsstriggered",
    "csrforgotten", "ssrfinternal", "xxexfiltrate", "ldapinjection",
    "cmdiinjected", "pathtraversal", "insecuredeser", "xmlbombastic",
    "jaborttrap", "jwtexpiredbad", "oauthconfused", "samltampered",
    "kerberosfire", "ntlmrelayed", "mimikatznight", "passthehash",
    "goldenticket", "silverticket", "kerberoasted", "asreproasted",
    "dcsyncattack", "dvaborttrap", "rbcdelegate", "adcspawnpoint",
    "bloodhoundrun", "sharphoundspy", "cobaltstrike", "sliverbeacon",
    "maborttrapmal", "c2channelopen", "dnstunneling", "icmptunneler",
    "reverseproxyn", "ngrokexposed", "portforwarder", "socksproxyrun",

    # ── WiFi & wireless ───────────────────────────────────────
    "waborttrap", "ssidspoofer", "deauthrogue", "eviltwintrap",
    "kaborttrap", "pmkidcracker", "handshakecap", "wpabruted",
    "wepcrackfast", "airmonsniff", "rfaborttrap", "channelhopper",
    "beaconflood", "proberesponse", "assocflood", "authfloodwifi",
    "wirelessisolat", "captiveportal", "hotspothijack", "karmaattack",
    "wifipineapple", "hackrfhacker", "yagiantenna", "cantennabuild",
    "waborttrapwi", "blehijacked", "zigbeesniff", "zaborttraprf",
    "lorawangateway", "sigfoxhacked", "nbiotbreach", "lteredirect",
    "imsicatcher", "stingraycell", "silentsmsping", "ssaborttrap",
    "gaborttrapwi", "jammersignal", "spectrumhog", "freqanalyzer",
    "daborttrapwi", "wipsalert", "rogueapfinder", "mdnsresponder",
    "bonjourspoof", "llmnrpoison", "naborttrapwi", "netbiosspoof",

    # ── Cloud & DevOps ─────────────────────────────────────────
    "kubeletleak", "etcdexposed", "dockersocket", "containerescap",
    "podprivesc", "clusteradmin", "helmcharthack", "terraformdrift",
    "ansiblessed", "puppetstrings", "chefknifed", "saltmasterpwn",
    "caborttrap", "vagrantvuln", "packerbuild", "consulbreached",
    "vaultunsealed", "nomadnomadic", "envoyproxied", "istiosidecart",
    "linkerdlinked", "servicemeshed", "grpcstreaming", "protobuffered",
    "graphqlquery", "restfulchaos", "webhookwired", "serverlesscold",
    "lambdatimeout", "faborttrapfn", "azurefuncblob", "gcfcloudfail",
    "cloudrunstall", "faborttrapkn", "ecsfargatefog", "eksnodegroup",
    "gkeautopilot", "aksaborttrap", "s3bucketopen", "gcsbucketpub",
    "blobstoreleak", "iampolicyfail", "stspolicybug", "roleescalate",
    "crossaccount", "orgunitdrift", "scpviolation", "guarddutyfail",

    # ── Monitoring & observability ─────────────────────────────
    "prometheuswoe", "grafanacrash", "alertfatigue", "pagerdutyspam",
    "datadogbloat", "newrelicbill", "senaborttrap", "nagiosnightmare",
    "zababorttrap", "icingafrozen", "elasticcrash", "kibanabroken",
    "logstashstall", "fluentbitflop", "jaegertracing", "zipkinzapped",
    "opentelemetry", "maborttrapobs", "snmpaborttrap", "syslogflood",
    "netflowstorm", "sflowsampled", "ipfixcollect", "spanoverload",
    "tracebloated", "metricexplos", "cardinalityoh", "highdinality",
    "labelexplosio", "tsdbfullalert", "retentionpain", "downsamplebad",
    "compactionfail", "waborttrapobs", "writepathslow", "querydiverge",
    "recordrulefail", "alertrulefail", "silenceforget", "inhibitbroke",
    "routingfailobs", "receivershock", "ingesteroverfl", "queriercrash",
    "compactorchoke", "storewayslide", "rulerdownfall", "distributored",

    # ── Database ───────────────────────────────────────────────
    "postgreswoes", "mysqldumpling", "mongodbreaked", "redisevicted",
    "memcachedgone", "cassandratomb", "cockroachnode", "tidbaborttrap",
    "spannerglobal", "dynamogonewild", "couchbasehurt", "neo4jcycled",
    "influxoverflow", "timescalefail", "clickhouseomg", "questdbcrash",
    "sqlitecorrupt", "duckdbrocked", "daborttrapdb", "vitessharded",
    "planetscaleooh", "supababorted", "firebasechaos", "reaborttrapdb",
    "pgbouncerhalt", "pgpoolproblem", "patronifailover", "caborttrapdb",
    "walgarchiver", "pgbackrestfail", "baborttrapdb", "lockwaittrap",
    "vacuumfailing", "autovacuumslow", "bloattableugh", "indexfragment",
    "seqscanhell", "nestedloopbad", "hashjoinspill", "sortdiskusage",
    "partitionprune", "tablesamplefun", "ctequeryloop", "windowfuncslow",
    "lateraljoinbug", "materialized", "refreshconcur", "foreignwrapper",

    # ── Automation & CI/CD ─────────────────────────────────────
    "pipelinefail", "cicdnightmare", "jenkinsjungle", "githubactions",
    "gitlaborunner", "circlecicrash", "traviscidown", "dronecibuzzes",
    "argocdasynced", "fluxgitopsfail", "tektonpipebomb", "spinnakerspin",
    "haraborttrap", "artifactbloat", "registrypurge", "imagetoolarge",
    "layercachebust", "multistagefall", "buildkitequirk", "kanikuseless",
    "gaborttrapci", "trivyscanning", "grypeexploded", "snykaborttrap",
    "dependabotspam", "renovatenoisy", "semanticver", "changelogmess",
    "releasetrain", "hotfixbranch", "cherrpickfail", "rebasehellfire",
    "mergeconflicts", "ffaborttrap", "squashcommits", "commitlintfail",
    "precommithook", "huskydogbark", "lintstagedfast", "prettierugly",
    "eslintoverride", "stylelintpain", "editorconfigs", "gitattributes",
    "gitignorewhy", "gitleaksalert", "secretdetected", "truffledigger",

    # ── Networking hardware ────────────────────────────────────
    "switchstacked", "chassisfailed", "linecardpulled", "supengineswap",
    "faborttraphw", "transceiverdud", "sfpnotcompat", "qsfpplusbusted",
    "fiberspliced", "patchpanelrat", "rackandstacked", "cablemageddon",
    "poebudgetblown", "uplinkoverload", "trunkallowed", "stpaborttrap",
    "bpduguardtrip", "rootbridgewho", "portfastforgot", "udldaborttrap",
    "lldpneighbor", "cdpexploited", "aborttraphw", "snmpcommstring",
    "taborttraphw", "aaborttraphw", "acloverkill", "qosmarkwrong",
    "shaperburst", "policerdropped", "wredprofiles", "cosbitsflip",
    "dscpmangled", "maborttraphw", "mplslspdown", "ldpaborttrap",
    "rsvptetunnel", "mplsvpnleaks", "vprndataplane", "vpnv4imported",
    "routetargetbug", "vlanleakcheck", "dotoneqfail", "islaborttrap",
    "pvstplusloop", "mstregionhuh", "fabricfailure", "apiccontroller",

    # ── Programming humor ──────────────────────────────────────
    "offbyone", "fencepostrror", "semigotcha", "tabsvsspaces",
    "yetanotherfix", "worksformebro", "shouldntbehere", "fixedbythis",
    "nodejsdepth", "callbackhades", "promisebroke", "asyncawaitwhat",
    "generatorlazy", "iteratorspent", "decoratorbomb", "metaclassrage",
    "monkeypatcher", "ducktyperquack", "typeerrorage", "indexerroroof",
    "keyerrordict", "valueerrorhmm", "attrerrorobj", "importfailed",
    "circularimport", "dependencyhell", "vaborttrap", "virtualenvlost",
    "condaconflicts", "poetrylockfail", "pipxpathissue", "uvloopcrash",
    "gaborttrappy", "regexcatastro", "unicodehorror", "encodingfury",
    "bytesvsstrs", "pickleexplode", "marshalbroken", "jsondecodeerr",
    "yamlaborttrap", "tomlaborttrap", "iniaborttrap", "xmlaborttrap",
    "csvdialectwho", "parquetcorrupt", "avroschemaold", "protomismatch",
]

# ---------------------------------------------------------------------------
# 20 TLDs
# ---------------------------------------------------------------------------
TLDS = [
    "com", "net", "org", "io", "dev", "cloud", "network", "systems",
    "tech", "zone", "digital", "link", "host", "site", "online",
    "de", "uk", "nl", "cc", "me",
]

# ---------------------------------------------------------------------------
# 4 record-set templates
# ---------------------------------------------------------------------------

def _google_workspace(domain):
    """Set 1 — Google Workspace (6 records)."""
    return "Google Workspace", [
        ("", "MX", 3600, [
            "1 aspmx.l.google.com.",
            "5 alt1.aspmx.l.google.com.",
            "5 alt2.aspmx.l.google.com.",
            "10 alt3.aspmx.l.google.com.",
            "10 alt4.aspmx.l.google.com.",
        ]),
        ("", "TXT", 3600, ['"v=spf1 include:_spf.google.com ~all"']),
        ("mail", "CNAME", 3600, ["ghs.googlehosted.com."]),
        ("calendar", "CNAME", 3600, ["ghs.googlehosted.com."]),
        ("drive", "CNAME", 3600, ["ghs.googlehosted.com."]),
        ("", "CAA", 3600, ['0 issue "letsencrypt.org"']),
    ]


def _basic_web(domain):
    """Set 2 — Basic Web Hosting (4 records)."""
    return "Basic Web Hosting", [
        ("", "A", 3600, ["93.184.216.34"]),
        ("", "AAAA", 3600, ["2001:db8::1"]),
        ("www", "CNAME", 3600, [f"{domain}."]),
        ("", "TXT", 3600, ['"v=spf1 -all"']),
    ]


def _mail_web(domain):
    """Set 3 — Mail + Web (5 records)."""
    return "Mail + Web", [
        ("", "A", 3600, ["198.51.100.10"]),
        ("www", "CNAME", 3600, [f"{domain}."]),
        ("", "MX", 3600, [f"10 mail.{domain}."]),
        ("mail", "A", 3600, ["198.51.100.11"]),
        ("", "TXT", 3600, ['"v=spf1 mx -all"']),
    ]


def _srv_caa(domain):
    """Set 4 — SRV + CAA (5 records)."""
    return "SRV + CAA", [
        ("", "A", 3600, ["203.0.113.50"]),
        ("", "AAAA", 3600, ["2001:db8:1::50"]),
        ("www", "CNAME", 3600, [f"{domain}."]),
        ("", "TXT", 3600, ['"v=spf1 include:mailgun.org ~all"']),
        ("", "CAA", 3600, [
            '0 issue "letsencrypt.org"',
            '0 issuewild "letsencrypt.org"',
        ]),
    ]


RECORD_SETS = [_google_workspace, _basic_web, _mail_web, _srv_caa]

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Bulk-create sample DNS zones with records via the deSEC API.",
    )
    p.add_argument(
        "--count", type=int, default=10,
        help="Number of domains to create (default: 10)",
    )
    p.add_argument(
        "--profile", type=str, default="test",
        help='User profile name (default: "test")',
    )
    p.add_argument(
        "--rate-limit", type=float, default=2.0,
        help="Seconds between API calls (default: 2.0)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be created without calling the API",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    if args.count < 1:
        print("Error: --count must be at least 1")
        sys.exit(1)
    if args.count > len(DOMAIN_NAMES):
        print(f"Error: --count cannot exceed {len(DOMAIN_NAMES)} (available names)")
        sys.exit(1)

    # ── Bootstrap profile & API client ─────────────────────────
    pm = ProfileManager()
    if not pm.switch_to_profile(args.profile):
        print(f"Error: could not switch to profile '{args.profile}'")
        print("Available profiles:", ", ".join(
            p["name"] for p in pm.get_available_profiles()
        ))
        sys.exit(1)

    config_manager = pm.get_config_manager()
    if config_manager is None:
        print("Error: could not get config manager for profile")
        sys.exit(1)

    api_client = APIClient(config_manager)

    if not args.dry_run:
        if not api_client.check_connectivity():
            print("Error: API connectivity check failed — verify token and network")
            sys.exit(1)
        print("API connectivity OK\n")

    # ── Pick domains ───────────────────────────────────────────
    names = list(DOMAIN_NAMES)
    random.shuffle(names)
    selected = names[: args.count]

    results = []  # (domain, set_name, n_records, success)

    for i, name in enumerate(selected, 1):
        tld = random.choice(TLDS)
        domain = f"{name}.{tld}"
        set_fn = random.choice(RECORD_SETS)
        set_name, records = set_fn(domain)

        prefix = f"[{i}/{args.count}]"

        if args.dry_run:
            print(f"{prefix} {domain}  ({set_name}, {len(records)} records)")
            for subname, rtype, ttl, content in records:
                sub_display = subname if subname else "(apex)"
                print(f"       {sub_display:12s}  {rtype:6s}  {ttl}  {content}")
            results.append((domain, set_name, len(records), True))
            continue

        # Create zone
        ok, resp = api_client.create_zone(domain)
        if not ok:
            err = resp if isinstance(resp, str) else str(resp)
            if "409" in err or "already" in err.lower() or "exists" in err.lower():
                print(f"{prefix} {domain}  — zone already exists, skipping")
                results.append((domain, set_name, 0, False))
                time.sleep(args.rate_limit)
                continue
            else:
                print(f"{prefix} {domain}  — zone creation failed: {err}")
                results.append((domain, set_name, 0, False))
                time.sleep(args.rate_limit)
                continue

        # Create records
        rec_ok = 0
        for subname, rtype, ttl, content in records:
            time.sleep(args.rate_limit)
            ok, resp = api_client.create_record(domain, subname, rtype, ttl, content)
            if ok:
                rec_ok += 1
            else:
                err = resp if isinstance(resp, str) else str(resp)
                sub_display = subname if subname else "(apex)"
                print(f"       Warning: {sub_display} {rtype} failed: {err}")

        print(f"{prefix} {domain}  ({set_name}, {rec_ok}/{len(records)} records)")
        results.append((domain, set_name, rec_ok, True))

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)
    print(f"{'Domain':<36s} {'Record Set':<20s} {'Records':>7s}")
    print("-" * 64)
    for domain, set_name, n_records, ok in results:
        status = f"{n_records}" if ok else "SKIP"
        print(f"{domain:<36s} {set_name:<20s} {status:>7s}")
    total_ok = sum(1 for *_, ok in results if ok)
    total_rec = sum(n for _, _, n, ok in results if ok)
    print("-" * 64)
    mode = "DRY RUN" if args.dry_run else "CREATED"
    print(f"{mode}: {total_ok} zones, {total_rec} records total")


if __name__ == "__main__":
    main()
