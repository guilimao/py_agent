from openai import OpenAI
import sys
import os
from agent import Agent
from config import get_system_prompt
from utils import get_user_message
        
def main():
    
    system_prompt = get_system_prompt()
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    agent = Agent(client, get_user_message,system_prompt)
    agent.run()

if __name__ == "__main__":
    main()