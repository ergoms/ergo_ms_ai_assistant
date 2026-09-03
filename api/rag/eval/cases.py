"""Золотые вопросы про экраны и поля. Без вызова модели в api test."""
from __future__ import annotations

from typing import NotRequired, TypedDict


class HowtoEvalCase(TypedDict):
    id: str
    question: str
    expected_source_any: NotRequired[list[str]]
    must_include_any: NotRequired[list[str]]
    must_include_all: NotRequired[list[str]]
    forbid: NotRequired[list[str]]
    require_owner: NotRequired[str]


EVAL_CASES: list[HowtoEvalCase] = [
    {
        'id': 'core-profile-fields',
        'question': 'Какие поля видны в профиле пользователя?',
        'expected_source_any': ['ui_catalog:Account', 'личный кабинет', '/user'],
        'must_include_any': ['имя', 'фамилия', 'email'],
        'forbid': ['manage.py', 'сериализатор'],
    },
    {
        'id': 'core-settings-path',
        'question': 'Где открыть настройки системы и темы оформления?',
        'expected_source_any': ['/settings', 'настройки', 'темы'],
        'must_include_any': ['настройк', 'тем'],
        'forbid': ['docker', 'ergoms'],
    },
    {
        'id': 'porosity-create-fields',
        'question': 'Какие поля заполнять, чтобы создать анализ пористости?',
        'require_owner': 'porosity_analysis',
        'expected_source_any': [
            'ui_catalog:PorosityAnalysisList',
            'пористост',
            '/porosity-analysis',
        ],
        'must_include_any': ['название', 'масштаб', 'описание', 'группа'],
        'forbid': ['сериализатор', 'manage.py', 'экспорт в excel'],
    },
    {
        'id': 'video-create-from-storage',
        'question': 'Как создать перевод видео из хранилища и какие данные вводить?',
        'require_owner': 'video_analysis',
        'expected_source_any': [
            'video',
            'видео',
            '/video-analysis',
        ],
        'must_include_any': ['видео-хранилищ', 'хран', 'перевод'],
        'forbid': ['manage.py', 'сериализатор'],
    },
]
