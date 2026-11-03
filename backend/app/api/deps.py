import uuid

TEMP_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    # Temporary: replaced by real login (Supabase Auth) later
    return TEMP_USER_ID