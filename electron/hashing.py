from electron import settings


def hex_digest(obj: str) -> str:
    """
    Get the hexdigest of a string `obj` under the chosen hashing scheme.

    :param obj: <str> The object to be hashed
    :return: <str> hexdigest of `obj`
    """
    output = settings.HASH_ALGORITHM(obj.encode('utf-8')).hexdigest()
    return output if not settings.DEBUG else output[:8]
