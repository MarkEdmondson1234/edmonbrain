from langchain.chains.summarize import load_summarize_chain
from langchain.schema import Document

from qna.llm import pick_llm
import logging

def summarise_docs(docs, vector_name):
    llm, _, _ = pick_llm(vector_name)
    for doc in docs:
        metadata = doc.metadata

    chain = load_summarize_chain(llm, chain_type="map_reduce")
    summary = chain.run(docs)
    
    metadata["type"] = "summary"
    summary = Document(page_content=summary, metadata=metadata)

    logging.info(f"Summary: {summary}")
    return summary