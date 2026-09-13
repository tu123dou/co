import { rawRequest } from "./client";

export const transcribeAudio = (audio: Blob) => rawRequest("/audio/transcribe", {
  method: "POST", headers: { "Content-Type": audio.type }, body: audio,
});
export const synthesizeSpeech = (text: string) => rawRequest("/audio/speech", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
});
