import { historyApi } from "./axios.js";

export async function listInterviewHistory() {
  const { data } = await historyApi.get("/interviews/");
  return data;
}

export async function getInterviewHistoryDetail(id) {
  const { data } = await historyApi.get(`/interviews/${id}/`);
  return data;
}

export async function renameInterview(id, title) {
  const { data } = await historyApi.patch(`/interviews/${id}/`, { title });
  return data;
}

export async function deleteInterview(id) {
  await historyApi.delete(`/interviews/${id}/`);
}

export async function getInterviewChat(id) {
  const { data } = await historyApi.get(`/interviews/${id}/chat/`);
  return data;
}

export async function sendInterviewChatMessage(id, message) {
  const { data } = await historyApi.post(`/interviews/${id}/chat/`, { message });
  return data;
}
