"""Pure qualification matching. Requirements are explicit business facts."""


def has_required_skills(skills, requirements) -> bool:
    return set(requirements).issubset(set(skills))
