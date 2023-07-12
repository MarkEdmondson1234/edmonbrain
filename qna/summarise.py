from langchain.chains.summarize import load_summarize_chain
from langchain.schema import Document

from qna.llm import pick_llm
from qna.publish_to_pubsub_embed import chunk_doc_to_docs
import logging

def summarise_docs(docs, vector_name):
    llm, _, _ = pick_llm(vector_name)
    chain = load_summarize_chain(llm, chain_type="map_reduce")

    summaries = []
    for doc in docs:
        logging.info(f"summarise: doc {doc}")
        metadata = doc.metadata
        chunks = chunk_doc_to_docs([doc])
        summary = chain.run(chunks)
        
        metadata["type"] = "summary"
        summary = Document(page_content=summary, metadata=metadata)
        logging.info(f"Summary: {summary}")
        summaries.append(summary)
        
    return summaries