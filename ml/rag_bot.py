from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain.document_loaders import PyPDFLoader, TextLoader, WebBaseLoader, BSHTMLLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader, JSONLoader, UnstructuredXMLLoader, UnstructuredExcelLoader, ConfluenceLoader
from langchain_community.document_loaders.merge import MergedDataLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chat_models.gigachat import GigaChat
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.llms import HuggingFacePipeline
from langchain.prompts import PromptTemplate
from typing import List, Union, Dict, Any, Optional
import os


class EnhancedConversationBufferMemory(ConversationBufferMemory):
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        if self.input_key is None:
            self.input_key = list(inputs.keys())[0]

        if self.output_key is None:
            self.output_key = list(outputs.keys())[0]

        human_message = inputs[self.input_key]
        ai_message = outputs[self.output_key]

        self.chat_memory.add_user_message(human_message)
        self.chat_memory.add_ai_message(ai_message)


class RAGChatBot:
    def __init__(
        self,
        data_sources: List[tuple],
        model_name: str = None,
        from_huggingface: bool = True,
        gigachat_api_key: Optional[str] = None,
        embeddings_model: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
        k_retriever: int = 5,
        save_path: str = 'vector_store.index',
        system_prompt:  Optional[str] = None
    ):
        self.data_sources = data_sources
        self.embeddings_model = embeddings_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.k_retriever = k_retriever
        self.save_path = save_path
        self.system_prompt = system_prompt

        if self.system_prompt:
            self.custom_prompt_template = f'''
            SYSTEM PROMPT: 
            {self.system_prompt}

            Контекст: 
            {{context}}

            Вопрос: 
            {{question}}

            История чата:
            {{chat_history}}

            Полезный ответ:
            '''

            self.custom_prompt = PromptTemplate(
                template=self.custom_prompt_template,
                input_variables=['context', 'question', 'chat_history'],
            )

        self.llm = self._get_model(
            model_name=model_name,
            from_huggingface=from_huggingface,
            gigachat_api_key=gigachat_api_key
        )

        self.embeddings = self._get_embeddings()

        self.message_history = []
        self.chat_memory = None
        self.conversation_chain = None

        if self.data_sources:
            self.documents = self._load_data(self.data_sources)
            self.docs = self._split_data(self.documents)
            self.vector_store = self._create_vector_store()
            self._initialize_conversation_chain()

    def _initialize_conversation_chain(self):
        retriever = self.vector_store.as_retriever(search_kwargs={'k': self.k_retriever})

        self.chat_memory = EnhancedConversationBufferMemory(
            memory_key='chat_history',
            return_messages=True,
            input_key='question',
            output_key='answer'
        )

        kwargs = {}

        if self.system_prompt:
            kwargs['combine_docs_chain_kwargs'] = {'prompt': self.custom_prompt}

        self.conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=retriever,
            memory=self.chat_memory,
            return_source_documents=True,
            chain_type='stuff',
            **kwargs
        )

    def chat(self, query: str):
        if not self.conversation_chain:
            raise ValueError('Initialize chatbot with documents first')
        result = self.conversation_chain({'question': query})

        return result['answer'], result['source_documents']

    def _load_data(self, sources: List[tuple]):
        loaders = []
        for mode, source in sources:
            if mode == 'file':
                if source.lower().endswith('.txt'):
                    loaders.append(TextLoader(source, autodetect_encoding=True))
                elif source.lower().endswith('.pdf'):
                    loaders.append(PyPDFLoader(source))
                elif source.lower().endswith('.csv'):
                    loaders.append(CSVLoader(source))
                elif source.lower().endswith(('.html', '.htm')):
                    loaders.append(BSHTMLLoader(source))
                elif source.lower().endswith('.md'):
                    loaders.append(UnstructuredMarkdownLoader(source))
                elif source.lower().endswith('.xml'):
                    loaders.append(UnstructuredXMLLoader(source))
                elif source.lower().endswith('.json'):
                    loaders.append(JSONLoader(
                        source,
                        jq_schema='.',
                        text_content=False
                    ))
                elif source.lower().endswith(('.xls', '.xlsx')):
                    loaders.append(UnstructuredExcelLoader(source))
                else:
                    raise ValueError(f'Unsupported file format: {source}')
            elif mode == 'url':
                if source.startswith(('http://', 'https://')):
                    loaders.append(WebBaseLoader(source))
                else:
                    raise ValueError(f'Unsupported URL format: {source}')
            elif mode == 'confluence':
                url, username, api_key, space_key, limit = source['url'], source[
                    'username'], source['api_key'], source['space_key'], source['limit']
                loader = ConfluenceLoader(
                    url=url,
                    username=username,
                    api_key=api_key,
                    space_key=space_key,
                    limit=limit,
                )
                loaders.append(loader)
            else:
                raise ValueError(f'Unsupported mode: {mode}')

        merged_loader = MergedDataLoader(loaders=loaders)
        return merged_loader.load()

    def _split_data(self, documents):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return text_splitter.split_documents(documents)

    def _get_embeddings(self, retriever: str = None):
        return HuggingFaceEmbeddings(model_name=retriever or self.embeddings_model)

    def _get_model(self, model_name: str = None, from_huggingface: bool = True, gigachat_api_key: str = None):
        if from_huggingface:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name)
            pipe = pipeline(
                'text-generation', model=model, tokenizer=tokenizer, max_new_tokens=1024
            )
            llm = HuggingFacePipeline(pipeline=pipe)
        else:
            llm = GigaChat(
                credentials=gigachat_api_key,
                verify_ssl_certs=False
            )

        return llm

    def _create_vector_store(self):
        if os.path.exists(self.save_path):
            print(f'Loading existing vector store from {self.save_path}')
            vector_store = FAISS.load_local(self.save_path, self.embeddings, allow_dangerous_deserialization=True)
        else:
            print(f'Creating new vector store and saving to {self.save_path}')
            vector_store = FAISS.from_documents(
                documents=self.docs,
                embedding=self.embeddings
            )
            vector_store.save_local(self.save_path)
        return vector_store

    def add_sources(self, new_sources: List[tuple]):
        new_documents = self._load_data(new_sources)
        new_docs = self._split_data(new_documents)

        self.vector_store.add_documents(new_docs)
        self.vector_store.save_local(self.save_path)

        self.data_sources.extend(new_sources)
        print(f'Successfully added {len(new_sources)} new sources to the chatbot.')

    def remove_sources(self, sources_to_remove: List[tuple]):
        self.data_sources = [
            source for source in self.data_sources if source not in sources_to_remove
        ]

        self.documents = self._load_data(self.data_sources)
        self.docs = self._split_data(self.documents)

        self.vector_store = FAISS.from_documents(self.docs, self.embeddings)
        self.vector_store.save_local(self.save_path)
        print(f'Successfully removed {len(sources_to_remove)} new sources from the chatbot.')

    def change_model(self, new_model_name: str, from_huggingface: bool = True, gigachat_api_key: Optional[str] = None):
        self.llm = self._get_model(
            model_name=new_model_name,
            from_huggingface=from_huggingface,
            gigachat_api_key=gigachat_api_key
        )
        self._initialize_conversation_chain()
        print(f'Model successfully changed to {new_model_name}.')

    def change_retriever(self, new_embeddings_model: str):
        self.embeddings = self._get_embeddings(retriever=new_embeddings_model)
        self.vector_store = self._create_vector_store()
        self._initialize_conversation_chain()
        print(f'Retriever successfully changed to {new_embeddings_model}.')

    def change_prompt(self, new_system_prompt: str):
        self.system_prompt = new_system_prompt
        self.custom_prompt_template = f'''
        SYSTEM PROMPT: 
        {self.system_prompt}

        Контекст: 
        {{context}}

        Вопрос: 
        {{question}}

        История чата:
        {{chat_history}}

        Полезный ответ:
        '''

        self.custom_prompt = PromptTemplate(
            template=self.custom_prompt_template,
            input_variables=['context', 'question', 'chat_history'],
        )

        self._initialize_conversation_chain()
        print(f'System prompt successfully changed to: {new_system_prompt}')


# roles = {
#     "аналитик": "Ты аналитик. Твоя задача — предоставить четкий, обоснованный и краткий анализ ситуации. Используй данные и логику для поддержки своих выводов. Избегай лишних деталей и философствования.",
#     "ресерчер": "Ты исследователь. Твоя задача — провести глубокое исследование темы, предоставить подробный контекст и ссылки на источники. Быть объективным и всесторонним в оценке информации.",
#     "технический эксперт": "Ты технический эксперт. Твоя задача — давать точные, технические ответы, основанные на глубоком знании предмета. Используй специализированный терминологический словарь, когда это необходимо.",
#     "учитель": "Ты учитель. Твоя задача — объяснить концепцию просто и понятно, используя примеры и аналогии. Быть доступным для начинающих, но также готовым предоставить более глубокую информацию для продвинутых пользователей.",
#     "помощник": "Ты помощник. Твоя задача — предоставить понятные и доброжелательные ответы, помогая пользователю решить его проблему. Быть эмпатичным и готовым предложить альтернативные решения.",
#     "творец": "Ты творец. Твоя задача — предлагать креативные и нестандартные решения, выходящие за рамки традиционного мышления. Быть инновационным и экспериментальным в подходе.",
#     "учёный": "Ты учёный. Твоя задача — отвечать строго на основе фактов, научных данных и объективного анализа. Избегай субъективных мнений и сосредоточься на доказательствах.",
#     "историк": "Ты историк. Твоя задача — предоставить подробный контекст событий, их причины и последствия. Быть точным в фактах и объективным в оценке исторических событий.",
#     "журналист": "Ты журналист. Твоя задача — предоставить полный и балансированный отчет о событиях, включая различные точки зрения и источники. Быть объективным и точным в информации.",
#     "юрист": "Ты юрист. Твоя задача — предоставить правовую консультацию, основанную на законодательстве и precedents. Быть точным в юридических терминах и предоставить рекомендации по действию.",
#     "психолог": "Ты психолог. Твоя задача — предоставить эмпатичную и профессиональную помощь, основанную на знании человеческой психологии. Быть внимательным к эмоциональным потребностям пользователя.",
#     "маркетолог": "Ты маркетолог. Твоя задача — предоставить стратегические рекомендации по продвижению продукта или услуги, основанные на рыночных исследованиях и тенденциях.",
#     "разработчик": "Ты разработчик. Твоя задача — предоставить технические решения для программных проблем, используя свой опыт в области разработки software.",
#     "дизайнер": "Ты дизайнер. Твоя задача — предлагать креативные и эстетически привлекательные решения для визуальных задач, основанные на принципах дизайна.",
#     "философ": "Ты философ. Твоя задача — размышлять над глубокими вопросами существования, этики и знания. Предоставлять размышления и аргументы на философские темы.",
#     "финансовый аналитик": "Ты финансовый аналитик. Твоя задача — проводить анализ финансовых показателей, предсказывать тенденции и предоставлять рекомендации по инвестициям."
# }

# gigachat_bot = RAGChatBot(
#     save_path='vector_store_1',
#     system_prompt=roles['ресерчер'],
#     data_sources=[
#         ('file', '/content/2408.17352v1.pdf'),
#         ('file', '/content/Bulgakov_Mihail_Master_i_Margarita_Readli.Net_bid256_5c1f5.txt'),
#         ('file', '/content/sample_submission.csv'),
#         ('file', '/content/https___python.langchain.com_v0.1_docs_modules_data_connection_document_loaders_html_.htm'),
#         ('file', '/content/README.md'),
#         ('file', '/content/10kb.json'),
#         ('file', '/content/1.xml'),
#         ('file', '/content/file_example_XLSX_1000.xlsx'),
#         ('confluence', {'url': 'https://yoursite.atlassian.com/wiki', 'username': 'me', 'api_key': '12345', 'space_key': 'SPACE', 'limit': 50}),
#     ],
#     from_huggingface=False,
#     gigachat_api_key='NjBiZDkyMTItOTVlYi00ZGE4LTlmM2YtNGExZWVhZTQ3MDQxOjhiMTAxN2Y2LWRiM2QtNDhiMS1hZTNkLTc3MjA2MDAzNDA1OA==',
#     embeddings_model='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
# )

# gigachat_bot.add_sources([
#     ('url', 'https://t1.ru/'),
# ])

# ans, _ = gigachat_bot.chat('что такое т1 облако')

# gigachat_bot.remove_sources([
#     ('file', '/content/sample_submission.csv'),
# ])

# ans, _ = gigachat_bot.chat('что такое т1 облако')

# gigachat_bot.change_model(new_model_name='google/gemma-2-9b-it')

# gigachat_bot.change_retriever(new_embeddings_model='sentence-transformers/all-MiniLM-L6-v2')

# huggingface_bot = RAGChatBot(
#     save_path='vector_store_2',
#     data_sources=[
#         ('file', '/content/2408.17352v1.pdf'),
#         ('file', '/content/Bulgakov_Mihail_Master_i_Margarita_Readli.Net_bid256_5c1f5.txt')
#     ],
#     from_huggingface=True,
#     model_name='google/gemma-2-9b-it',
#     embeddings_model='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
# )
