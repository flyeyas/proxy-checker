"""Migrate v1 storage layout (repo_data/, checked_data/, auto_data/, logs/<token>.json)
to v2 tenant directory layout (data/<token>/{repo.json,repo.txt,checked.txt,auto.json,runs.json}).

The migration is idempotent: a tenant directory containing any of the target
files is skipped. The legacy directories are NEVER touched by this routine —
operators run ``--purge`` manually after verifying that the application works
on the new layout.
"""

import argparse
import os
import shutil

from proxy_checker.config import (
    BASE_DIR,
    DATA_DIR,
    LEGACY_AUTO_DIR,
    LEGACY_CHECKED_DIR,
    LEGACY_REPO_DIR,
    LEGACY_RUNS_DIR,
)
from proxy_checker.storage.paths import tenant_dir_path


TENANT_FILES = ("repo.json", "repo.txt", "checked.txt", "auto.json", "runs.json")


def _is_safe_token_name(base):
    return bool(base) and base.replace("_", "").isalnum()


def list_legacy_tokens(
    *,
    repo_dir=None,
    checked_dir=None,
    auto_dir=None,
    runs_dir=None,
):
    sources = (
        (repo_dir or LEGACY_REPO_DIR, ".json"),
        (repo_dir or LEGACY_REPO_DIR, ".txt"),
        (checked_dir or LEGACY_CHECKED_DIR, ".txt"),
        (auto_dir or LEGACY_AUTO_DIR, ".json"),
        (runs_dir or LEGACY_RUNS_DIR, ".json"),
    )
    tokens = set()
    for directory, ext in sources:
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            base, file_ext = os.path.splitext(name)
            if file_ext != ext:
                continue
            if not _is_safe_token_name(base):
                continue
            tokens.add(base)
    return sorted(tokens)


def _tenant_dir_has_data(new_dir):
    if not os.path.isdir(new_dir):
        return False
    return any(os.path.isfile(os.path.join(new_dir, name)) for name in TENANT_FILES)


def _copy_if_exists(src, dst):
    if not os.path.isfile(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def migrate_tenant(
    token,
    *,
    data_dir=None,
    repo_dir=None,
    checked_dir=None,
    auto_dir=None,
    runs_dir=None,
):
    if not _is_safe_token_name(token):
        return "invalid_token"

    data_dir = data_dir or DATA_DIR
    repo_dir = repo_dir or LEGACY_REPO_DIR
    checked_dir = checked_dir or LEGACY_CHECKED_DIR
    auto_dir = auto_dir or LEGACY_AUTO_DIR
    runs_dir = runs_dir or LEGACY_RUNS_DIR

    new_dir = tenant_dir_path(data_dir, token)
    if _tenant_dir_has_data(new_dir):
        return "skipped"

    os.makedirs(new_dir, exist_ok=True)
    plan = (
        (os.path.join(repo_dir, f"{token}.json"), os.path.join(new_dir, "repo.json")),
        (os.path.join(repo_dir, f"{token}.txt"), os.path.join(new_dir, "repo.txt")),
        (os.path.join(checked_dir, f"{token}.txt"), os.path.join(new_dir, "checked.txt")),
        (os.path.join(auto_dir, f"{token}.json"), os.path.join(new_dir, "auto.json")),
        (os.path.join(runs_dir, f"{token}.json"), os.path.join(new_dir, "runs.json")),
    )
    migrated_any = False
    for src, dst in plan:
        if _copy_if_exists(src, dst):
            migrated_any = True

    if not migrated_any:
        try:
            os.rmdir(new_dir)
        except OSError:
            pass
        return "no_legacy"
    return "migrated"


def needs_migration(
    *,
    data_dir=None,
    repo_dir=None,
    checked_dir=None,
    auto_dir=None,
    runs_dir=None,
):
    tokens = list_legacy_tokens(
        repo_dir=repo_dir,
        checked_dir=checked_dir,
        auto_dir=auto_dir,
        runs_dir=runs_dir,
    )
    if not tokens:
        return False
    data_dir = data_dir or DATA_DIR
    for token in tokens:
        new_dir = tenant_dir_path(data_dir, token)
        if not _tenant_dir_has_data(new_dir):
            return True
    return False


def run(
    *,
    dry_run=False,
    data_dir=None,
    repo_dir=None,
    checked_dir=None,
    auto_dir=None,
    runs_dir=None,
):
    tokens = list_legacy_tokens(
        repo_dir=repo_dir,
        checked_dir=checked_dir,
        auto_dir=auto_dir,
        runs_dir=runs_dir,
    )
    data_dir = data_dir or DATA_DIR
    results = {}
    for token in tokens:
        if dry_run:
            new_dir = tenant_dir_path(data_dir, token)
            results[token] = "skipped" if _tenant_dir_has_data(new_dir) else "would_migrate"
        else:
            results[token] = migrate_tenant(
                token,
                data_dir=data_dir,
                repo_dir=repo_dir,
                checked_dir=checked_dir,
                auto_dir=auto_dir,
                runs_dir=runs_dir,
            )
    return results


def purge_legacy(
    *,
    repo_dir=None,
    checked_dir=None,
    auto_dir=None,
    runs_dir=None,
):
    repo_dir = repo_dir or LEGACY_REPO_DIR
    checked_dir = checked_dir or LEGACY_CHECKED_DIR
    auto_dir = auto_dir or LEGACY_AUTO_DIR
    runs_dir = runs_dir or LEGACY_RUNS_DIR

    removed = []
    for directory in (repo_dir, checked_dir, auto_dir):
        if os.path.isdir(directory):
            shutil.rmtree(directory)
            removed.append(directory)

    if os.path.isdir(runs_dir):
        for name in os.listdir(runs_dir):
            base, ext = os.path.splitext(name)
            if ext == ".json" and _is_safe_token_name(base):
                path = os.path.join(runs_dir, name)
                if os.path.isfile(path):
                    os.remove(path)
                    removed.append(path)
    return removed


def maybe_run_migration(*, logger=None, **kwargs):
    try:
        if not needs_migration(**kwargs):
            return None
    except OSError as exc:
        if logger:
            logger.warning("Storage migration probe failed: %s", exc)
        return None

    if logger:
        logger.info("Detected legacy storage layout, running migration")
    try:
        results = run(**kwargs)
    except OSError as exc:
        if logger:
            logger.warning("Storage migration failed: %s", exc)
        return None
    if logger:
        migrated = [t for t, status in results.items() if status == "migrated"]
        skipped = [t for t, status in results.items() if status == "skipped"]
        logger.info(
            "Storage migration completed: %d migrated, %d skipped",
            len(migrated),
            len(skipped),
        )
    return results


def _cli():
    parser = argparse.ArgumentParser(
        prog="python -m proxy_checker.migrate.v1_to_v2",
        description="Migrate v1 storage layout to v2 tenant directory layout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the migration plan without writing anything",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Remove legacy repo_data/, checked_data/, auto_data/ directories and "
             "logs/<token>.json files (run only after verifying the new layout)",
    )
    args = parser.parse_args()

    if args.purge:
        removed = purge_legacy()
        if not removed:
            print("Nothing to purge.")
        for path in removed:
            print(f"removed: {os.path.relpath(path, BASE_DIR)}")
        return

    results = run(dry_run=args.dry_run)
    if not results:
        print("No legacy tokens found.")
        return
    for token, status in results.items():
        print(f"{token}: {status}")


if __name__ == "__main__":
    _cli()
