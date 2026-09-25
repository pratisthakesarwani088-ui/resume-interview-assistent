import { assistantApi } from "./axios.js";

const CHAT_PATHS = {
  resume_expert: "/chat/resume-expert/",
  career_coach: "/chat/career-coach/",
  tutor: "/chat/tutor/",
};

export async function getChatHistory(mode) {
  const { data } = await assistantApi.get(CHAT_PATHS[mode]);
  return data; // { mode, selected_role, messages: [...] }
}

export async function sendChatMessage(mode, message, role) {
  const payload = { message };
  if (role) payload.role = role;
  const { data } = await assistantApi.post(CHAT_PATHS[mode], payload);
  return data; // the new assistant ChatMessage
}

export async function getInterviewStatus() {
  const { data } = await assistantApi.get("/interview/status/");
  return data;
}

export async function startInterview(role) {
  const { data } = await assistantApi.post("/interview/start/", { role });
  return data;
}

export async function submitInterviewAnswer(answer) {
  const { data } = await assistantApi.post("/interview/answer/", { answer });
  return data;
}
