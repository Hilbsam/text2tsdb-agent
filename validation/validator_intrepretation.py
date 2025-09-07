import sys
sys.path.append('../')
import pandas as pd
from app.agent.agent import workflow
from dotenv import load_dotenv
from langfuse.langchain import CallbackHandler
from langchain.schema.runnable.config import RunnableConfig
from tqdm import tqdm
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import json

def load_excel_data(file_path: str) -> pd.DataFrame:
    """
    Lade eine Excel-Datei und gebe die Daten als DataFrame zurück.
    """
    return pd.read_excel(file_path, sheet_name="Questions")

def call_reasoning_llm(question: str, daten: list, interpreation: list, model: str) -> str:
    """
    Rufe das reasoning LLM auf, um die Bewertung der Daten zu erhalten.
    :param question: Die Frage, die beantwortet werden soll.
    :param daten: Die Daten, die bewertet werden sollen.
    :param model: Das Modell, das verwendet werden soll (mistral, openai, google).
    :param interpreation: Die Interpretation der Daten von Google, Openai und Mistral.
    :return: Die Antwort des Modells.
    """
    template = """# TASK
- For each of the three texts, assign a score from 1 (least relevant) to 5 (most relevant) with respect to the Question and the Data. Then provide a short explanation for your scoring.
- If a text is not relevant or completly missed the mark, assign a score of 1.
- If a text is relevant, assign a score based on its relevance.
- If a text has additonal information/insights and it fits in (e.g. min and max values), add it positly to the score.
- The scores should reflect the relevance of each text to the question and data provided.
- You can give the same score to multiple texts if you find them equally relevant or irrelevant.
- The reasoning should be short, concise and directly related to the scores assigned.
- The output should be in JSON format with the scores and reasoning.
- Most delays in the data set are in minutes. Unless otherwise specified, assume that the data is in minutes.

# INPUT
Question: {question}
Data: {daten}

Texts to Evaluate:
1. text1: {interpreation[0]}
2. text2: {interpreation[1]}
3. text3: {interpreation[2]}

# EXPECTED OUTPUT FORMAT (JSON-like)
{json_output}"""
    formated_template = template.format(
        question=question,
        daten=daten,
        interpreation=interpreation,
        json_output="""{
  "scores": {
    "text1": <1-5>,
    "text2": <1-5>,
    "text3": <1-5>
  },
  "reasoning": "<Brief, explanation for the assigned scores>"
}"""
    )
    if model == "mistral":
        response = ChatMistralAI(
            model_name="magistral-medium-latest",
            timeout=600
        ).invoke(formated_template)
        scoring = json.loads(response.content[1]['text'].replace('```json', '').replace('```', ''))
    elif model == "openai":
        response = ChatOpenAI(
            model="o4-mini-2025-04-16",
            temperature=1
        ).invoke(formated_template)
        scoring = json.loads(response.content.replace('```json', '').replace('```', ''))
    elif model == "google":
        response = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
        ).invoke(formated_template)
        scoring = json.loads(response.content.replace('```json', '').replace('```', ''))
    else:
        raise ValueError(f"Unsupported model: {model}")
    
    return scoring

def main():
    df = load_excel_data("../questions/questions.xlsx")
    print("Excel-Daten geladen:")
    print(df.head())
    # check if the columns exist, if not create them
    if 'Reasoning' not in df.columns:
        for new_col in ['Mistral', 'Google', 'Openai']:
            df[new_col + 'Interpretation'] = None
            df[new_col + 'Votes'] = None
            df[new_col + 'Score'] = None
        df['Reasoning'] = None
    # vereinfachung zur Abfrage ab wo angefangen werden soll
    df = df[df['Reasoning'].isnull()]
    print(df)
    
    graph = workflow().compile().with_config({"run_name": "T2TSDB-Agent"})
    langfuse_handler = CallbackHandler()
    for i, row in tqdm(df.iterrows(), total=df.shape[0], desc="Processing questions"):
        question = row['Frage']
        goldendaten = row["GoldenDaten"]
        # Ausführen der Intrepretation von den Golden Daten
        intrepretation = []
        try:
            for model in ['mistral', 'google', 'openai']:
                config = {
                            "model_query": "dryrun",
                            "model_interpret": model, 
                            "metadata": {
                                "langfuse_user_id": "admin",
                                "langfuse_session_id": "testing",
                            }
                        }
                invoked_awnser = None
                while invoked_awnser is None:
                    try:
                        invoked_awnser = graph.invoke({'question': question, 'data': goldendaten, 'config': config},
                                                     RunnableConfig(callbacks=[langfuse_handler], **config))['answer']
                    except Exception as e:
                        print(f"Error invoking graph for question {question} with model {model}: {e}")
                        continue
                intrepretation.append(invoked_awnser)
                df.at[i, model.capitalize() + 'Interpretation'] = invoked_awnser
        except Exception as e:
            print(f"Error invoking graph for question {question} with model {model}: {e}")
            df.at[i, model.capitalize() + 'Interpretation'] = None
            continue
        mistral_score = []
        google_score = []
        openai_score = []
        reasoning_scores = []
        for model in ['mistral', 'google', 'openai']:
            control_list = []
            while len(control_list) < 5:
                try:
                    model_score = call_reasoning_llm(question, goldendaten, intrepretation, model)
                    control_list.append(model_score['scores']['text1'] + model_score['scores']['text2'] + model_score['scores']['text3'])
                    model_score['reasoning'] 
                    mistral_score.append(model_score['scores']['text1'])
                    google_score.append(model_score['scores']['text2'])
                    openai_score.append(model_score['scores']['text3'])
                    reasoning_scores.append(model_score['reasoning'])
                except Exception as e:
                    print(f"Error calling reasoning llm for question {question} with model {model}: {e}")
                    continue
        df.at[i, 'MistralVotes'] = mistral_score
        df.at[i, 'GoogleVotes'] = google_score
        df.at[i, 'OpenaiVotes'] = openai_score
        df.at[i, 'MistralScore'] = sum(mistral_score) / len(mistral_score) if mistral_score else None
        df.at[i, 'GoogleScore'] = sum(google_score) / len(google_score) if google_score else None
        df.at[i, 'OpenaiScore'] = sum(openai_score) / len(openai_score) if openai_score else None
        df.at[i, 'Reasoning'] = reasoning_scores
        # Speichern der Ergebnisse in einer Excel-Datei
        df.to_excel("../questions/results_intrepretation.xlsx", index=False, engine='openpyxl')         

if __name__ == "__main__":
    load_dotenv('../app/.env')
    main()