# https://colab.research.google.com/drive/1cUw26iHAQMq6-iY6hWzasPmQytwY1IIg#scrollTo=brkqRojUm-ad
VERTEX_API_PROJECT = 'cloudai-353208' #@param {"type": "string"}
VERTEX_API_LOCATION = 'us-central1' #@param {"type": "string"}

from google.colab import auth as google_auth
google_auth.authenticate_user()

from __future__ import annotations

from google.cloud import discoveryengine_v1beta
from google.cloud.discoveryengine_v1beta.services.search_service import pagers
from google.protobuf.json_format import MessageToDict
import json
from langchain import PromptTemplate
from langchain.agents import AgentType, initialize_agent, AgentExecutor, LLMSingleActionAgent, AgentOutputParser
from langchain.callbacks.manager import CallbackManagerForChainRun, Callbacks
from langchain.chains.base import Chain
from langchain.chains.question_answering import load_qa_chain
from langchain.chains import LLMChain
from langchain.llms import VertexAI
from langchain.llms.utils import enforce_stop_tokens
from langchain.prompts import StringPromptTemplate
from langchain.retrievers import GoogleCloudEnterpriseSearchRetriever as EnterpriseSearchRetriever
from langchain.schema import AgentAction, AgentFinish, Document, BaseRetriever
from langchain.tools import Tool
from langchain.utils import get_from_dict_or_env
from pydantic import BaseModel, Extra, Field, root_validator
import re
from typing import Any, Mapping, List, Dict, Optional, Tuple, Sequence, Union
import unicodedata
import vertexai
from vertexai.preview.language_models import TextGenerationModel

vertexai.init(project=VERTEX_API_PROJECT, location=VERTEX_API_LOCATION)


class EnterpriseSearchChain(Chain):
    """Chain that queries an Enterprise Search Engine and summarizes the responses."""

    chain: Optional[LLMChain]
    search_client: Optional[EnterpriseSearchRetriever]

    def __init__(self,
                 project,
                 search_engine,
                 chain,
                 location='global',
                 serving_config_id='default_config'):
        super().__init__()
        self.chain = chain
        self.search_client = EnterpriseSearchRetriever(project_id=project,
                                                       search_engine_id=search_engine,
                                                       location_id=location,
                                                       serving_config_id=serving_config_id)

    @property
    def input_keys(self) -> List[str]:
        return ['query']

    @property
    def output_keys(self) -> List[str]:
        return ['summary']

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        _run_manager = CallbackManagerForChainRun.get_noop_manager()
        query = inputs['query']
        _run_manager.on_text(query, color="green", end="\n", verbose=self.verbose)
        documents = self.search_client.get_relevant_documents(query)
        content = [d.page_content for d in documents]
        _run_manager.on_text(content, color="white", end="\n", verbose=self.verbose)
        summary = self.chain.run(content)
        return {'summary': summary}


    @property
    def _chain_type(self) -> str:
        return "google_enterprise_search_chain"
    

def simple_retrieve():
    """
    In this example, we use a search engine containing Alphabet Investor PDFs (an unstructured Enterprise Search engine). We retrieve a set of search results (snippets from individual PDF documents) and then pass these into an LLM prompt. We ask the LLM to summarize the results

Use Cases
Retrieving and summarizing data that exists across various sources
Structuring unstructured data, e.g. converting financial data stored in PDFs to a Pandas dataframe
"""
    GCP_PROJECT = "cloudai-353208" #@param {type: "string"}
    SEARCH_ENGINE = "myunstructured_1682326157050" #@param {type: "string"}
    LLM_MODEL = "text-bison@001" #@param {type: "string"}
    MAX_OUTPUT_TOKENS = 1024 #@param {type: "integer"}
    TEMPERATURE = 0.2 #@param {type: "number"}
    TOP_P = 0.8 #@param {type: "number"}
    TOP_K = 40 #@param {type: "number"}
    VERBOSE = True #@param {type: "boolean"}
    llm_params = dict(
        model_name=LLM_MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        top_k=TOP_K,
        verbose=VERBOSE,
    )

    llm = VertexAI(**llm_params)
    SEARCH_QUERY = 'Total Revenue' #@param {type: "string"}
    PROMPT_STRING = "Please parse these search results of financial data and combine them into a tab delimited table: {results}" #@param {type: "string"}

    # Combine the LLM with a prompt to make a simple chain
    prompt = PromptTemplate(input_variables=['results'],
                            template=PROMPT_STRING)

    chain = LLMChain(llm=llm, prompt=prompt, verbose=True)

    # Combine this chain with Enterprise Search in a new chain
    es_chain = EnterpriseSearchChain(project=GCP_PROJECT,
                                    search_engine=SEARCH_ENGINE,
                                    chain=chain)

    result = es_chain.run(SEARCH_QUERY)

    result.split('\n')


def llm_retrieve():
    """
In some cases a user query might be too complex or abstract to be easily retrievable using a search engine. In this example we take the following approach:

Take a complex query from the user
Use an LLM to divide it into simple search terms
Run a search for each query, retrieve and combine the results
Ask the LLM to summarize the results in order to answer the query
The dataset in this example is an unstructured search engine containing a set of PDFs downloaded from Worldbank
"""
    COMPLEX_QUERY = 'Is it correct to assume that a draft SEP must be disclosed prior to appraisal, but the consultation does not need to be completed before appraisal?' #@param {"type": "string"}
    GCP_PROJECT = "google.com:es-demo-search-engines" #@param {type: "string"}
    SEARCH_ENGINE = 'worldbank-pdfs_1683039312062' #@param {"type": "string"}

    LLM_MODEL = "text-bison@001" #@param {type: "string"}
    MAX_OUTPUT_TOKENS = 256 #@param {type: "integer"}
    TEMPERATURE = 0.2 #@param {type: "number"}
    TOP_P = 0.8 #@param {type: "number"}
    TOP_K = 40 #@param {type: "number"}
    VERBOSE = True #@param {type: "boolean"}

    # Initialise an LLM
    llm_params = dict(
        model_name=LLM_MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        top_k=TOP_K,
        verbose=VERBOSE,
    )

    llm = VertexAI(**llm_params)

    # Initialise an Enterprise Search Retriever
    retriever = EnterpriseSearchRetriever(project_id=GCP_PROJECT, search_engine_id=SEARCH_ENGINE)

    prompt = PromptTemplate(input_variables=["complex_query"], template="""Extract the most specific search terms from the following query:

    Query:
    '{complex_query}'

    Search Terms:
    * """)

    #@markdown ## Fetch results from the LLM
    chain = LLMChain(llm=llm, prompt=prompt, verbose=True)
    terms = chain.run(COMPLEX_QUERY)

    lines_to_ignore = 0 #@param {"type": "integer"}
    max_terms_to_search = 4 #@param {"type": "integer"}

    clean_terms = [re.sub('[^\d\w\s]', '', q).strip() for q in terms.split('\n')[lines_to_ignore:lines_to_ignore + max_terms_to_search]]

    #@markdown `['disclosure', 'appraisal', 'consultation', 'draft', 'sep']`
    num_results = 1 #@param {"type": "integer"}

    results = []
    for q in clean_terms:
        snippets = [d.page_content for d in retriever.get_relevant_documents(q)]
        results.extend([s for s in snippets[:num_results]])

        results = list(set(results)) # Deduplicate to keep prompt length down
    
    #@markdown ## Combine the search results into an answer using an LLM
    # Combine the LLM with a prompt to make a simple chain
    prompt = PromptTemplate(input_variables=['query', 'results'],
                            template="""Please summarize the following contextual data to answer the following question. Provide references to the context in your answer:
    Question: {query}
    Context:
    {results}
    Answer with citations:""")
    chain = LLMChain(llm=llm, prompt=prompt, verbose=True)

    res = chain.run({"query": COMPLEX_QUERY, "results": results})

    res.split('\n')

    return res

def langchain_qa(clean_terms, retriever, COMPLEX_QUERY, llm):
    """
Langchain provides some more sophisticated examples of chains which are designed specifically for question answering on your own documents. There are a few approaches, one of which is the refine pattern.

The refine chain is passed a set of langchain Documents and a query. It begins with the first document and sees if it can answer the question using the context. It then iteratively incorporates each subsequent document to refine its answer.

In this example we convert a set of Enterprise Search snippets into Documents and pass them to the chain.

We will use the same search engine and terms extracted from the previous example

More examples in langchain docs here
    """
    # def search_response_to_documents(res) -> List[Document]:
#     """Retrieve langchain Documents from a search response"""
#     documents = []
#     for result in res.results:
#         data = MessageToDict(result.document._pb)
#         metadata = data.copy()
#         del metadata['derivedStructData']
#         del metadata['structData']
#         if data.get('derivedStructData') is None:
#             content = json.dumps(data.get('structData', {}))
#         else:
#             content = json.dumps([d.get('snippet') for d in data.get('derivedStructData', {}).get('snippets', []) if d.get('snippet') is not None])
#         documents.append(Document(page_content=content, metadata=metadata))
#     return documents

#@markdown ## Search for each search term and extract into a langchain `Document` format
#@markdown * This format just contains the snippets as `page_content` and the document title and link as `metadata`

    document_responses = []
    for t in clean_terms:
        document_responses.append(retriever.get_relevant_documents(t))

    # This chain will run one LLM call for every document, so we likely do not want to keep all of the context if the document count is very large
    for idx, d in enumerate(document_responses):
        print(f"Search {idx + 1}: {len(d)} documents")
    # There are 65 documents total, so we will just keep the top 3 from each search
    final_documents = [d for r in document_responses for d in r[:3]]

    len(final_documents)

    chain = load_qa_chain(llm, chain_type="refine", return_refine_steps=True)

    chain({"input_documents": final_documents, "question": COMPLEX_QUERY}, return_only_outputs=True)

def react_chain():
    """
ArXiv Paper

One of the more sophisticated workflows using LLMs is to create an 'agent' that can create new prompts for itself and then answer them in order to complete more complex tasks.

One of the most powerful examples is the 'ReAct' (Reasoning + Acting) agent, which alternates between retrieving results from a prompt and assessing them in the context of a task. The agent autonomously determines if it has successfully completed the task and whether to continue answering new prompts or to return a result to the user.

ReAct agents can be provided with an array of tools, each with a description. (These tools can be as simple as any python function that provides a string input and string output.) The ReAct agent uses the description of each tool to determine which to use at each stage.

The following examples use Enterprise Search as a tool to retrieve a set of search result snippets to inform the prompt.

Use Cases
Answering queries with complex intent
Combining information retrieval with other tools such as data processing, mathematical operations, web search, etc.
    """
    COMPLEX_QUERY = 'Is it correct to assume that a draft SEP must be disclosed prior to appraisal, but the consultation does not need to be completed before appraisal?' #@param {"type": "string"}
    GCP_PROJECT = "google.com:es-demo-search-engines" #@param {type: "string"}
    SEARCH_ENGINE = "worldbank-pdfs_1683039312062" #@param {type: "string"}
    LLM_MODEL = "text-bison@001" #@param {type: "string"}
    MAX_OUTPUT_TOKENS = 512 #@param {type: "integer"}
    TEMPERATURE = 0.2 #@param {type: "number"}
    TOP_P = 0.8 #@param {type: "number"}
    TOP_K = 40 #@param {type: "number"}
    VERBOSE = True #@param {type: "boolean"}

    # Initialize an LLM
    llm_params=dict(
        model_name=LLM_MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        top_k=TOP_K,
        verbose=VERBOSE,
        )

    llm = VertexAI(**llm_params)

    # Initialize an Enterprise Search Retriever
    retriever = EnterpriseSearchRetriever(project_id=GCP_PROJECT, search_engine_id=SEARCH_ENGINE)

    # The name and description here are critical in helping the LLM determine which tool to use
    tools = [
        Tool.from_function(
            func=retriever.get_relevant_documents,
            name = "Enterprise Search",
            description="Search for a query"
        )
    ]

    # Combine the LLM with the search tool to make a ReAct agent
    react_agent = initialize_agent(tools,
                                llm,
                                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                                verbose=True)


    react_agent.run(COMPLEX_QUERY)

def custom_agent():
    #@title [Work in Progress!] Creating a custom agent to customize the LLM prompts and behaviour
#@markdown More prompt refinement is needed here to encourage the ReAct agent to act as expected
# Define the strings that define an Agent observation and the final question answer
    OUTPUT_STOPSTRING = 'Final answer: '
    OBSERVATION_STOPSTRING = "Observation:"

    # Define the initial prompt to guide the ReAct Agent LLM

    agent_template = f"""Answer the following question by retrieving and summarizing search results from a document store.
    * Include citations from the search results when answering the question.
    * Always begin by running a search against the document store.
    * Once you have information from the document store, answer the question with citations and finish.

    * If the document store returns no search results, then use the query simplifier and search using the new keywords.
    * If you are given a set of keywords, search for each of them in turn and summarize the results.
    * Do not attempt to open and read the documents, just summarize the information contained in the snippets.

    You have access to the following tools:

    {{tools}}

    Always use the format:

    Question: the input question you must answer
    Thought: you should always think about what to do
    Action: the action to take, should be one of [{{tool_names}}]
    Action Input: the input to the action
    {OBSERVATION_STOPSTRING}the result of the action
    ... (this Thought/Action/Action Input/Observation can repeat N times)
    Thought: I now have search results which I can use to produce an answer
    {OUTPUT_STOPSTRING}the final answer to the original input question

    Begin!

    Question: {{input}}
    {{agent_scratchpad}}"""

    class LLMSingleActionAgentWithRetry(LLMSingleActionAgent):
        """Custom Class to allow retry on failed actions"""
        llm_chain: LLMChain
        output_parser: AgentOutputParser
        stop: List[str]

        @property
        def input_keys(self) -> List[str]:
            return list(set(self.llm_chain.input_keys) - {"intermediate_steps"})

        def plan(
            self,
            intermediate_steps: List[Tuple[AgentAction, str]],
            callbacks: Callbacks = None,
            **kwargs: Any,
        ) -> Union[AgentAction, AgentFinish]:
            """Given input, decided what to do.

            Args:
                intermediate_steps: Steps the LLM has taken to date,
                    along with observations
                callbacks: Callbacks to run.
                **kwargs: User inputs.

            Returns:
                Action specifying what tool to use.
            """
            output = self.llm_chain.run(
                intermediate_steps=intermediate_steps,
                stop=self.stop,
                callbacks=callbacks,
                **kwargs,
            )
            return self.output_parser.parse(output, intermediate_steps)


    class SearchAgentPromptTemplate(StringPromptTemplate):
        """Custom class to format the agent output into the correct prompts"""
        template: str
        tools: List[Tool]

        def format(self, **kwargs) -> str:
            intermediate_steps = kwargs.pop("intermediate_steps")
            thoughts = ""
            for action, observation in intermediate_steps:
                thoughts += action.log
                thoughts += f"\n{OBSERVATION_STOPSTRING}{observation}\nThought>>"
            kwargs["agent_scratchpad"] = thoughts
            kwargs["tools"] = "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])
            kwargs["tool_names"] = ", ".join([tool.name for tool in self.tools])
            return self.template.format(**kwargs)

    class SearchAgentOutputParser(AgentOutputParser):
        """Custom class to parse agent output"""

        tools: List[str]

        def parse(self,
                llm_output: str,
                intermediate_steps: Optional[List[Tuple[AgentAction, str]]]
                ) -> Union[AgentAction, AgentFinish]:
            if OUTPUT_STOPSTRING in llm_output:
                return AgentFinish(
                    return_values={"output": llm_output.split(OUTPUT_STOPSTRING)[-1].strip()},
                    log=llm_output,
                )
            regex = r".*?\nAction[\s\d]*:(.*?)\nAction Input[\s\d]*:(.*)"
            # No LLM response, try a different tool
            if llm_output.strip() == '':
                if intermediate_steps != []:
                    last_step = intermediate_steps[-1][0]
                    other_tools = [t for t in self.tools if t != last_step.tool]
                    if other_tools != []:
                        return AgentAction(tool=other_tools[0], tool_input=last_step.tool_input, log=llm_output)
                return AgentFinish(return_values={"output": "No results found"}, log=llm_output,)
            match = re.search(regex, llm_output, re.DOTALL)
            if not match:
                raise ValueError(f"Could not parse LLM output: `{llm_output}`")
            action = match.group(1).strip()
            action_input = match.group(2)
            return AgentAction(tool=action, tool_input=action_input.strip(" ").strip('"'), log=llm_output)

    # Initialise an Enterprise Search project
    search_project = "google.com:es-unstructured-demo" #@param {"type": "string"}
    search_engine = 'worldbank_poc-818346' #@param {"type": "string"}

    # Initialise the LLM
    llm = VertexAI(**{
        "model_name": 'text-bison@001',
        "max_output_tokens": 256,
        "temperature": 0.1,
        "top_p": 0.8,
        "top_k": 40,
        "verbose": True,
        })

    # Initialise the Enterprise Search Retriever to fetch document snippets for a search query
    retriever = EnterpriseSearchRetriever(project_id=search_project, search_engine_id=search_engine)

    # Define a function to use an LLM to split a complex query into better search terms

    def extract_search_terms(self, query:str) -> List[str]:
        """Use an LLM to break a complex query into an array of search terms"""
        prompt = PromptTemplate(
            input_variables=['query'],
            template="""Parse the following question and extract an array of specific search terms to use in a search engine:
    Question:
    '{query}'
    Search Terms:
    * """)
        chain = LLMChain(llm=self.llm, prompt=prompt)
        res = chain.run(query)
        terms = [re.sub(r'[^\w\d\s]', '', r).strip() for r in res.split('\n')]
        return [t for t in terms if t != '']

    tools = [
        Tool.from_function(
            func=retriever.get_relevant_documents,
            name = "Search Documents",
            description="""Use this to retrieve excerpts from documents in a document store.
            These documents contain contextual information which may be useful in answering
            a user query.""",
        ),
        Tool.from_function(
            func=extract_search_terms,
            name = "Simplify Query",
            description="""Convert a query into a set of simple search keywords.
    Use this if a search term is not returning any results from a search engine.
            These keywords may then be searched in the Document store."""
        )
    ]


    prompt = SearchAgentPromptTemplate(
        template=agent_template,
        tools=tools,
        input_variables=["input", "intermediate_steps"]
    )



    chain = LLMChain(llm=llm, prompt=prompt)
    tool_names =[tool.name for tool in tools]

    output_parser = SearchAgentOutputParser(tools=tool_names)

    search_agent = LLMSingleActionAgentWithRetry(
        llm_chain=chain,
        output_parser=output_parser,
        stop=[OBSERVATION_STOPSTRING],
        allowed_tools=tool_names
    )
    search_agent_executor = AgentExecutor.from_agent_and_tools(agent=search_agent, tools=tools, verbose=True)