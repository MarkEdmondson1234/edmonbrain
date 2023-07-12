from langchain.chains.summarize import load_summarize_chain
from langchain.schema import Document

from qna.llm import pick_llm
from qna.publish_to_pubsub_embed import chunk_doc_to_docs
import logging

from langchain.prompts import PromptTemplate

prompt_template = """Write a summary for below, including key concepts, people and distinct information but do not add anything that is not in the original text:

"{text}"

SUMMARY:"""
MAP_PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])


def summarise_docs(docs, vector_name):
    llm, _, _ = pick_llm(vector_name)
    chain = load_summarize_chain(llm, chain_type="map_reduce", verbose=True,
                                 map_prompt=MAP_PROMPT,
                                 combine_prompt=MAP_PROMPT)

    summaries = []
    for doc in docs:
        logging.debug(f"summarise: doc {doc}")
        metadata = doc.metadata
        chunks = chunk_doc_to_docs([doc])
        summary = chain.run(chunks)
        
        metadata["type"] = "summary"
        summary = Document(page_content=summary, metadata=metadata)
        logging.info(f"Summary: {summary}")
        summaries.append(summary)
        
    return summaries