def normalize_target_profile(value, target_profiles):
    profile_id = str(value or "generic")
    profile_ids = {str(item["id"]) for item in target_profiles}
    return profile_id if profile_id in profile_ids else "generic"


def get_target_profile_name(value, target_profiles):
    profile_id = normalize_target_profile(value, target_profiles)
    for item in target_profiles:
        if item["id"] == profile_id:
            return item["name"]
    return profile_id


def normalize_max_concurrent(value, default, limit):
    try:
        concurrent = int(value)
    except (TypeError, ValueError):
        concurrent = default
    return max(1, min(limit, concurrent))


def normalize_rounds(value, default, max_rounds):
    try:
        rounds = int(value)
    except (TypeError, ValueError):
        rounds = default
    return max(1, min(max_rounds, rounds))
