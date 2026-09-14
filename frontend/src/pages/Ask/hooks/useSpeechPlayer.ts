import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { synthesizeSpeech } from "../../../api/audio";

export function useSpeechPlayer(text: string) {
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const pending = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    setLoading(false);
    setPlaying(false);
    return () => {
      controller.abort();
      const player = audio.current;
      if (player) {
        player.onended = null;
        player.onerror = null;
        player.pause();
        player.removeAttribute("src");
        player.load();
      }
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      audio.current = null;
      objectUrl.current = null;
      pending.current = false;
    };
  }, [text]);

  const toggle = async () => {
    const controller = lifetime.current;
    if (!controller || controller.signal.aborted || pending.current) return;
    if (audio.current && !audio.current.paused) {
      audio.current.pause();
      setPlaying(false);
      return;
    }
    pending.current = true;
    setLoading(true);
    try {
      let player = audio.current;
      if (!player) {
        const response = await synthesizeSpeech(text.slice(0, 3000), controller.signal);
        if (controller.signal.aborted) return;
        if (!response.ok) throw new Error("语音合成失败，请重试");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        const url = URL.createObjectURL(blob);
        objectUrl.current = url;
        player = new Audio(url);
        audio.current = player;
        player.onended = () => {
          if (!controller.signal.aborted) setPlaying(false);
        };
        player.onerror = () => {
          if (!controller.signal.aborted) {
            setPlaying(false);
            message.error("语音播放失败");
          }
        };
      }
      await player.play();
      if (!controller.signal.aborted) setPlaying(true);
    } catch (cause) {
      if (!controller.signal.aborted) {
        setPlaying(false);
        // 清除失效播放器，让下一次点击可以重新合成。
        const player = audio.current;
        if (player) {
          player.onended = null;
          player.onerror = null;
          player.pause();
          player.removeAttribute("src");
          player.load();
        }
        audio.current = null;
        if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
        objectUrl.current = null;
        message.error(cause instanceof Error ? cause.message : "语音播放失败");
      }
    } finally {
      if (!controller.signal.aborted) {
        pending.current = false;
        setLoading(false);
      }
    }
  };

  return { loading, playing, toggle };
}
