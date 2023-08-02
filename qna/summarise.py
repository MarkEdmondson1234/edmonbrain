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


import time
import random

def summarise_docs(docs, vector_name):
    llm, _, _ = pick_llm(vector_name)
    chain = load_summarize_chain(llm, chain_type="map_reduce", verbose=True,
                                 map_prompt=MAP_PROMPT,
                                 combine_prompt=MAP_PROMPT)

    summaries = []
    for doc in docs:
        logging.info(f"summarise: doc {doc}")
        if len(doc.page_content) < 10000:
            continue
        metadata = doc.metadata
        chunks = chunk_doc_to_docs([doc])

        # Initial delay
        delay = 1.0  # 1 second, for example
        max_delay = 300.0  # Maximum delay, adjust as needed

        for attempt in range(5):  # Attempt to summarize 5 times
            try:
                summary = chain.run(chunks)
                break  # If the summary was successful, break the loop
            except Exception as e:
                logging.error(f"Error while summarizing on attempt {attempt+1}: {e}")
                print(f"Failure, waiting {delay} seconds before retrying...")
                time.sleep(delay)  # Wait for the delay period
                delay = min(delay * 2 + random.uniform(0, 1), max_delay)  # Exponential backoff with jitter
        else:
            logging.error(f"Failed to summarize after 5 attempts")
            continue  # If we've failed after 5 attempts, move on to the next document

        
        metadata["type"] = "summary"
        summary = Document(page_content=summary, metadata=metadata)
        logging.info(f"Summary: {summary}")
        summaries.append(summary)
        
    return summaries
