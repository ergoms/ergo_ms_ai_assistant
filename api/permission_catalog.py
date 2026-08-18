from .permissions import MODULE_NAME, AI_ASSISTANT_MINI_CHAT, AI_ASSISTANT_VIEW

PERMISSION_CATALOG = {
    'module_name': MODULE_NAME,
    'module_label': 'AI-ассистент',
    'user_description': (
        'Помощник по интерфейсу ERGO MS: подсказывает, где найти разделы, '
        'объясняет типичные действия и отвечает на вопросы по загруженным документам. '
        'Плавающий мини-чат — отдельное право, без него виджет скрыт.'
    ),
    'permissions': {
        AI_ASSISTANT_VIEW: 'Просмотр хаба AI-ассистента',
        AI_ASSISTANT_MINI_CHAT: (
            'Мини-чат AI-ассистента (меню приложений и плавающий виджет)'
        ),
    },
}
