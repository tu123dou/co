import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { synthesizeSpeech } from "../../../api/audio";

export default function useSpeechPlayback(text: string) {
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  useEffect(() => () => {
    audioRef.current?.pause();
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }, []);

  async function toggle() {
    if (audioRef.current && playing) {
      audioRef.current.pause();
      setPlaying(false);
      return;
    }
    if (audioRef.current) {
      await audioRef.current.play();
      setPlaying(true);
      return;
    }
    setLoading(true);
    try {
      const response = await synthesizeSpeech(text.slice(0, 3000));
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "语音合成失败");
      }
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      urlRef.current = url;
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      audio.onerror = () => {
        setPlaying(false);
        message.error("语音播放失败");
      };
      await audio.play();
      setPlaying(true);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return { loading, playing, toggle };
}
