import time

from proxy_checker.responses import ok_response
from proxy_checker.storage.checked_store import read_checked_list, write_checked_list
from proxy_checker.storage.repo_store import (
    compact_repo,
    compact_repo_item,
    read_repo_data,
    save_repo_payload,
    write_repo_data,
)
from proxy_checker.utils import proxy_key, sanitize_token


def result_to_repo_item(result, existing=None):
    now = int(time.time() * 1000)
    existing = existing or {}
    country = result.get("country")
    checks_detail = result.get("checks_detail")
    if not country and isinstance(checks_detail, dict):
        ip_info = checks_detail.get("ip_info")
        if isinstance(ip_info, dict):
            country = ip_info.get("country")
    item = {
        "proxy": result.get("proxy") or result.get("original"),
        "grade": result.get("grade") or "F",
        "latency": result.get("latency"),
        "ip": result.get("ip"),
        "country": str(country).upper() if country else None,
        "ip_type": result.get("ip_type"),
        "service_reachable": result.get("service_reachable") is True,
        "api_reachable": result.get("api_reachable") is True,
        "cf_bypass": result.get("cf_bypass") is True,
        "recommended_use": result.get("recommended_use"),
        "target_profile": result.get("target_profile"),
        "target_name": result.get("target_name"),
        "added": existing.get("added") or now,
        "updated": now,
    }
    return compact_repo_item(item)


def result_matches_policy(result, policy):
    grade = str(result.get("grade") or "F").upper()
    if policy == "archive_all":
        return True
    if policy == "grade_a_only":
        return grade == "A"
    if policy == "grade_b_only":
        return grade == "B"
    if policy == "grade_ab_only":
        return grade in ("A", "B")
    if policy == "include_unstable":
        return grade in ("A", "B", "C", "D") or result.get("valid") or result.get("unstable")
    return grade in ("A", "B", "C") or result.get("valid")


def normalize_repo_grades(grades):
    return {
        str(grade).strip().upper()
        for grade in grades
        if str(grade).strip()
    }


def repo_item_matches_grades(item, grades):
    return str(item.get("grade") or "").upper() in normalize_repo_grades(grades)


def filter_repo_by_grades(repo, grades):
    allowed_grades = normalize_repo_grades(grades)
    return [
        item
        for item in compact_repo(repo)
        if repo_item_matches_grades(item, allowed_grades)
    ]


def merge_repo_results(token, repo, results, checked_inputs, policy, repo_update_policies):
    policy = policy if policy in repo_update_policies else "stable_only"
    participating = {proxy_key(proxy) for proxy in checked_inputs}
    result_by_key = {}
    for result in results:
        for value in (result.get("original"), result.get("proxy")):
            key = proxy_key(value)
            if key:
                result_by_key[key] = result

    existing_by_key = {}
    for item in compact_repo(repo):
        existing_by_key[proxy_key(item["proxy"])] = item

    removed = 0
    next_repo = []
    for item in compact_repo(repo):
        key = proxy_key(item["proxy"])
        result = result_by_key.get(key)
        if policy != "archive_all" and key in participating and result and not result_matches_policy(result, policy):
            removed += 1
            continue
        next_repo.append(item)

    index_by_key = {proxy_key(item["proxy"]): i for i, item in enumerate(next_repo)}
    added = 0
    updated = 0
    for result in results:
        if not result_matches_policy(result, policy):
            continue
        candidate_keys = [proxy_key(result.get("original")), proxy_key(result.get("proxy"))]
        existing = None
        existing_index = None
        for key in candidate_keys:
            if key in index_by_key:
                existing_index = index_by_key[key]
                existing = next_repo[existing_index]
                break
            if key in existing_by_key:
                existing = existing_by_key[key]
        item = result_to_repo_item(result, existing)
        if not item:
            continue
        if existing_index is None:
            next_repo.append(item)
            index_by_key[proxy_key(item["proxy"])] = len(next_repo) - 1
            added += 1
        else:
            next_repo[existing_index] = item
            index_by_key[proxy_key(item["proxy"])] = existing_index
            updated += 1

    saved = write_repo_data(token, next_repo)
    return {
        "repo_count": len(saved),
        "repo_added": added,
        "repo_updated": updated,
        "repo_removed": removed,
    }


class RepoService:
    def __init__(
        self,
        *,
        read_repo_func=read_repo_data,
        save_repo_func=save_repo_payload,
        write_repo_func=write_repo_data,
        read_checked_func=read_checked_list,
        write_checked_func=write_checked_list,
    ):
        self.read_repo = read_repo_func
        self.save_repo = save_repo_func
        self.write_repo = write_repo_func
        self.read_checked = read_checked_func
        self.write_checked = write_checked_func

    def repo_json(self, token):
        return self.read_repo(token)

    def repo_text(self, token):
        return "\n".join(item["proxy"] for item in self.read_repo(token))

    def checked_text(self, token):
        return "\n".join(self.read_checked(token))

    def save(self, data):
        repo_data = data.get("repo")
        proxies = data.get("proxies", [])
        token = sanitize_token(data.get("token", "default"))
        mode = data.get("mode", "merge")
        base_count = data.get("base_count")
        incoming = repo_data if repo_data is not None else [{"proxy": proxy} for proxy in proxies]

        saved, response = self.save_repo(token, incoming, mode, base_count)
        if saved is None:
            return response
        response["url"] = f"/api/repo/{token}.json" if repo_data is not None else f"/api/repo/{token}.txt"
        return response

    def load(self, data):
        token = sanitize_token(data.get("token", "default"))
        repo = self.read_repo(token)
        return {"repo": repo, "count": len(repo)}

    def clear(self, data):
        token = sanitize_token(data.get("token", "default"))
        self.write_repo(token, [])
        return ok_response(count=0)

    def save_checked(self, data):
        token = sanitize_token(data.get("token", "default"))
        saved = self.write_checked(token, data.get("proxies", []))
        return ok_response(count=len(saved))

    def filter_checked(self, data):
        token = sanitize_token(data.get("token", "default"))
        proxies = data.get("proxies", [])
        checked_set = {proxy_key(proxy) for proxy in self.read_checked(token)}
        unchecked = [proxy for proxy in proxies if proxy_key(proxy) not in checked_set]
        return {
            "unchecked": unchecked,
            "skipped": len(proxies) - len(unchecked),
            "total": len(proxies),
            "checked_count": len(checked_set),
        }
