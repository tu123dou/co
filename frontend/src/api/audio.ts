import { rawRequest } from "./client";

export const transcribeAudio = (audio: Blob, signal?: AbortSignal) =>
  rawRequest("/audio/transcribe", {
    signal,
    method: "POST",
    headers: { "Content-Type": audio.type },
    body: audio,
  });

export const synthesizeSpeech = (text: string, signal?: AbortSignal) =>
  rawRequest("/audio/speech", {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
