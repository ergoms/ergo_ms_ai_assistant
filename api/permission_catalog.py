from .permissions import MODULE_NAME, AI_ASSISTANT_VIEW

PERMISSION_CATALOG = {
    'module_name': MODULE_NAME,
    'module_label': 'AI-ассистент',
    'user_description': (
        'Помощник по интерфейсу ERGO MS: подсказывает, где найти разделы, '
        'объясняет типичные действия и отвечает на вопросы по загруженным документам.'
    ),
    'permissions': {
        AI_ASSISTANT_VIEW: 'Просмотр AI-ассистента',
    },
}
