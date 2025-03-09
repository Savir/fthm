import bcrypt


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against a stored bcrypt hash."""
    if not plain_password:
        return False
    if not hash_password:
        return False
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
