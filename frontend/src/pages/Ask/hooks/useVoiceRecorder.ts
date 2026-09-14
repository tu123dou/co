import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { transcribeAudio } from "../../../api/audio";

export function useVoiceRecorder(onText: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const media = useRef<MediaRecorder | null>(null);
  const microphone = useRef<MediaStream | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const pending = useRef(false);
  const onTextRef = useRef(onText);

  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    return () => {
      controller.abort();
      const recorder = media.current;
      if (recorder) {
        // 卸载不是用户提交录音：先解绑回调，再停止媒体。
        recorder.onstop = null;
        recorder.ondataavailable = null;
        recorder.onerror = null;
        if (recorder.state !== "inactive") recorder.stop();
      }
      microphone.current?.getTracks().forEach((track) => track.stop());
      microphone.current = null;
      media.current = null;
      pending.current = false;
    };
  }, []);

  const toggle = async () => {
    const controller = lifetime.current;
    if (!controller || controller.signal.aborted) return;
    if (media.current?.state === "recording") {
      media.current.stop();
      return;
    }
    // 覆盖授权弹窗、stop 回调与转写期间，防止连续点击启动多份录音。
    if (pending.current) return;
    if (!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder) {
      message.warning("当前环境无法使用麦克风，请通过 HTTPS 或 localhost 访问");
      return;
    }
    pending.current = true;
    let stream: MediaStream | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (controller.signal.aborted) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const tracks = stream;
      const parts: BlobPart[] = [];
      const supported = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      const recorder = new MediaRecorder(stream, supported ? { mimeType: supported } : undefined);
      microphone.current = stream;
      media.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size) parts.push(event.data);
      };
      recorder.onerror = () => {
        recorder.onerror = null;
        recorder.onstop = null;
        recorder.ondataavailable = null;
        tracks.getTracks().forEach((track) => track.stop());
        if (recorder.state !== "inactive") recorder.stop();
        if (controller.signal.aborted) return;
        media.current = null;
        microphone.current = null;
        pending.current = false;
        setRecording(false);
        message.error("录音失败，请检查麦克风权限");
      };
      recorder.onstop = async () => {
        tracks.getTracks().forEach((track) => track.stop());
        if (controller.signal.aborted) return;
        media.current = null;
        microphone.current = null;
        setRecording(false);
        const blob = new Blob(parts, { type: recorder.mimeType || "audio/webm" });
        if (!blob.size) {
          pending.current = false;
          return;
        }
        setTranscribing(true);
        try {
          const response = await transcribeAudio(blob, controller.signal);
          const payload: unknown = await response.json();
          if (controller.signal.aborted) return;
          if (!response.ok) throw new Error("语音识别失败，请重试");
          if (
            typeof payload !== "object" ||
            payload === null ||
            !("text" in payload) ||
            typeof payload.text !== "string"
          ) {
            throw new Error("服务返回了无法识别的语音内容");
          }
          onTextRef.current(payload.text);
          message.success("语音已转换为文字");
        } catch (cause) {
          if (!controller.signal.aborted)
            message.error(cause instanceof Error ? cause.message : "语音识别失败");
        } finally {
          if (!controller.signal.aborted) {
            pending.current = false;
            setTranscribing(false);
          }
        }
      };
      recorder.start();
      setRecording(true);
    } catch (cause) {
      stream?.getTracks().forEach((track) => track.stop());
      if (controller.signal.aborted) return;
      media.current = null;
      microphone.current = null;
      pending.current = false;
      message.error(
        cause instanceof DOMException && cause.name === "NotAllowedError"
          ? "请允许浏览器使用麦克风"
          : "无法启动录音",
      );
    }
  };

  return { recording, transcribing, toggle };
}
