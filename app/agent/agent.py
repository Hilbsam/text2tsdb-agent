# Diese Datei wurde mit der Dokumentation von https://python.langchain.com/docs/introduction/ und 
# https://langchain-ai.github.io/langgraph/concepts/why-langgraph/ erstellt.
# Selbstdefinierte Imports
import os
from typing import Literal
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import re
from agent.schema import arrivals, departures, station, trainnames, holidays, engine
from sqlalchemy import text
import pandas as pd
from types import SimpleNamespace

# Mit Hilfe der Dokumentation von LangGraph und Langchain geschrieben
from langgraph.types import Command
from langgraph.graph import StateGraph, MessagesState, START, END
from typing_extensions import TypedDict
from langchain_core.output_parsers import JsonOutputParser

mistral_model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
gemma_model = os.getenv("GOOGLE_MODEL", "gemma-3-27b-it")
openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")

class GraphState(TypedDict):
    messages: MessagesState
    question: str
    query: str
    data: dict
    config: dict
    answer: str
    error: str
    error_count: int
    intrepreted: bool


# Supervisor zum handeln ob Querry oder Interpretation gemacht werden soll
def supervisor(state: GraphState) -> Command[Literal["query_agent", "interpretation_agent", END]]:
    question = state["question"]
    try:
        data = state["data"]
    except:
        data = {}
    try:
        answer = state["answer"]
    except:
        answer = ""
    json_answer = """{'next_agent':'query_agent'} or {'next_agent':'interpretation_agent'} or {'next_agent':'__end__'}"""
    template = """You are a supervisor. Decide wether to create a query and get new data from the database or to interpret the data already available.\n\n
    Important there always should be an answer to the question. If the data is already available and the question is answered, then end the conversation.\n
    If the data is not available, then create a query and get the data from the database.\n
    If the data is available but the question is not answered, then interpret the data and answer the question.\n
    If the question is not answerable, then end the conversation.\n
    Question: {question}\n
    Data: {data}\n
    Answer: {answer}\n
    Decide wether to create a query and get new data from the database or to end if already everything is answered or to interpret the data already available.\n
    Answer with a json like {json_answer}.\n"""
    if state["config"]["model_query"] == "mistral":
        response = ChatMistralAI(
            model_name=mistral_model,
            temperature=0.15,
        ).invoke(template.format(question=question, data=data, answer=answer, json_answer=json_answer))
    elif state["config"]["model_query"] == "openai":
        response = ChatOpenAI(
            model=openai_model,
            temperature=0.15,
        ).invoke(template.format(question=question, data=data, answer=answer, json_answer=json_answer))
    elif state["config"]["model_query"] == "google":
        response = ChatGoogleGenerativeAI(
            model=gemma_model,
            temperature=0.15,
        ).invoke(template.format(question=question, data=data, answer=answer, json_answer=json_answer))
    else:
        raise ValueError("Unknown model for query agent")
    parser = JsonOutputParser()
    raw = response.content if hasattr(response, "content") else str(response)
    raw = raw.replace("'", '"')
    try:
        parsed_dict = parser.parse(raw)
        next_agent = parsed_dict["next_agent"]
    except Exception as e:
        return Command(goto="supervisor")

    return Command(goto=next_agent)

def query_agent(state: GraphState) -> Command[Literal["supervisor",  "query_agent", END]]:
    question = state["question"]
    try:
        query = state["query"]
    except:
        query = ""
    try:
        error = state["error"]
    except:
        error = ""
    template = f"""You are a query agent for a timescale database tsb15. You build a query base on the user question execute it and if nesseary correct errors in the query.
    The timescale database has the following tables in schema oebb: 
    - {arrivals.name}: {arrivals.columns._all_columns}
    - {departures.name}: {departures.columns._all_columns}
    - {station.name}: {station.columns._all_columns}
    - {trainnames.name}: {trainnames.columns._all_columns}
    - {holidays.name}: {holidays.columns._all_columns}
    Use if needed the timescale hypertable feature to query the data like time_bucket, time_bucket_gapfill, stats_agg(1D), stats_agg(2D), etc.
    The user question is: {question}
    The last query was: {query}
    The last error of that query was: {error}
    The query should be in english.
    The query should ONLY be a valid SQL query that can be executed on the timescale database directly.
    DO NOT add anything else to your response like explanations or comments.
    Additonall:
    - The arrivalstatus and departurestatus have following values: 'Ausfall', 'Neu' or Null. It does not contain anyother values. Only use them if nessecary.
    - arrivalmintues and departuremintues are the delay in minutes.
    """
    if state["config"]["model_query"] == "mistral":
        response = ChatMistralAI(
            model_name=mistral_model,
            temperature=0.15,
        ).invoke(template)
    elif state["config"]["model_query"] == "openai":
        response = ChatOpenAI(
            model=openai_model,
            temperature=0.15,
        ).invoke(template)
    elif state["config"]["model_query"] == "google":
        response = ChatGoogleGenerativeAI(
            model=gemma_model,
            temperature=0.15,
        ).invoke(template)
    elif state["config"]["model_query"] == "dryrun":
        response = SimpleNamespace(content="SELECT * FROM oebb.arrivals LIMIT 10; -- Das ist ein Testlauf. Die Antwort ist statisch und es wird kein LLM verwendet.")
    else:
        raise ValueError("Unknown model for query agent")
    
    m = re.search(r'```(?:\w+)?\s*(.*?)```', response.content, re.DOTALL)
    parsed_sql = m.group(1).strip() if m else response.content.strip()
    state["query"] = parsed_sql
    
    try:
        statements = [q.strip() for q in query.strip().split(';') if q.strip()]
        dfs = []
        timeout = 450000  # Timeout in Millisekunden (7,5 Minuten)
        with engine.connect() as conn:
            conn.execute(text(f"SET statement_timeout = {timeout}"))
            for stmt in statements:
                compiled = text(stmt).compile(bind=conn)
                df = pd.read_sql_query(compiled, con=conn)
                dfs.append(df)
        if not dfs:
            state["data"] = []
        combined_df = pd.concat(dfs, ignore_index=True)
        state["data"] = combined_df.to_dict(orient="records")
        if len(df) == 0:
            state["error"] = "The query returned no results."
            state["data"] = []
            try:
                state["error_count"] += 1
            except:
                state["error_count"] = 1
            if state["error_count"] > 3:
                return  Command(goto="interpretation_agent"), {'data': state["data"], 'question': state["question"], 'query': state["query"]}
            return Command(goto="query_agent"), {'data': state["data"], 'query': state["query"], 'error': state["error"], 'error_count': state["error_count"]}
    except Exception as e:
        state["error"] = str(e)
        state["data"] = []
        try:
            state["error_count"] += 1
        except:
            state["error_count"] = 1
        if state["error_count"] > 3:
            state["answer"] = "I encountered too many errors while trying to execute the query. Please try again later."
            return Command(goto=END)
        return Command(goto="query_agent"), {'data': state["data"], 'query': state["query"], 'error': state["error"], 'error_count': state["error_count"]}
    return Command(goto="supervisor"), {'data': state["data"], 'question': state["question"], 'query': state["query"]}
    
def interpretation_agent(state: GraphState) -> Command[Literal["supervisor"]]:
    template = f"""You are an interpretation agent for a timescale database tsb15. You interpret the data from the last query and answer the user question.
    Most delays in the data set are in minutes. Unless otherwise specified, assume that the data is in minutes.
    The data from the  query is: {state["data"]}
    The user question is: {state["question"]}
    The answer should be in the same language as the user question.
    """
    if state["config"]["model_interpret"] == "mistral":
        response = ChatMistralAI(
            model_name=mistral_model,
            temperature=0.15,
        ).invoke(template)
    elif state["config"]["model_interpret"] == "openai":
        response = ChatOpenAI(
            model=openai_model,
            temperature=0.15,
        ).invoke(template)
    elif state["config"]["model_interpret"] == "google":
        response = ChatGoogleGenerativeAI(
            model=gemma_model,
            temperature=0.15,
        ).invoke(template)
    elif state["config"]["model_interpret"] == "dryrun":
        response = SimpleNamespace(content="Das ist ein Testlauf. Die Antwort ist statisch und es wird kein LLM verwendet.")
    else:
        raise ValueError("Unknown model for query agent")
    state["answer"] = response.content
    return Command(goto="supervisor"), {'answer': state["answer"]}

# Graph Nodes definieren
def workflow():
    workflow = StateGraph(GraphState)
    workflow.add_node(supervisor)
    workflow.add_node(query_agent)
    workflow.add_node(interpretation_agent)
    # Graph Edges definieren
    workflow.add_edge(START, "supervisor")

    return workflow
