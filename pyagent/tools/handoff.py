"""
交接棒工具 - 用于在不同Agent之间传递上下文

当任务需要全新的对话上下文时，使用此工具将当前状态交接给新Agent。
这会终止当前Agent的运行，并使用全新的messages启动一个新Agent。
"""

from typing import Dict, Any


class HandoffSignal(Exception):
    """
    交接信号异常
    
    当工具返回此异常时，表示需要终止当前Agent并启动新Agent。
    包含新Agent所需的所有上下文信息。
    """
    def __init__(self, task: str, request_history: str, background: str):
        self.task = task
        self.request_history = request_history
        self.background = background
        # 构造新Agent的user_prompt
        self.user_prompt = self._construct_user_prompt()
        super().__init__("Agent交接信号")
    
    def _construct_user_prompt(self) -> str:
        """构造新Agent的user_prompt"""
        prompt_parts = []
        
        if self.request_history:
            prompt_parts.append("===== 历史需求 =====")
            prompt_parts.append(self.request_history)
            prompt_parts.append("")
        
        if self.background:
            prompt_parts.append("===== 背景信息 =====")
            prompt_parts.append(self.background)
            prompt_parts.append("")
        
        prompt_parts.append("===== 当前任务 =====")
        prompt_parts.append(self.task)
        
        return "\n".join(prompt_parts)


def handoff_task(task: str, request_history: str = "", background: str = "") -> Dict[str, Any]:
    """
    交接棒工具 - 将当前任务交接给新的Agent实例
    
    当当前对话上下文过于复杂、token消耗过高，或需要以全新视角处理任务时，
    使用此工具终止当前Agent，并使用精简后的上下文启动新Agent。
    
    Args:
        task: 描述接下来要做的事（纯文本）
        request_history: 描述用户提出过的需求（纯文本，若之前有多条用户消息，需要包含所有相关内容）
        background: 对完成当前任务能起到帮助的背景信息（纯文本），如：
                   - 工作文件夹结构
                   - 项目使用的编程语言
                   - 虚拟环境的方案
                   - 之前做的变更
                   - 重要的代码片段
                   - 当前的进展状态
    
    Returns:
        dict: 包含交接信息的字典（实际不会返回，会抛出HandoffSignal异常）
    
    Raises:
        HandoffSignal: 交接信号，被Agent捕获后用于启动新Agent
    
    Example:
        handoff_task(
            task="实现用户登录功能的前端页面",
            request_history="1. 用户要求创建一个Web应用\\n2. 需要先完成登录功能",
            background="项目使用React+TypeScript，已配置好vite开发环境，目录结构：src/components, src/pages"
        )
    """
    # 抛出交接信号，由Agent捕获并处理
    raise HandoffSignal(
        task=task,
        request_history=request_history,
        background=background
    )


# 工具元信息（供LLM识别）
HANDOFF_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "handoff_task",
            "description": """交接棒工具 - 将当前任务交接给新的Agent实例

当当前对话上下文过于复杂、token消耗过高，或需要以全新视角处理任务时，
使用此工具终止当前Agent，并使用精简后的上下文启动新Agent。

使用场景：
1. 对话历史过长，token消耗过大
2. 需要清理思维，以全新视角处理任务
3. 任务方向发生重大转变
4. 当前对话已积累过多无关信息

调用本工具的时机如下：
1. 对于一个全新的复杂任务，已经规划好任务方向，开始编写具体实现前，调用该工具以专注编写实现
2. 项目代码已经编写完成，转而进入测试阶段前，调用该工具以专注于测试
3. 在项目中翻阅了大量文件，已经确定关键问题和修复方法后，调用该工具以清理无关上下文，专注于修复工作
4. 对于复杂且涉及多领域的综合性问题，先规划任务清单，将其添加到request_history，完成task中指明的项，然后调用本工具，将request_history中的下一项填到task中，以这种方式逐项完成任务
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "描述接下来要做的事（纯文本，需要清晰、具体、可执行）"
                    },
                    "request_history": {
                        "type": "string",
                        "description": "描述用户提出过的需求（纯文本）。若之前有多条用户消息，需要包含所有相关内容（标明是否已经完成），以编号或列表形式呈现"
                    },
                    "background": {
                        "type": "string",
                        "description": """对完成当前任务能起到帮助的背景信息（纯文本），建议包含：
- 工作文件夹结构
- 项目使用的编程语言/框架
- 虚拟环境的方案
- 之前做的关键变更
- 重要的代码片段或配置
- 当前的进展状态和已完成的步骤"""
                    }
                },
                "required": ["task"]
            }
        }
    }
]

# 工具函数映射（供Agent调用）
HANDOFF_FUNCTIONS = {
    "handoff_task": handoff_task
}
