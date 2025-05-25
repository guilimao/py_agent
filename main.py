from openai import OpenAI
import sys
import json
import os
from typing import Callable,Tuple
from tools import TOOL_FUNCTIONS,TOOLS

class Agent:
    def __init__(self, client: OpenAI, get_user_message: Callable[[], Tuple[str, bool]],system_prompt:str):
        self.client = client
        self.get_user_message = get_user_message
        self.messages = [{"role": "system", "content": system_prompt}]

    def run(self):
        try:
            print("对话开始，输入‘退出’结束对话")
            while True:
                user_input, has_input = self.get_user_message()
                if not has_input or user_input.lower() == '退出':
                    break
                self.messages.append({"role": "user", "content": user_input})

                while True:
                    full_response = ""
                    tool_calls_cache = {}
                    tool_calls = None

                    stream = self.client.chat.completions.create(
                        model="deepseek-chat",
                        messages=self.messages,
                        stream = True,
                        tools = TOOLS,
                        tool_choice= "auto"
                    )

                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            chunk_content = chunk.choices[0].delta.content
                            full_response += chunk_content
                            #chunk_content = chunk_content.replace('\n', '\n    ')
                            sys.stdout.write(chunk_content)
                            sys.stdout.flush()

                        tool_calls = getattr(chunk.choices[0].delta, 'tool_calls', None)
                        if tool_calls is not None:
                            for tool_chunk in tool_calls if tool_calls else []:
                                if tool_chunk.index not in tool_calls_cache:
                                    tool_calls_cache[tool_chunk.index] = {
                                        'id': '',
                                        'function': {'name': '', 'arguments': ''}
                                    }
                                if tool_chunk.id:
                                    tool_calls_cache[tool_chunk.index]['id'] = tool_chunk.id
                                if hasattr(tool_chunk.function,'name') and tool_chunk.function.name:
                                    tool_calls_cache[tool_chunk.index]['function']['name'] = tool_chunk.function.name
                                if hasattr(tool_chunk.function,'arguments') and tool_chunk.function.arguments:
                                    tool_calls_cache[tool_chunk.index]['function']['arguments'] += tool_chunk.function.arguments
                    print()

                    if full_response:
                        self.messages.append({"role": "assistant", "content": full_response})

                    if tool_calls_cache:
                        tool_calls = list(tool_calls_cache.values())
                        self.messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        'id': tool_call['id'],
                                        'type': 'function',
                                        'function': {
                                            'name': tool_call['function']['name'],
                                            'arguments': tool_call['function']['arguments']
                                        }
                                    }for tool_call in tool_calls
                                ]
                                })
                        for tool_call in tool_calls:
                            function_name = tool_call['function']['name']
                            try:
                                function_args = json.loads(tool_call['function']['arguments'])
                            except json.JSONDecodeError:
                                print(f"工具参数解析失败：{tool_call['function']['arguments']}")
                                continue
                            
                            if function_name in TOOL_FUNCTIONS:
                                function_response = TOOL_FUNCTIONS[function_name](**function_args)
                                print(f"工具调用中：{function_name}")
                                self.messages.append({
                                    "role": "tool", 
                                    "content": str(function_response), 
                                    "tool_call_id": tool_call['id']})
                            else:
                                print(f"未找到工具函数：{function_name}")
                    else:
                        break


        except Exception as e:
            print(f"发生错误: {e}")
        
def get_user_message()->Tuple[str,bool]:
    try:
        line = input("用户输入：")
        return line, True
    except EOFError:
        return "", False
    except KeyboardInterrupt:
        return "", False
def main():
    try:
        with open('system_prompt.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            system_prompt = config.get('system_prompt', "默认系统提示")
    except FileNotFoundError:
        print("配置文件不存在，使用默认系统提示")
        system_prompt = "这是一个默认的系统提示"
    except json.JSONDecodeError:
        print("配置文件格式错误，使用默认系统提示")
        system_prompt = "这是一个默认的系统提示"
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    agent = Agent(client, get_user_message,system_prompt)
    agent.run()

if __name__ == "__main__":
    main()