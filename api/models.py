from django.db import models
from pgvector.django import HnswIndex, VectorField

from .settings import RAG_VECTOR_DIMENSIONS

import uuid


class ChatSession(models.Model):
    """
    Сессия чата - представляет один разговор с AI ассистентом
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_public_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    module = models.CharField(max_length=50, default='chat', help_text='Модуль AI ассистента (chat, docs, code и т.д.)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    metadata = models.JSONField(default=dict, blank=True, help_text='Дополнительные данные сессии')
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(
                fields=['user_public_id', '-updated_at'],
                name='ai_assistan_usrpid_upd_idx',
            ),
            models.Index(
                fields=['user_public_id', 'module', '-updated_at'],
                name='ai_assistan_usrpid_mod_idx',
            ),
        ]
    
    def __str__(self):
        return f"{self.user_public_id} - {self.title or 'Без названия'} ({self.module})"
    
    @property
    def message_count(self):
        return self.messages.count()


class ChatMessage(models.Model):
    """
    Сообщение в чате - запрос пользователя или ответ AI
    """
    MESSAGE_TYPE_USER = 'user'
    MESSAGE_TYPE_ASSISTANT = 'assistant'
    MESSAGE_TYPE_CHOICES = [
        (MESSAGE_TYPE_USER, 'Пользователь'),
        (MESSAGE_TYPE_ASSISTANT, 'Ассистент'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    request_started_at = models.DateTimeField(null=True, blank=True, help_text='Время начала запроса (для ответов AI)')
    response_received_at = models.DateTimeField(null=True, blank=True, help_text='Время получения ответа')
    processing_time_ms = models.IntegerField(null=True, blank=True, help_text='Время обработки в миллисекундах')
    
    # Метаданные
    metadata = models.JSONField(default=dict, blank=True, help_text='Дополнительные данные (модель, настройки и т.д.)')
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_message_type_display()} - {self.content[:50]}..."
    
    def calculate_processing_time(self):
        """Вычисляет время обработки на основе временных меток"""
        if self.request_started_at and self.response_received_at:
            delta = self.response_received_at - self.request_started_at
            return int(delta.total_seconds() * 1000)  # в миллисекундах
        return None


class KnowledgeDocument(models.Model):
    """
    Документ в базе знаний RAG
    
    Может хранить либо файл (Word, PDF и т.д.), либо текстовый контент.
    При наличии файла контент извлекается автоматически при индексации.

    corpus=system — общий корпус документации ERGO MS (user_public_id=None).
    corpus=user — документы пользователя.
    """
    CORPUS_USER = 'user'
    CORPUS_SYSTEM = 'system'
    CORPUS_CHOICES = [
        (CORPUS_USER, 'Пользовательский'),
        (CORPUS_SYSTEM, 'Системный'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_public_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text='Владелец документа; пусто для системного корпуса',
    )
    corpus = models.CharField(
        max_length=20,
        choices=CORPUS_CHOICES,
        default=CORPUS_USER,
        db_index=True,
        help_text='Корпус: пользовательский или системный (документация ERGO MS)',
    )
    title = models.CharField(max_length=500, help_text='Название документа')
    
    # Файл документа (Word, PDF и т.д.)
    file = models.FileField(
        upload_to='rag_documents/',
        blank=True,
        null=True,
        help_text='Файл документа (Word, PDF, TXT и т.д.)'
    )
    file_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Тип файла (docx, pdf, txt и т.д.)'
    )
    
    # Текстовое содержимое (опционально, может быть извлечено из файла или введено вручную)
    content = models.TextField(
        blank=True,
        null=True,
        help_text='Текстовое содержимое документа (извлекается из файла автоматически или вводится вручную)'
    )
    
    source = models.CharField(max_length=500, blank=True, null=True, help_text='Источник документа (URL, путь к файлу и т.д.)')
    
    # Метаданные
    metadata = models.JSONField(default=dict, blank=True, help_text='Дополнительные метаданные документа')
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Статус индексации
    is_indexed = models.BooleanField(default=False, help_text='Индексирован ли документ (разбит на chunks с embeddings)')
    indexed_at = models.DateTimeField(null=True, blank=True, help_text='Время последней индексации')
    INDEXING_STATUS_PENDING = 'pending'
    INDEXING_STATUS_RUNNING = 'running'
    INDEXING_STATUS_DONE = 'done'
    INDEXING_STATUS_FAILED = 'failed'
    INDEXING_STATUS_CHOICES = [
        (INDEXING_STATUS_PENDING, 'Ожидает'),
        (INDEXING_STATUS_RUNNING, 'Выполняется'),
        (INDEXING_STATUS_DONE, 'Готово'),
        (INDEXING_STATUS_FAILED, 'Ошибка'),
    ]
    indexing_status = models.CharField(
        max_length=20,
        choices=INDEXING_STATUS_CHOICES,
        default=INDEXING_STATUS_PENDING,
        db_index=True,
        help_text='Статус фоновой индексации документа',
    )
    indexing_error = models.TextField(blank=True, default='', help_text='Текст ошибки последней индексации')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['user_public_id', '-created_at'],
                name='ai_assistan_usrpid_crt_idx',
            ),
            models.Index(fields=['is_indexed']),
            models.Index(
                fields=['corpus', 'is_indexed'],
                name='ai_assistan_corpus_7f2a1b_idx',
            ),
            models.Index(
                fields=['corpus', 'source'],
                name='ai_assistan_corpus_3c9e4d_idx',
            ),
        ]
    
    def __str__(self):
        return f"{self.title} ({'индексирован' if self.is_indexed else 'не индексирован'})"
    
    @property
    def chunks_count(self):
        return self.chunks.count()


class KnowledgeChunk(models.Model):
    """
    Chunk (фрагмент) документа с векторным embedding для RAG
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name='chunks')
    
    # Текст chunk
    content = models.TextField(help_text='Содержимое chunk')
    
    # Позиция в документе
    chunk_index = models.IntegerField(help_text='Индекс chunk в документе (порядковый номер)')
    start_char = models.IntegerField(null=True, blank=True, help_text='Начальная позиция в исходном документе')
    end_char = models.IntegerField(null=True, blank=True, help_text='Конечная позиция в исходном документе')
    
    # Векторное представление (embedding)
    embedding = VectorField(
        dimensions=RAG_VECTOR_DIMENSIONS,
        help_text='Векторное представление текста (embedding) для поиска по схожести',
    )
    embedding_model = models.CharField(
        max_length=100,
        help_text='Модель, использованная для генерации embedding'
    )
    
    # Метаданные
    metadata = models.JSONField(default=dict, blank=True, help_text='Дополнительные метаданные chunk')
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['embedding_model']),
            HnswIndex(
                name='ai_assistan_embed_hnsw_idx',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]
        # Уникальность: один chunk_index на один документ
        unique_together = [['document', 'chunk_index']]
    
    def __str__(self):
        return f"Chunk {self.chunk_index} из документа '{self.document.title}'"


class LlmJob(models.Model):
    """Задача LLM (chat/stream), выполняется Celery worker'ом."""

    KIND_CHAT = 'chat'
    KIND_CHAT_STREAM = 'chat_stream'
    KIND_CHOICES = [
        (KIND_CHAT, 'Chat'),
        (KIND_CHAT_STREAM, 'Chat stream'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_public_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='llm_jobs',
        null=True,
        blank=True,
    )
    user_message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        related_name='llm_jobs',
        null=True,
        blank=True,
    )
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='')
    event_seq = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['user_public_id', '-created_at'],
                name='ai_assistan_usrpid_job_idx',
            ),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'LlmJob {self.id} ({self.kind}/{self.status})'


class LlmJobEvent(models.Model):
    """События стрима LLM для SSE (chunk/done/error), пишет worker."""

    id = models.BigAutoField(primary_key=True)
    job = models.ForeignKey(LlmJob, on_delete=models.CASCADE, related_name='events')
    seq = models.PositiveIntegerField()
    event = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['seq']
        constraints = [
            models.UniqueConstraint(fields=['job', 'seq'], name='ai_assistant_llmjobevent_job_seq'),
        ]
        indexes = [
            models.Index(fields=['job', 'seq']),
        ]

    def __str__(self):
        return f'LlmJobEvent {self.job_id}#{self.seq}'
