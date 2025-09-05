import sys
sys.path.append('../')
import pandas as pd
from app.agent.schema import engine
from sqlalchemy import text
from app.agent.agent import workflow
from dotenv import load_dotenv
from langfuse.langchain import CallbackHandler
from langchain.schema.runnable.config import RunnableConfig
from tqdm import tqdm

def load_excel_data(file_path: str) -> pd.DataFrame:
    """
    Lade eine Excel-Datei und gebe die Daten als DataFrame zurück.
    """
    return pd.read_excel(file_path, sheet_name="Questions")

def run_query(query:str, explain:bool=False):
    """
    Führe die gegebene SQL-Abfrage aus und gebe die Ergebnisse zurück. Falls explain=True, wird die Abfrage nicht ausgeführt, sondern mit EXPLAIN ANALYZE erklärt.
    """
    # Timeout in Millisekunden (7,5 Minuten)
    statement_timeout = 450000
    if explain:
        # Rüfen ob eine Abfrage mehrere SQL-Abfragen enthält
        # und diese dann einzeln ausführen
        query_splitted = query.replace('\n', ' ').rsplit('; ')
        if len(query_splitted) == 1:
            # Wenn nur eine Abfrage vorhanden ist, dann diese direkt ausgeführt werden
            prepared_query = f"EXPLAIN ANALYZE {query}"
            with engine.connect() as conn:
                conn.execute(text(f"SET statement_timeout = {statement_timeout}"))
                result = conn.execute(text(prepared_query)).fetchall()
            try:
                return  pd.DataFrame([{'plantime': float(result[-6][0].rsplit(':')[1].rsplit(' ')[1]), 'executiontime': float(result[-1][0].rsplit(':')[1].rsplit(' ')[1])}])
            except:
                try:
                    return pd.DataFrame([{'plantime': float(result[-2][0].rsplit(':')[1].rsplit(' ')[1]), 'executiontime': float(result[-1][0].rsplit(':')[1].rsplit(' ')[1])}])
                except:
                    raise ValueError("Could not parse the result of EXPLAIN ANALYZE. Please check the query syntax or the database connection.")
        else:
            # Wenn mehrere Abfragen vorhanden sind, dann werden diese einzeln ausgeführt und die gesamten Zeiten addiert
            plantime = []
            executiontime = []
            for i, q in enumerate(query_splitted):
                query = f"EXPLAIN ANALYZE {q}"
                with engine.connect() as conn:
                    conn.execute(text(f"SET statement_timeout = {statement_timeout}"))
                    result = conn.execute(text(query)).fetchall()
                plantime.append(float(result[-6][0].rsplit(':')[1].rsplit(' ')[1]))
                executiontime.append(float(result[-1][0].rsplit(':')[1].rsplit(' ')[1]))
            return pd.DataFrame([{'plantime': sum(plantime), 'executiontime': sum(executiontime)}])
    # Unterstützung für mehrere SQL-Abfragen: Query an Semikolon trennen und Ergebnisse zusammenführen
    statements = [q.strip() for q in query.strip().split(';') if q.strip()]
    dfs = []
    with engine.connect() as conn:
            # Timeout nach den statement_timeout setzen
            conn.execute(text(f"SET statement_timeout = {statement_timeout}"))
            for stmt in statements:
                compiled = text(stmt).compile(bind=conn)
                df = pd.read_sql_query(compiled, con=conn)
                dfs.append(df)
    if not dfs:
        return []
    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df.to_dict(orient="records")

def main():
    langfuse_handler = CallbackHandler()
    df = load_excel_data("../questions/questions.xlsx")
    print("Excel-Daten geladen:")
    print(df.head())
    
    # vereinfachung zur Abfrage ab wo angefangen werden soll
    df = df[df['OpenaiSQL'].isnull()]
    print(f"Anzahl der Fragen ohne GoldenDaten: {df.shape[0]}")
    
    for col in ['GoldenDaten','MistralSQL', 'MistralDaten', 'GoogleSQL', 'GoogleDaten', 'OpenaiSQL', 'OpenaiDaten']:
        df[col] = None
        df[col] = df[col].astype(object)
    graph = workflow().compile().with_config({"run_name": "T2TSDB-Agent"})
    for i, row in tqdm(df.iterrows(), total=df.shape[0], desc="Processing questions"):
        question = row['Frage']
        golden_query = row["GoldenSQL"]
        # die Golden Query ausführen

        data = run_query(golden_query, explain=False)
        df.at[i, 'GoldenDaten'] = data
        for x in tqdm(range(10), desc="GoldenSQL explain analyze runs", leave=False):
            temp_df = pd.DataFrame()
            time_result = run_query(golden_query, explain=True)
            temp_df = pd.concat([temp_df, time_result], ignore_index=True)
        df.at[i, 'GoldenExecutionTime'] = temp_df['executiontime'].mean()
        df.at[i, 'GoldenPlanTime'] = temp_df['plantime'].mean()
        for model in ['mistral','google','openai']:
            config = {
                "model_query": model,
                "model_interpret": "dryrun", "metadata": {
                    "langfuse_user_id": "admin",
                    "langfuse_session_id": "testing",
                }
            }
            invoked_graph = graph.invoke({'question': question, 'config':config}, RunnableConfig(callbacks=[langfuse_handler], **config))
            df.at[i, model.capitalize()+'SQL'] = invoked_graph['query']
            if len(invoked_graph['data']) == 0:
                df.at[i, model.capitalize()+'Daten'] = None
            else:
                df.at[i, model.capitalize()+'Daten'] = invoked_graph['data']
            try:
                for x in tqdm(range(10), desc=f"{model.capitalize()} explain analyze runs", leave=False):
                    temp_df = pd.DataFrame()
                    time_result = run_query(invoked_graph['query'], explain=True)
                    temp_df = pd.concat([temp_df, time_result], ignore_index=True)
                df.at[i, model.capitalize()+'ExecutionTime'] = temp_df['executiontime'].mean()
                df.at[i, model.capitalize()+'PlanTime'] = temp_df['plantime'].mean()
            except Exception as e:
                print(f"Error executing {model.capitalize()} query for question {question}: {e}")
                df.at[i, model.capitalize()+'ExecutionTime'] = None
                df.at[i, model.capitalize()+'PlanTime'] = None
                if df.at[i, model.capitalize()+'Daten'] is None:
                    df.at[i, model.capitalize()+'Daten'] = e
                continue
    # Speichern der Ergebnisse in einer Excel-Datei
        df.to_excel("../questions/results_time.xlsx", index=False, engine='openpyxl')
            
    


if __name__ == "__main__":
    load_dotenv('../app/.env')
    main()
    print("Ergebnisse gespeichert in ../questions/results_time.xlsx")
