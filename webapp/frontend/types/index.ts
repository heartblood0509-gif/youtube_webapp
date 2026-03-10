export type Category = 'cosmetics' | 'cruise' | 'other';
export type TTSEngine = 'edge' | 'typecast';
export type BuildStatus = 'idle' | 'building' | 'done' | 'error';

export interface VideoInfo {
  filename: string;
  width: number;
  height: number;
  duration: number;
  size_mb: number;
}

export interface ClipConfig {
  source: string;
  start: number;
  end: number;
}

export interface BuildProgressEvent {
  type: 'progress' | 'done' | 'error' | 'heartbeat';
  step: string;
  step_number: number;
  total_steps: number;
  progress_percent: number;
  message: string;
  result?: VideoResult;
}

export interface VideoResult {
  filename: string;
  path: string;
  url: string;
  width: number;
  height: number;
  duration: number;
  size_mb: number;
}

export interface AppState {
  geminiKey: string;
  currentStep: number;
  projectId: string | null;
  category: Category;
  topic: string;
  pexelsKey: string;
  videoSource: 'upload' | 'youtube' | 'ai' | 'pexels';
  videos: VideoInfo[];
  youtubeUrls: { url: string; name: string }[];
  generatedTitles: string[];
  selectedTitle: string;
  generatedScript: string[];
  ttsEngine: TTSEngine;
  ttsLanguage: string;
  bgmVolume: number;
  clips: ClipConfig[];
  buildJobId: string | null;
  buildStatus: BuildStatus;
  buildProgress: BuildProgressEvent[];
  result: VideoResult | null;
}
