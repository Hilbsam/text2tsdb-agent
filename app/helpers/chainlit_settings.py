# Diese Datei wurde mit der Dokumentation von https://docs.chainlit.io/api-reference/input-widgets/select#attributes erstellt.
from chainlit.input_widget import Select

settings_list = [
    Select(
        id="model_query",
        label="Model für den Query Agent",
        items={
                "Mistral": "mistral",
                "OpenAI":  "openai",
                "Google":  "google"
                },
        initial_value="mistral",
        description="Wähle das Modell, das der Query Agent verwenden soll."
    ),
    Select(
        id="model_interpret",
        label="Model für den Interpretation Agent",
        items={
                "Mistral": "mistral",
                "OpenAI":  "openai",
                "Google":  "google"
                },
        initial_value="mistral",
        description="Wähle das Modell, das der Interpretation Agent verwenden soll."
    ),
]