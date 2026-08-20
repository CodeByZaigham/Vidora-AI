from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from RAG_pipeline.textsplitter import split_text
from llm import get_llm

llm=get_llm()

def summarize_chunks(transcript: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """Summarize the following meeting transcript chunk concisely.

            Focus only on the important information:
            - Main topics discussed
            - Important points or updates
            - Questions that were asked
            - Decisions that were made
            - Actionable items or tasks
            - Deadlines or responsibilities, if mentioned

            Preserve questions, decisions, and action items accurately.
            Do not invent information or add details that are not present.
            Keep the summary short and factual."""
        ),
        ("human", "{text}")
    ])

    summary_chain = prompt | llm | StrOutputParser()

    chunks = split_text(transcript)

    summaries = [
        summary_chain.invoke({"text": chunk})
        for chunk in chunks
    ]

    return "\n".join(summaries)


