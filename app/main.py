from fastapi import FastAPI
from pydantic import BaseModel

from app.agent import build_agent

app =  FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(request: AskRequest):
    agent = build_agent()
    result = agent(request.question)
    return {"answer": str(result)}