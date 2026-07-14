/** @deprecated BI module removed — stub for legacy session loading */
export const biClient = {
  async getConnections() {
    return { success: false, connections: [], error: 'Модуль BI отключён' }
  },
  async getConnectionFiles() {
    return { success: false, files: [], error: 'Модуль BI отключён' }
  },
  async getUserFiles() {
    return { success: false, files: [], error: 'Модуль BI отключён' }
  },
  async askQuestionStream() {
    return { success: false, error: 'Модуль BI отключён' }
  },
}
