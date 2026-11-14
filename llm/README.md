# FireOrbit LLM layer (Gemini)

```
pip install -r llm/requirements.txt          # plus embedding/requirements.txt + rank_bm25
export GEMINI_API_KEY=...                    # https://aistudio.google.com/apikey

# one question
python llm/rag_answer.py "which test reached 85% oxygen" --model gemini-3-flash-preview

# compare models on the eval set (retrieval shared, only the LLM differs)
python llm/compare_models.py --models gemini-3-flash-preview gemini-2.5-flash \
       --judge-model gemini-2.5-pro
```
Outputs `llm/results/{results.json,results.csv,report.md}`.
Check exact model IDs with `client.models.list()`; override the default with `GEMINI_MODEL`.
