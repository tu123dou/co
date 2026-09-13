import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { transcribeAudio } from "../../../api/audio";

export default function useVoiceInput(onTranscript: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => () => {
    recorder.current?.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  async function toggleRecording() {
    if (recording) return recorder.current?.stop();
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      message.warning("当前页面无法使用麦克风，请通过 HTTPS 或 localhost 访问");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType = preferredTypes.find((type) => MediaRecorder.isTypeSupported(type));
      const nextRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorder.current = nextRecorder;
      streamRef.current = stream;
      chunks.current = [];
      nextRecorder.ondataavailable = (event) => event.data.size && chunks.current.push(event.data);
      nextRecorder.onerror = () => message.error("录音失败，请检查麦克风权限");
      nextRecorder.onstop = async () => {
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        const blob = new Blob(chunks.current, { type: nextRecorder.mimeType || "audio/webm" });
        if (!blob.size) return;
        setTranscribing(true);
        try {
          const response = await transcribeAudio(blob);
          if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "语音识别失败");
          }
          const data = await response.json() as { text: string };
          onTranscript(data.text);
          message.success("语音已转换为文字");
        } catch (error) {
          message.error((error as Error).message);
        } finally {
          setTranscribing(false);
          recorder.current = null;
          chunks.current = [];
        }
      };
      nextRecorder.start();
      setRecording(true);
    } catch (error) {
      message.error((error as DOMException).name === "NotAllowedError" ? "请允许浏览器使用麦克风" : "无法启动录音");
    }
  }

  return { recording, transcribing, toggleRecording };
}
