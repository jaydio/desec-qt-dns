#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Git-based zone versioning for DNS record changes.

Every record mutation (create / update / delete) produces a git commit
in a local repository at ~/.config/desecqt/versions/.  This gives the
user a full undo / restore history per zone without any external
dependencies beyond the git CLI.
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SAFE_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9._-]+$')

_VERSIONS_DIR = os.path.join(os.path.expanduser("~/.config/desecqt"), "versions")


class VersionManager:
    """Lightweight git-backed zone version history."""

    def __init__(self, base_dir: str = _VERSIONS_DIR):
        self._base = Path(base_dir)
        self._zones_dir = self._base / "zones"
        self._init_repo()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_domain(domain_name: str) -> None:
        """Raise ValueError if domain_name contains unsafe path characters."""
        if not domain_name or not _SAFE_DOMAIN_RE.match(domain_name):
            raise ValueError(f"Invalid domain name for versioning: {domain_name!r}")

    def snapshot(self, domain_name: str, records: List[Dict[str, Any]], message: str) -> bool:
        """Write zone records to JSON and commit.

        Args:
            domain_name: The zone name (e.g. "example.com")
            records: List of record dicts as returned by the API
            message: Human-readable commit message

        Returns:
            True if a commit was created, False if nothing changed.
        """
        self._validate_domain(domain_name)
        if not records:
            return False

        zone_file = self._zone_path(domain_name)
        zone_file.parent.mkdir(parents=True, exist_ok=True)

        # Write pretty-printed JSON
        payload = json.dumps(records, indent=2, sort_keys=True, default=str)
        zone_file.write_text(payload, encoding="utf-8")

        # Stage and commit
        self._git("add", str(zone_file.relative_to(self._base)))
        rc = self._git("diff", "--cached", "--quiet")
        if rc == 0:
            logger.debug("No changes to commit for %s", domain_name)
            return False

        self._git("commit", "-m", f"[{domain_name}] {message}")
        logger.info("Version snapshot: [%s] %s", domain_name, message)
        return True

    def get_history(self, domain_name: str, limit: int = 50) -> List[Dict[str, str]]:
        """Return commit history for a zone file.

        Returns a list of dicts with keys: hash, date, message.
        """
        self._validate_domain(domain_name)
        rel = self._zone_rel(domain_name)
        out = self._git_output(
            "log", f"--max-count={limit}",
            "--format=%H|%aI|%s",
            "--", rel,
        )
        if not out:
            return []

        history = []
        for line in out.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                history.append({
                    "hash": parts[0],
                    "date": parts[1],
                    "message": parts[2],
                })
        return history

    def get_version(self, domain_name: str, commit_hash: str) -> List[Dict[str, Any]]:
        """Return the zone records from a specific commit."""
        self._validate_domain(domain_name)
        rel = self._zone_rel(domain_name)
        out = self._git_output("show", f"{commit_hash}:{rel}")
        if not out:
            return []
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            logger.error("Failed to parse version %s for %s", commit_hash, domain_name)
            return []

    def restore(self, domain_name: str, commit_hash: str) -> List[Dict[str, Any]]:
        """Return records from a historical version for the caller to push to the API.

        This is intentionally read-only — the caller is responsible for
        pushing the restored records through the API queue.
        """
        return self.get_version(domain_name, commit_hash)

    def delete_zone_history(self, domain_name: str) -> bool:
        """Remove a zone's version history file and commit the deletion.

        Returns True if the file was removed, False if it didn't exist.
        """
        self._validate_domain(domain_name)
        zone_file = self._zone_path(domain_name)
        if not zone_file.exists():
            return False

        rel = self._zone_rel(domain_name)
        self._git("rm", "-f", rel)
        self._git("commit", "-m", f"[{domain_name}] Delete version history")
        logger.info("Deleted version history for %s", domain_name)
        return True

    def list_versioned_zones(self) -> List[str]:
        """Return a list of domain names that have version history."""
        if not self._zones_dir.exists():
            return []
        return sorted(
            p.stem for p in self._zones_dir.glob("*.json")
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _zone_path(self, domain_name: str) -> Path:
        return self._zones_dir / f"{domain_name}.json"

    def _zone_rel(self, domain_name: str) -> str:
        return f"zones/{domain_name}.json"

    def _init_repo(self):
        """Initialise the git repo if it doesn't exist yet."""
        self._base.mkdir(parents=True, exist_ok=True)
        git_dir = self._base / ".git"
        if not git_dir.exists():
            self._git("init")
            self._git("config", "user.name", "deSEC Qt DNS Manager")
            self._git("config", "user.email", "desecqt@localhost")
            # Initial empty commit so log never fails on an empty repo
            self._git("commit", "--allow-empty", "-m", "Init version history")
            logger.info("Initialised version repo at %s", self._base)

    def _git(self, *args: str) -> int:
        """Run a git command in the versions directory. Returns the exit code."""
        cmd = ["git", "-C", str(self._base)] + list(args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 and "nothing to commit" not in result.stdout:
                logger.debug("git %s → %d: %s", " ".join(args), result.returncode, result.stderr.strip())
            return result.returncode
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("git command failed: %s", exc)
            return 1

    def _git_output(self, *args: str) -> Optional[str]:
        """Run a git command and return its stdout, or None on failure."""
        cmd = ["git", "-C", str(self._base)] + list(args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("git command failed: %s", exc)
            return None
