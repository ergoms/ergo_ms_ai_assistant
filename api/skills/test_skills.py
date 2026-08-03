"""
Скрипт для тестирования навыков AI ассистента.

Предпочтительно: ergoms api test_skills

В shell:
    ergoms api shell
    >>> exec(open('modules/ai_assistant/api/skills/test_skills.py', encoding='utf-8').read())
"""
from modules.ai_assistant.api.skills import get_skills_manager
from modules.ai_assistant.api.skills.integration import (
    build_skills_prompt,
    execute_skill_from_llm_response,
)

print('=' * 80)
print('ТЕСТИРОВАНИЕ НАВЫКОВ AI АССИСТЕНТА')
print('=' * 80)

manager = get_skills_manager()
skills = manager.get_all_skills()
print(f'Зарегистрировано навыков: {len(skills)}')
for skill in skills:
    print(f'  - {skill.name}: {skill.description}')

function_defs = manager.get_function_definitions()
print()
print('Промпт навыков для LLM (первые 500 символов):')
prompt = build_skills_prompt(function_defs)
print(prompt[:500] + ('...' if len(prompt) > 500 else ''))
print()

sample = '[EXECUTE]{"tool": "math_calculator", "parameters": {"expression": "2+2"}}'
result, cleaned, display_name, skill_call = execute_skill_from_llm_response(
    sample,
    'посчитай 2+2',
    context={},
)
print('Smoke execute_skill_from_llm_response:')
print(f'  display={display_name}, call={skill_call}, success={getattr(result, "success", None)}')
print('=' * 80)
