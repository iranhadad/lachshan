CANONICAL_ENTITY_MAP = {
    "רבין": "יצחק רבין",
    "יצחק רבין": "יצחק רבין",
    "בגין": "מנחם בגין",
    "מנחם בגין": "מנחם בגין",
    "בן גוריון": "דוד בן גוריון",
    "דוד בן גוריון": "דוד בן גוריון",
    "הרצל": "בנימין זאב הרצל",
    "בנימין זאב הרצל": "בנימין זאב הרצל",
}


BIRTH_YEAR_FACTS = {
    "יצחק רבין": "1922",
    "מנחם בגין": "1913",
    "דוד בן גוריון": "1886",
    "בנימין זאב הרצל": "1860",
}


def normalize_entity_name(name: str) -> str:
    return " ".join(name.strip().split())


def get_canonical_entity_name(name: str) -> str | None:
    normalized = normalize_entity_name(name)
    return CANONICAL_ENTITY_MAP.get(normalized)


def lookup_birth_year(entity_name: str) -> str | None:
    canonical_name = get_canonical_entity_name(entity_name)
    if not canonical_name:
        return None
    return BIRTH_YEAR_FACTS.get(canonical_name)