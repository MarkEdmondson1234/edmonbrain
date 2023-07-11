from langchain.chains.summarize import load_summarize_chain
from qna.llm import pick_llm

def summarise_docs(docs, vector_name):
    llm, _, _ = pick_llm(vector_name)
    for doc in docs:
        doc.metadata.update({"type":"summary"})
    chain = load_summarize_chain(llm, chain_type="map_reduce")
    summary = chain.run(docs)

    return summary