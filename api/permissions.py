from src.core.cms.adp.base_permissions import BaseModulePermission

MODULE_NAME = 'ai_assistant'

AI_ASSISTANT_VIEW = 'ai_assistant_view'


class _BaseAiAssistantPermission(BaseModulePermission):
    module_name = MODULE_NAME


class CanViewAiAssistant(_BaseAiAssistantPermission):
    required_permission = AI_ASSISTANT_VIEW
