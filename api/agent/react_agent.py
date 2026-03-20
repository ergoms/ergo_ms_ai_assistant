"""
ReAct (Reasoning + Acting) агент для AI ассистента.
Реализует паттерн: Thought → Action → Observation → ... → Final Answer
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REACT_SYSTEM_PROMPT = """You are an AI assistant that uses tools to answer user questions.
Use the ReAct pattern: Thought → Action → Observation → Final Answer.

Available tools:
{tools_description}

Always respond in this exact format (use Russian language for Thought and Final Answer):

Thought: <your reasoning about what to do next>
Action: <tool_name or "none" if no tool needed>
Action Input: <JSON parameters for the tool, or empty if no tool>
Observation: <result of the action (filled by system)>
...
Final Answer: <your final response to the user>

Rules:
- Use tools only when truly necessary for the task
- If the question can be answered directly, go straight to Final Answer
- Maximum {max_iterations} iterations
- Always end with "Final Answer:"
"""

REACT_DIRECT_PROMPT = """You are a helpful AI assistant. Answer the user's question directly and concisely.
Use the information from context if provided. Answer in Russian unless asked otherwise."""


class ReActAgent:
    """
    ReAct агент — выполняет цикл Thought/Action/Observation до получения Final Answer.
    """

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations

    def _parse_react_response(self, text: str) -> Dict[str, Any]:
        """Парсит ответ LLM в формате ReAct."""
        result = {
            "thought": "",
            "action": "",
            "action_input": {},
            "final_answer": "",
        }

        # Final Answer
        fa_match = re.search(r'Final Answer:\s*(.*?)(?=$|\n\n)', text, re.DOTALL | re.IGNORECASE)
        if fa_match:
            result["final_answer"] = fa_match.group(1).strip()

        # Thought
        t_match = re.search(r'Thought:\s*(.*?)(?=Action:|Final Answer:|$)', text, re.DOTALL | re.IGNORECASE)
        if t_match:
            result["thought"] = t_match.group(1).strip()

        # Action
        a_match = re.search(r'Action:\s*(.+?)(?=\n|Action Input:|$)', text, re.IGNORECASE)
        if a_match:
            result["action"] = a_match.group(1).strip()

        # Action Input
        ai_match = re.search(r'Action Input:\s*(.*?)(?=Observation:|Final Answer:|Thought:|$)', text, re.DOTALL | re.IGNORECASE)
        if ai_match:
            raw = ai_match.group(1).strip()
            try:
                result["action_input"] = json.loads(raw) if raw else {}
            except (json.JSONDecodeError, ValueError):
                result["action_input"] = {"raw": raw}

        return result

    def _build_tools_description(self, skills: List[Dict[str, Any]]) -> str:
        """Формирует описание инструментов для системного промпта."""
        if not skills:
            return "No tools available."
        lines = []
        for skill in skills:
            name = skill.get("name", "")
            desc = skill.get("description", "")
            params = skill.get("parameters", {})
            props = params.get("properties", {})
            required = params.get("required", [])
            lines.append(f"- {name}: {desc}")
            for param, info in props.items():
                req = " (required)" if param in required else " (optional)"
                lines.append(f"    {param} ({info.get('type', 'string')}): {info.get('description', '')}{req}")
        return "\n".join(lines)

    def _needs_tools(self, query: str, skills: List[Dict[str, Any]]) -> bool:
        """Простая эвристика: нужны ли инструменты для этого запроса."""
        if not skills:
            return False
        # Ключевые слова, явно указывающие на вызов инструмента
        action_keywords = [
            'посчитай', 'вычисли', 'сколько будет', 'создай документ', 'сделай файл',
            'сформируй отчёт', 'выгрузи', 'построй график', 'создай график',
            'visualize', 'calculate', 'compute', 'generate document', 'create report',
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in action_keywords)

    def run(
        self,
        query: str,
        context: str,
        skills: List[Dict[str, Any]],
        history: List[Dict[str, str]],
        llm_client: Any,
        skills_manager: Any,
        session: Any = None,
        user: Any = None,
        module: str = "chat",
    ) -> Dict[str, Any]:
        """
        Запускает ReAct цикл.

        Returns:
            {
                "answer": str,          # финальный ответ
                "skill_result": ...,    # результат последнего навыка
                "skill_display_name": str,
                "skill_call": dict,
                "thoughts": [str],      # цепочка рассуждений
                "used_react": bool,
            }
        """
        # Если инструменты не нужны — прямой ответ
        if not self._needs_tools(query, skills):
            return self._direct_answer(query, context, history, llm_client)

        tools_desc = self._build_tools_description(skills)
        system_msg = REACT_SYSTEM_PROMPT.format(
            tools_description=tools_desc,
            max_iterations=self.max_iterations,
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_msg}]
        # Добавляем релевантную историю (последние 4 сообщения)
        for msg in history[-4:]:
            messages.append(msg)

        # Пользовательский запрос с контекстом
        user_content = query
        if context:
            user_content = f"[Контекст из базы знаний]\n{context}\n\n{query}"
        messages.append({"role": "user", "content": user_content})

        thoughts = []
        skill_result = None
        skill_display_name = None
        skill_call = None
        execution_context = {"user": user, "session": session, "module": module}

        for iteration in range(self.max_iterations):
            try:
                response = llm_client.chat(messages, temperature=0.2, num_predict=800)
            except Exception as e:
                logger.error(f"ReAct: ошибка LLM на итерации {iteration}: {e}")
                break

            parsed = self._parse_react_response(response)
            if parsed["thought"]:
                thoughts.append(parsed["thought"])

            # Если есть Final Answer — возвращаем
            if parsed["final_answer"]:
                return {
                    "answer": parsed["final_answer"],
                    "skill_result": skill_result,
                    "skill_display_name": skill_display_name,
                    "skill_call": skill_call,
                    "thoughts": thoughts,
                    "used_react": True,
                }

            # Если есть Action — выполняем
            action = parsed.get("action", "").strip().lower()
            if action and action != "none":
                action_input = parsed.get("action_input", {})
                skill_call = {"tool": action, "parameters": action_input}

                try:
                    skill = skills_manager.get_skill(action)
                    if skill:
                        skill_display_name = skill.display_name
                    skill_result = skills_manager.execute_skill(action, query, action_input, execution_context)
                    observation = str(skill_result.result) if skill_result.success else f"Error: {skill_result.error}"
                except Exception as e:
                    observation = f"Tool execution error: {e}"

                # Добавляем Observation в контекст разговора
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                # Нет действия и нет финального ответа — прерываем
                break

        # Если цикл завершился без Final Answer — возвращаем последний ответ
        last_answer = thoughts[-1] if thoughts else query
        return {
            "answer": last_answer,
            "skill_result": skill_result,
            "skill_display_name": skill_display_name,
            "skill_call": skill_call,
            "thoughts": thoughts,
            "used_react": True,
        }

    def _direct_answer(
        self,
        query: str,
        context: str,
        history: List[Dict[str, str]],
        llm_client: Any,
    ) -> Dict[str, Any]:
        """Прямой ответ без ReAct цикла (для простых вопросов)."""
        messages: List[Dict[str, str]] = [{"role": "system", "content": REACT_DIRECT_PROMPT}]
        for msg in history[-8:]:
            messages.append(msg)

        user_content = query
        if context:
            user_content = (
                f"[Контекст из базы знаний]\n{context}\n\n"
                "Используй эту информацию для ответа на вопрос пользователя. "
                "Если в базе знаний есть релевантная информация, обязательно используй её.\n\n"
                f"{query}"
            )
        messages.append({"role": "user", "content": user_content})

        try:
            answer = llm_client.chat(messages, temperature=0.2)
        except Exception as e:
            logger.error(f"ReAct direct answer error: {e}")
            answer = "Извините, произошла ошибка при генерации ответа."

        return {
            "answer": answer.strip(),
            "skill_result": None,
            "skill_display_name": None,
            "skill_call": None,
            "thoughts": [],
            "used_react": False,
        }
