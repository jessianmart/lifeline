"""Tier 0 do M3 — sync via GIT, custo zero. Reusa o fato (#0022) de que a view textual
(LIFELINE.md) é o artefato versionado e o `.db` é cache reconstruível: o git move o texto,
o content-addressing torna o merge tolerante a conflito (appends de lados diferentes
deduplicam por id na re-ingestão), e o GitHub vira o hub. Sem infra nova.

Estes são wrappers finos sobre o `git` (subprocess). A orquestração (rebuild antes do push,
migrate+rebuild depois do pull) vive na CLI.
"""
import subprocess


def _git(args, cwd="."):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def is_repo(cwd=".") -> bool:
    return _git(["rev-parse", "--is-inside-work-tree"], cwd).returncode == 0


def add_commit(cwd, message):
    _git(["add", "-A"], cwd)                       # .db é gitignored → só a view textual entra
    return _git(["commit", "-m", message], cwd)    # returncode != 0 se não houver nada a commitar


def push(cwd, remote="origin"):
    return _git(["push", remote, "HEAD"], cwd)


def pull(cwd, remote="origin"):
    return _git(["pull", "--no-edit", remote], cwd)


def clone(url, dest):
    return _git(["clone", url, dest])


def has_conflict(cwd=".") -> bool:
    """True se há arquivos com conflito de merge não resolvido."""
    r = _git(["diff", "--name-only", "--diff-filter=U"], cwd)
    return bool(r.stdout.strip())
