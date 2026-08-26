from uuid import UUID


def owner_public_id(user, *, required: bool = True):
    if user is None:
        if required:
            raise ValueError('user_public_id is required')
        return None
    pid = getattr(user, 'public_id', None)
    if pid is None:
        if required:
            raise ValueError('user_public_id is required')
        return None
    if isinstance(pid, UUID):
        return pid
    return UUID(str(pid))
