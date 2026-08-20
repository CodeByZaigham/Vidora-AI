from langchain_core.runnables import RunnableSequence
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm import get_llm

llm=get_llm()

def build_chain(system_prompt , summary:str) -> RunnableSequence:
     return RunnableSequence(
          ChatPromptTemplate.from_messages([
               ("system",system_prompt),
               ("human",summary)
          ])
          | llm | StrOutputParser()
     )

def get_title(summary:str) -> str:
     prompt=(
          "I am giving you multiple summarized chunks of a meeting transcript. "
          "Analyze all the chunks together and generate one concise, meaningful title "
          "that accurately represents the main topic and purpose of the meeting. "
          "Return only the title, without quotes, explanations, or additional text."
     )

     chain=build_chain(prompt,summary)

     return chain.invoke({})

def get_summary(summary:str) -> str:
     prompt="I am giving you multiple summarized chunks of my meeting's transcript" \
     "combine it and generate one proper summary of the meeting."
     return build_chain(prompt,summary).invoke({})

def get_questions(summary:str) -> str:
    prompt = (
        "I am giving you multiple summarized chunks of a meeting transcript. "
        "Extract all important questions that were explicitly asked during the meeting. "
        "Combine questions that are duplicates or have the same meaning. "
        "Return only the questions as a clear numbered list. "
        "Do not generate new questions and do not provide a summary."
    )
    return build_chain(prompt, summary).invoke({})

def get_decisions(summary:str) -> str:
    prompt = (
        "I am giving you multiple summarized chunks of a meeting transcript. "
        "Analyze all the chunks together and identify the key decisions that were "
        "made during the meeting. Include decisions about plans, tasks, priorities, "
        "deadlines, responsibilities, or changes that were agreed upon. "
        "Do not include suggestions or unresolved discussions. "
        "Return only the decisions as a clear numbered list."
    )
    return build_chain(prompt, summary).invoke({})
     
def get_actions(summary:str) -> str:
    prompt = (
        "I am giving you multiple summarized chunks of a meeting transcript. "
        "Analyze all the chunks together and identify the action items agreed upon "
        "during the meeting. For each action item, include the task, the person "
        "responsible if mentioned, and the deadline if mentioned. "
        "Do not include completed tasks, general discussion, or decisions that do "
        "not require an action. "
        "Return only the action items as a clear numbered list."
    )
    return build_chain(prompt, summary).invoke({})
     
     