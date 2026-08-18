from src.core.cms.adp.base_permissions import BaseModulePermission

MODULE_NAME = 'ai_assistant'

AI_ASSISTANT_VIEW = 'ai_assistant_view'
AI_ASSISTANT_MINI_CHAT = 'ai_assistant_mini_chat'


class _BaseAiAssistantPermission(BaseModulePermission):
    module_name = MODULE_NAME


class CanViewAiAssistant(_BaseAiAssistantPermission):
    required_permission = AI_ASSISTANT_VIEW


class CanUseAiAssistantMiniChat(_BaseAiAssistantPermission):
    required_permission = AI_ASSISTANT_MINI_CHAT
