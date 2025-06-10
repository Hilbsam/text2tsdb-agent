from typing import Optional
import chainlit as cl
# 2vmQQ2FUcGCkrnWmtqnNF67tdyFXjCvS0FQfphmH
# 0iS2wrQ81HFnLtN2XN3GIsrHTQlcNOXBS1LjLr3e67mRcAjd0hdMpD0gJPiwVwngWbB9p08qP8EL6AUNMFzISVZrWJSXLyhUkr6yHp4t94Ad2S2NqRetF0NufuYM33RR

from typing import Dict, Optional
import chainlit as cl


@cl.oauth_callback
def oauth_callback(
  provider_id: str,
  token: str,
  raw_user_data: Dict[str, str],
  default_user: cl.User,
) -> Optional[cl.User]:
    print(provider_id)
    print(raw_user_data)
    return default_user


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    # Fetch the user matching username from your database
    # and compare the hashed password with the value stored in the database
    if (username, password) == ("admin", "admin"):
        return cl.User(
            identifier="admin", metadata={"role": "admin", "provider": "credentials"}
        )
    else:
        return None

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="We are Pied Piper!").send()