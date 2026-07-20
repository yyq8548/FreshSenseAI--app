export const FPS = 30;
export const TOTAL_FRAMES = 60 * FPS;

export type Callout = {label: string; x: number; y: number; delayFrame: number};
export type SceneKind = 'title' | 'screenshot' | 'manager' | 'closing';
export type Scene = {
  id: string;
  kind: SceneKind;
  startFrame: number;
  endFrame: number;
  screenshot?: string;
  headline: string;
  narration: string;
  callouts: readonly Callout[];
};

export const SCENES: readonly Scene[] = [
  {id: 'problem', kind: 'title', startFrame: 0, endFrame: 150, headline: 'Fruit checks happen fast', narration: 'Fruit checks happen fast, but the record often disappears with the shift.', callouts: []},
  {id: 'overview', kind: 'screenshot', startFrame: 150, endFrame: 360, screenshot: 'overview.png', headline: 'One shared inspection workspace', narration: 'FreshSense gives small grocery teams one place to inspect fruit and follow review work.', callouts: [{label: 'Live inspection history', x: 73, y: 45, delayFrame: 40}]},
  {id: 'batch', kind: 'screenshot', startFrame: 360, endFrame: 690, screenshot: 'batch-inspection.png', headline: 'Inspect a batch in one step', narration: 'Staff can take a photo or add twenty images at once. The model covers apples, bananas, oranges, mangoes, tomatoes, and pears. Photos are not stored by default.', callouts: [{label: 'Camera or multi-photo upload', x: 36, y: 68, delayFrame: 45}, {label: 'Up to 20 images', x: 47, y: 58, delayFrame: 100}]},
  {id: 'vision', kind: 'screenshot', startFrame: 690, endFrame: 990, screenshot: 'batch-inspection.png', headline: 'Classify, or withhold', narration: 'A DenseNet201 classifier looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs instead of forcing a label.', callouts: [{label: 'DenseNet201 result', x: 73, y: 28, delayFrame: 40}, {label: 'Uncertain inputs are withheld', x: 73, y: 52, delayFrame: 110}]},
  {id: 'agent', kind: 'screenshot', startFrame: 990, endFrame: 1290, screenshot: 'agent-activity.png', headline: 'A bounded Agent follows through', narration: 'Next, a bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval.', callouts: [{label: 'Automatic follow-up tasks', x: 44, y: 31, delayFrame: 45}, {label: 'Manager approval boundary', x: 70, y: 31, delayFrame: 115}]},
  {id: 'review', kind: 'screenshot', startFrame: 1290, endFrame: 1500, screenshot: 'review-queue.png', headline: 'People make the final call', narration: 'Staff confirm or correct results in the review queue.', callouts: [{label: 'Human-observed outcome', x: 72, y: 42, delayFrame: 45}]},
  {id: 'manager', kind: 'manager', startFrame: 1500, endFrame: 1680, screenshot: 'manager-chat.png', headline: 'Grounded answers, daily evidence', narration: 'Managers ask grounded questions about inspection history and Agent decisions, then check the daily report.', callouts: [{label: 'Workspace citations', x: 61, y: 56, delayFrame: 30}]},
  {id: 'cta', kind: 'closing', startFrame: 1680, endFrame: 1800, headline: 'See FreshSense working', narration: 'FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try freshsenseai.com, or view the code on GitHub.', callouts: []},
] as const;

export const NARRATION_TEXT = SCENES.map((scene) => scene.narration).join(' ');
