"""
Навык для создания документов PDF.
Использует MD шаблоны и генераторы документов.
"""
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

from ...base import BaseSkill, SkillResult
from .template_loader import get_template_loader
from .generators import PDFGenerator
from ....media_storage import (
    commit_generated_document,
    scratch_session,
    signed_url,
)
from ....file_uploads import assign_knowledge_file
from ....ownership import owner_public_id


class DocumentSkill(BaseSkill):
    """Навык для создания документов PDF на основе шаблонов."""
    
    def __init__(self):
        self._pdf_generator = PDFGenerator()
        self._template_loader = get_template_loader()
    
    @property
    def name(self) -> str:
        return "create_document"
    
    @property
    def display_name(self) -> str:
        return "Документы"
    
    @property
    def description(self) -> str:
        templates_info = self._template_loader.get_templates_description()
        return f"""Создает документ PDF на основе шаблонов.

ИСПОЛЬЗУЙ ТОЛЬКО когда пользователь ЯВНО просит создать/сформировать/выгрузить документ:
- "создай документ", "сделай файл", "запиши в документ"
- "сформируй отчёт", "выгрузи отчёт", "экспортируй в файл"
- "сохрани как документ", "создай PDF"

НЕ используй этот навык если:
- Пользователь просто задает вопрос или просит объяснить что-то
- В ответе упоминается слово "документ" в контексте информации (например: "в документе указано...")
- Пользователь просит найти информацию или проиндексировать документ
- Это обычный вопрос к базе знаний (RAG)

Этот навык только для СОЗДАНИЯ нового файла, а не для работы с существующими документами.

{templates_info}"""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        templates = self._template_loader.get_all_templates()
        template_ids = [t.id for t in templates] if templates else ["report", "analysis"]
        
        return {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "enum": template_ids,
                    "description": f"ID шаблона документа: {', '.join(template_ids)}"
                },
                "format": {
                    "type": "string",
                    "enum": ["pdf"],
                    "description": "Формат документа: pdf",
                    "default": "pdf"
                },
                "title": {
                    "type": "string",
                    "description": "Заголовок документа"
                },
                "content": {
                    "type": "string",
                    "description": "Основное содержимое документа"
                },
                "summary": {
                    "type": "string",
                    "description": "Краткое резюме (для шаблона analysis)"
                },
                "analysis": {
                    "type": "string",
                    "description": "Детальный анализ (для шаблона analysis)"
                },
                "conclusions": {
                    "type": "string",
                    "description": "Выводы (для шаблона analysis)"
                },
                "recommendations": {
                    "type": "string",
                    "description": "Рекомендации (для шаблона analysis)"
                },
                "author": {
                    "type": "string",
                    "description": "Автор документа"
                },
            },
            "required": ["template", "title"]
        }
    
    def execute(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None, 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Создает документ на основе шаблона."""
        if not parameters:
            return SkillResult(
                success=False,
                error="Не указаны параметры для создания документа"
            )
        
        template_id = parameters.get('template', 'report')
        doc_format = parameters.get('format', 'pdf')
        title = parameters.get('title', 'Документ')
        
        # Проверяем формат - Word отчеты отключены
        if doc_format == 'docx':
            return SkillResult(
                success=False,
                error="Формирование Word отчетов отключено. Используйте формат PDF."
            )
        
        # Получаем шаблон
        template = self._template_loader.get_template(template_id)
        if not template:
            # Используем базовый шаблон если указанный не найден
            template = self._template_loader.get_template('report')
            if not template:
                return self._create_simple_document(parameters, doc_format, context)
        
        # Собираем переменные для шаблона
        variables = {
            'title': title,
            'author': parameters.get('author', 'AI Ассистент'),
            'date': datetime.now().strftime('%d.%m.%Y'),
            'content': parameters.get('content', ''),
            'summary': parameters.get('summary', ''),
            'analysis': parameters.get('analysis', ''),
            'conclusions': parameters.get('conclusions', ''),
            'recommendations': parameters.get('recommendations', ''),
        }
        
        # Рендерим шаблон
        rendered_content = template.render(variables)
        
        try:
            storage_path, filename, download_url = self._generate_and_store(
                rendered_content, title, doc_format, context
            )
            document_info = self._save_document_info(
                title=title,
                storage_path=storage_path,
                doc_format=doc_format,
                template_id=template_id,
                context=context,
            )
            return SkillResult(
                success=True,
                result=f"Документ '{title}' успешно создан.\n\n[Скачать {filename}]({download_url})",
                metadata={
                    'document_id': document_info.get('id'),
                    'file_path': storage_path,
                    'filename': filename,
                    'download_url': download_url,
                    'format': doc_format,
                    'template': template_id,
                }
            )
        except Exception as e:
            return SkillResult(
                success=False,
                error=f"Ошибка создания документа: {str(e)}"
            )
    
    def _create_simple_document(
        self, 
        parameters: Dict[str, Any], 
        doc_format: str, 
        context: Optional[Dict[str, Any]]
    ) -> SkillResult:
        """Создает простой документ без шаблона."""
        # Проверяем формат - Word отчеты отключены
        if doc_format == 'docx':
            return SkillResult(
                success=False,
                error="Формирование Word отчетов отключено. Используйте формат PDF."
            )
        
        title = parameters.get('title', 'Документ')
        content = parameters.get('content', '')
        
        # Простой Markdown
        markdown_content = f"""# {title}

**Автор:** {parameters.get('author', 'AI Ассистент')}  
**Дата:** {datetime.now().strftime('%d.%m.%Y')}

---

{content}

---

*Документ сгенерирован системой ERGO MS*
"""
        
        try:
            storage_path, filename, download_url = self._generate_and_store(
                markdown_content, title, doc_format, context
            )
            document_info = self._save_document_info(
                title=title,
                storage_path=storage_path,
                doc_format=doc_format,
                template_id='simple',
                context=context,
            )
            return SkillResult(
                success=True,
                result=f"Документ '{title}' успешно создан.\n\n[Скачать {filename}]({download_url})",
                metadata={
                    'document_id': document_info.get('id'),
                    'file_path': storage_path,
                    'filename': filename,
                    'download_url': download_url,
                    'format': doc_format,
                }
            )
        except Exception as e:
            return SkillResult(
                success=False,
                error=f"Ошибка создания документа: {str(e)}"
            )

    def _build_filename(self, title: str, doc_format: str) -> str:
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title[:50] or 'document'
        unique_id = str(uuid.uuid4())[:8]
        return f"{safe_title}_{unique_id}.{doc_format}"

    def _generate_and_store(
        self,
        content: str,
        title: str,
        doc_format: str,
        context: Optional[Dict[str, Any]],
    ) -> Tuple[str, str, str]:
        """Генерирует PDF в scratch и коммитит в media_api."""
        user = context.get('user') if context else None
        user_id = getattr(user, 'id', None) if user else None
        filename = self._build_filename(title, doc_format)

        with scratch_session('ai_assistant_generated') as workdir:
            local_path = Path(workdir) / filename
            generated = self._pdf_generator.generate(content, local_path, title=title)
            storage_path = commit_generated_document(generated, user_id, filename)

        download_url = signed_url(storage_path) or ''
        return storage_path, filename, download_url
    
    def _save_document_info(
        self,
        title: str,
        storage_path: str,
        doc_format: str,
        template_id: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Сохраняет информацию о документе в БД и привязывает файл media_api."""
        try:
            from ....models import KnowledgeDocument
            
            user = context.get('user') if context else None
            
            document = KnowledgeDocument.objects.create(
                user_public_id=owner_public_id(user, required=False),
                corpus=KnowledgeDocument.CORPUS_USER,
                title=title,
                content=f"Документ в формате {doc_format.upper()}",
                file_type=doc_format,
                source='ai_assistant_skill',
                metadata={
                    'created_by': 'ai_assistant',
                    'skill': 'document_creation',
                    'template': template_id,
                    'storage_path': storage_path,
                }
            )
            assign_knowledge_file(document, file_path=storage_path)
            
            return {
                'id': str(document.id),
                'title': document.title,
            }
        except Exception:
            return {'id': None, 'title': title}
