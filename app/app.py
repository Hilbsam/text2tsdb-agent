# Diese Datei wurde mit der Dokumentation von https://docs.chainlit.io/get-started/overview, 
# https://langfuse.com/integrations/frameworks/langchain und 
# https://langchain-ai.github.io/langgraph/concepts/memory/ erstellt.

import chainlit as cl
from typing import Dict, Optional
from agent.agent import workflow
from langchain.schema.runnable.config import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import os
from helpers.chainlit_settings import settings_list
from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler()
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
@cl.on_settings_update
async def update_state_by_settings(settings: cl.ChatSettings):
    state = cl.user_session.get("state")
    state["config"] = settings
    cl.user_session.set("state", state)
    
@cl.on_chat_start
async def on_chat_start():

    settings = await cl.ChatSettings(
        settings_list
    ).send()
    cl.user_session.set("state", {"question": "", "generation": "","config": settings})
    cl.user_session.set("runnable", workflow())
    
    
@cl.on_message
async def on_message(message: cl.Message):
    runnable = cl.user_session.get("runnable")
    msg = cl.Message(content="")
    async with AsyncPostgresSaver.from_conn_string(os.environ.get("DATABASE_URL")) as checkpointer:
        graph = runnable.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": cl.context.session.thread_id}, "metadata": {
            "langfuse_user_id": cl.context.session.user.identifier,
            "langfuse_session_id": cl.context.session.thread_id,
        }}
        config = {**config, **cl.user_session.get("state")["config"]}
        cb = cl.LangchainCallbackHandler(
                to_ignore=["ChannelRead", "RunnableLambda", "ChannelWrite", "__start__", "_execute", "call_model"])
        async for chunk in graph.astream_events({"question": message.content, "config": config}, config=RunnableConfig(callbacks=[cb, langfuse_handler], **config),
                                         stream_mode="chunk", version="v2"):               
            try:
                if chunk["metadata"]["langgraph_node"] == "interpretation_agent" and chunk["event"] == "on_chat_model_stream":
                    
                    await msg.stream_token(chunk["data"]["chunk"].content)
            except:
                pass
        await msg.send()
    

if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)