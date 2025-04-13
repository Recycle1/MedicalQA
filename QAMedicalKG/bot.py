import os
import requests
import re
import json
from openai import OpenAI
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
import torch
from bs4 import BeautifulSoup
from serpapi import GoogleSearch  # pip install google-search-results
from bs4 import BeautifulSoup

from question_classifier import *
from question_parser import *
from answer_search import *

'''问答类'''
class ChatBotGraph:
    def __init__(self):
        self.classifier = QuestionClassifier()
        self.parser = QuestionPaser()
        self.searcher = AnswerSearcher()

    def chat_main(self, sent):
        answer = ''
        res_classify = self.classifier.classify(sent)
        if not res_classify:
            return answer
        res_sql = self.parser.parser_main(res_classify)
        final_answers = self.searcher.search_main(res_sql)
        if not final_answers:
            return answer
        else:
            template = f"从医疗知识图谱中查询到如下信息：{''.join(final_answers)}，请整理并返回给用户一个完整的回答"
            return template

load_dotenv()
client = OpenAI(base_url='http://localhost:11434/v1', api_key='qwen2.5:latest')  # ollama服务默认端口
model = SentenceTransformer('D:/python_about/pythonProject/DeepLearning/医药问答/QAMedicalKG/sbert-chinese-general-v2')
# https://huggingface.co/DMetaSoul/sbert-chinese-general-v2/tree/main

# 设置颜色
PINK = '\033[95m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
NEON_GREEN = '\033[92m'
RESET_COLOR = '\033[0m'

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

def get_relevant_context(user_input, vault_embeddings, vault_content, model, top_k=7):  # adjust your top_k here
    if vault_embeddings.nelement() == 0:
        return []
    input_embedding = model.encode([user_input])
    cos_scores = util.cos_sim(input_embedding, vault_embeddings)[0]
    top_k = min(top_k, len(cos_scores))
    top_indices = torch.topk(cos_scores, k=top_k)[1].tolist()
    relevant_context = [vault_content[idx].strip() for idx in top_indices]
    return relevant_context

#serpapi, 需要注册下,但是我测试中文搜索不咋地
def search_baidu(query):
    # 设置请求头部信息，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    # 构建搜索URL
    search_url = f"https://www.baidu.com/s?wd={query}"

    # 发送GET请求
    response = requests.get(search_url, headers=headers)

    # 检查请求是否成功
    if response.status_code == 200:
        # 解析响应内容
        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找搜索结果的标题和链接
        search_results = soup.find_all('h3', class_='t')

        # 提取标题和链接

        results = ""
        for idx, result in enumerate(search_results):
            title = result.get_text(strip=True)
            link = result.a['href']
            results += str(idx + 1) + "." + title + "   链接：" + link + "\n"

        return results
    else:
        print("请求失败！")
        return None

#参考：https://platform.openai.com/docs/guides/function-calling
def convert_to_openai_function(func):
    return {
        "name": func.__name__,
        "description": func.__doc__,
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Email address of the recipient"},
                "subject": {"type": "string", "description": "Subject of the email"},
                "body": {"type": "string", "description": "Body of the email"},
                "attachment": {"type": "string", "description": "Path to an attachment"},
                "query": {"type": "string", "description": "Query to search on Google"},
                "user_message": {"type": "string", "description": "Users provided message to compare to the context"},
                "note_content": {"type": "string", "description": "Content to be written to the notes.txt file"},
            },
            "required": ["recipient", "subject", "body"],
        },
    }

functions = [
    convert_to_openai_function(search_baidu),
]

def parse_function_call(input_str):
    match = re.search(r'<functioncall>(.*?)</functioncall>', input_str, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None

def chat(messages):
    system_message = f"""
    你是一个医疗问答机器人，辅助用户决策，你可以调用知识图谱中相应的信息，同时可以直接搜索，对于搜索功能具体如下：
    {json.dumps(functions, indent=2)}
    
    如果用户的输入包含"搜索“或类似的问题或查询，生成如下格式的函数调用：
    <functioncall>{{"name": "search_baidu","arguments": {{"query": "user_provided_query"}}}}</functioncall>
    将“user_provided_query”替换为用户提供的实际查询，并确保整个函数调用在一行上。
    生成函数调用后，执行该函数搜索百度，抓取搜索结果url的内容，以1000个字符为块添加到结果中，并返回url。
    
    示例: 用户: 百度搜索 user query / question
 
"""
    
    messages.insert(0, {"role": "system", "content": system_message})
    response = client.chat.completions.create(model="qwen2.5:latest", messages=messages, functions=functions, temperature=0)
    message_content = response.choices[0].message.content
    function_call = parse_function_call(message_content)
    if function_call:
        function_name = function_call["name"]
        function_arguments = function_call["arguments"]
        if function_name == "search_baidu":
            search_result = search_baidu(**function_arguments)
            return f"搜索结果:\n{search_result}\n"
        else:
            return f"Unknown function: {function_name}"
    return message_content

conversation_history = []
handler = ChatBotGraph()
while True:
    user_input = input(NEON_GREEN + "用户：" + RESET_COLOR)
    if user_input == '退出':
        print(PINK + "小助手：" + RESET_COLOR, "已退出，欢迎您随时与我再次聊天。")
        break
    answer = handler.chat_main(user_input)
    if answer:
        user_input = answer
    conversation_history = conversation_history[-1:] #change this if you want full history
    conversation_history.append({"role": "user", "content": user_input})
    response = chat(conversation_history)
    conversation_history.append({"role": "assistant", "content": response})
    print(PINK + "小助手：" + RESET_COLOR, response)
