import sys
sys.path.append('../')
import pandas as pd
from app.agent.schema import arrivals, departures, station, trainnames, holidays
from dotenv import load_dotenv
from langfuse.langchain import CallbackHandler
from tqdm import tqdm
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

langfuse_handler = CallbackHandler()
def load_excel_data(file_path: str) -> pd.DataFrame:
    """
    Lade eine Excel-Datei und gebe die Daten als DataFrame zurück.
    """
    return pd.read_excel(file_path, sheet_name="Questions")

def call_reasoning_llm(question: str, goldenquery: list, generatedquery: list, model: str) -> str:
    """
    Rufe das reasoning LLM auf, um die Bewertung der Daten zu erhalten.
    :param question: Die Frage, die beantwortet werden soll.
    :param goldenquery: Die goldene SQL-Abfrage, die als Referenz dient.
    :param generatedquery: Die generierte SQL-Abfrage, die bewertet werden soll.
    :param model: Das Modell, das verwendet werden soll (mistral, openai, google).
    :return: Die Antwort des Modells.
    """
    template = """# TASK
- Given a natural-language Question, a database Schema with table/column definitions, a Golden SQL query, and a generated SQL query, evaluate how well the generated query matches the intended semantics.
- The Database is a timescale database tsb15.
- Assign a score from 1 (completely incorrect or irrelevant) to 5 (perfect match) based on:
  1. Semantic correctness (does it return the same result set?).
  2. Use of schema elements (correct tables/joins/columns).
  3. Handling of edge cases (e.g. NULLs, filters).
  4. Any extra insights or improvements (e.g. clearer logic, better aggregation).
  5. Use of timescale-specific features (e.g. time-series functions, continuous aggregates).
- If the generated query is completely off-mark, give 1.
- If it matches the golden query in all respects, give 5.
- Provide a brief justification (“reasoning”) that cites the main strengths or flaws of the generated query.

# INPUT
Question:
{question}

schema of oebb: 
- {arrivals.name}: {arrivals.columns._all_columns}
- {departures.name}: {departures.columns._all_columns}
- {station.name}: {station.columns._all_columns}
- {trainnames.name}: {trainnames.columns._all_columns}
- {holidays.name}: {holidays.columns._all_columns}

Golden Query:
```sql
{goldenquery}```

Generated Query:
```sql
{generated_query}```

# EXPECTED OUTPUT FORMAT (JSON-like)
{json_output}"""
    formated_template = template.format(
        question=question,
        goldenquery=goldenquery,
        generated_query=generatedquery,
        arrivals=arrivals,
        departures=departures,
        station=station,
        trainnames=trainnames,
        holidays=holidays,
        json_output="""{"score": <1-5>,
        "reasoning": "<Brief, explanation for the assigned scores>"
        }"""
    )
    if model == "mistral":
        response = ChatMistralAI(
            model_name="magistral-medium-latest",
            timeout=600
        ).invoke(formated_template, config={"callbacks": [langfuse_handler],"metadata": {
            "langfuse_user_id": "admin",
            "langfuse_session_id": "SQLsemantic_reasoning",
        }})
        scoring = json.loads(response.content[1]['text'].replace('```json', '').replace('```', ''))
    elif model == "openai":
        response = ChatOpenAI(
            model="&-2025-04-16",
            temperature=1
        ).invoke(formated_template, config={"callbacks": [langfuse_handler],"metadata": {
            "langfuse_user_id": "admin",
            "langfuse_session_id": "SQLsemantic_reasoning",
        }})
        scoring = json.loads(response.content.replace('```json', '').replace('```', ''))
    elif model == "google":
        response = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
        ).invoke(formated_template, config={"callbacks": [langfuse_handler],"metadata": {
            "langfuse_user_id": "admin",
            "langfuse_session_id": "SQLsemantic_reasoning",
        }})
        scoring = json.loads(response.content.replace('```json', '').replace('```', ''))
    else:
        raise ValueError(f"Unsupported model: {model}")
    
    return scoring

def main():
    df = load_excel_data("../questions/questions.xlsx")
    print("Excel-Daten geladen:")
    print(df.head())
    # vereinfachung zur Abfrage ab wo angefangen werden soll
    df = df[df['OpenaiSQLSemanticReasoning'].isnull()]
    print(f"Anzahl der Fragen ohne SemanticScoring: {df.shape[0]}")
    for col in ['MistralSQLSemanticVotes', 'GoogleSQLSemanticVotes', 'OpenaiSQLSemanticVotes',
                'MistralSQLSemanticScore', 'GoogleSQLSemanticScore', 'OpenaiSQLSemanticScore',
                'MistralSQLSemanticReasoning', 'GoogleSQLSemanticReasoning', 'OpenaiSQLSemanticReasoning']:
        df[col] = None
        df[col] = df[col].astype(object)
    
    
    for i, row in tqdm(df.iterrows(), total=df.shape[0], desc="Processing questions"):
        question = row['Frage']
        goldensql = row["GoldenSQL"]
        ###for model in tqdm(['mistral', 'google', 'openai'], desc="Processing models", leave=False):
        ###    
        ###    query = row[model.capitalize() + 'SQL']
        ###    score = []
        ###    reasoning_scores = []
        ###    for model in ['mistral', 'google', 'openai']:  
        ###        control_list = []
        ###        while len(control_list) < 5:
        ###            try:
        ###                model_score = call_reasoning_llm(question, goldensql, query, model)
        ###                control_list.append(model_score['score'])
        ###                model_score['reasoning']
        ###                score.append(model_score['score'])
        ###                reasoning_scores.append(model_score['reasoning'])
        ###            except:
        ###                continue
        ###    df.at[i, model.capitalize() + 'SQLSemanticVotes'] = score
        ###    df.at[i, model.capitalize() + 'SQLSemanticScore'] = sum(score) / len(score) if score else 0
        ###    df.at[i, model.capitalize() + 'SQLSemanticReasoning'] = reasoning_scores
        for candidate in tqdm(['Mistral','Google','Openai'], desc="Processing candidate queries", leave=False):
            query = row[f"{candidate}SQL"]

            # init per‐model collectors
            reasoning_models = ['mistral','google','openai']
            scores_by_model     = {rm: [] for rm in reasoning_models}
            reasonings_by_model = {rm: [] for rm in reasoning_models}

            # fire off 5 calls per model in parallel
            with ThreadPoolExecutor(max_workers=len(reasoning_models)*2) as executor:
                futures = {
                    executor.submit(call_reasoning_llm, question, goldensql, query, rm): rm
                    for rm in reasoning_models
                    for _ in range(5)
                }
                for future in as_completed(futures):
                    rm = futures[future]
                    try:
                        res = future.result()
                        scores_by_model[rm].append(res['score'])
                        reasonings_by_model[rm].append(res['reasoning'])
                    except Exception:
                        # you can log here if you want
                        continue

            all_scores = [score for votes in scores_by_model.values() for score in votes]
            all_reasonings = [r for reasoning_list in reasonings_by_model.values() for r in reasoning_list]

            # write back into your df as flat lists
            df.at[i, f"{candidate}SQLSemanticVotes"] = all_scores
            df.at[i, f"{candidate}SQLSemanticScore"] = sum(all_scores)/len(all_scores) if all_scores else 0
            df.at[i, f"{candidate}SQLSemanticReasoning"] = all_reasonings
        # Speichern der Ergebnisse in einer Excel-Datei
        df.to_excel("../questions/results_sqlsemantic.xlsx", index=False, engine='openpyxl')

if __name__ == "__main__":
    load_dotenv('../app/.env')
    main()